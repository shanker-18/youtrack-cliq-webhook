import os
import re
import datetime
import pandas as pd
import psycopg2
from dotenv import load_dotenv

import database

load_dotenv()

def normalize_column_name(col_name):
    if not col_name:
        return "unnamed_column"
    
    col = str(col_name).strip()
    col = re.sub(r'[^a-zA-Z0-9]', '_', col)
    col = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', col)
    col = re.sub(r'_+', '_', col)
    return col.strip('_').lower()

def check_column_collisions(snowflake_cols):
    normalized_mapping = {}
    reverse_mapping = {}

    for orig_col in snowflake_cols:
        norm = normalize_column_name(orig_col)
        normalized_mapping[orig_col] = norm
        
        if norm in reverse_mapping:
            reverse_mapping[norm].append(orig_col)
        else:
            reverse_mapping[norm] = [orig_col]

    collisions = {norm: cols for norm, cols in reverse_mapping.items() if len(cols) > 1}
    
    if collisions:
        details = [f"Normalized column '{norm}' collides with original Snowflake columns: {cols}" for norm, cols in collisions.items()]
        err_msg = "SYNC ABORTED — Normalized column collision detected: " + "; ".join(details)
        return True, err_msg, normalized_mapping

    return False, "", normalized_mapping

def verify_unique_keys(normalized_cols, target_keys):
    missing_keys = [k for k in target_keys if k not in normalized_cols]
    if missing_keys:
        return False, missing_keys
    return True, []

def infer_pg_data_type(series):
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    elif pd.api.types.is_float_dtype(series):
        return "NUMERIC"
    elif pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    else:
        return "TEXT"

def safe_align_postgres_schema(pg_conn, table_name, df, unique_keys):
    cur = pg_conn.cursor()
    
    key_defs = ", ".join([f"{k} VARCHAR(255)" for k in unique_keys])
    create_stmt = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {key_defs},
            data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
            is_manually_edited BOOLEAN DEFAULT FALSE,
            last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    cur.execute(create_stmt)

    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s;
    """, (table_name,))
    existing_pg_cols = {row[0].lower() for row in cur.fetchall()}

    for col in df.columns:
        if col.lower() not in existing_pg_cols:
            pg_type = infer_pg_data_type(df[col])
            alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col} {pg_type};"
            cur.execute(alter_stmt)

    index_name = f"idx_unique_{table_name}_" + "_".join(unique_keys)
    keys_clause = ", ".join(unique_keys)
    
    cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({keys_clause});")
    cur.close()

def upsert_dataframe_to_postgres(pg_conn, table_name, df, unique_keys):
    if df.empty:
        return 0

    cur = pg_conn.cursor()
    cols = list(df.columns)
    
    if 'data_source' not in cols:
        df['data_source'] = 'SNOWFLAKE'
        cols.append('data_source')
    if 'is_manually_edited' not in cols:
        df['is_manually_edited'] = False
        cols.append('is_manually_edited')
    if 'last_modified_at' not in cols:
        df['last_modified_at'] = datetime.datetime.now()
        cols.append('last_modified_at')

    non_key_cols = [c for c in cols if c not in unique_keys and c != 'is_manually_edited']
    
    cols_str = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    conflict_keys_str = ", ".join(unique_keys)

    if non_key_cols:
        update_set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in non_key_cols])
        upsert_query = f"""
            INSERT INTO {table_name} ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_keys_str})
            DO UPDATE SET {update_set_clause}
            WHERE {table_name}.is_manually_edited = FALSE;
        """
    else:
        upsert_query = f"""
            INSERT INTO {table_name} ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_keys_str})
            DO NOTHING;
        """

    records_synced = 0
    for _, row in df.iterrows():
        val_tuple = tuple(None if pd.isna(val) else val for val in row[cols])
        cur.execute(upsert_query, val_tuple)
        records_synced += 1

    cur.close()
    return records_synced

def sync_single_dataset(pg_conn, sf_conn, sf_table_name, pg_table_name, unique_key_env_var):
    if not sf_table_name:
        return False, 0, f"Snowflake table name for '{pg_table_name}' is not configured in .env."

    unique_keys_raw = os.getenv(unique_key_env_var, "").strip()
    if not unique_keys_raw:
        return False, 0, f"Unique key environment variable '{unique_key_env_var}' is not configured."

    unique_keys = [normalize_column_name(k) for k in unique_keys_raw.split(",") if k.strip()]

    try:
        sf_cur = sf_conn.cursor()
        sf_cur.execute(f"SELECT * FROM {sf_table_name};")
        sf_data = sf_cur.fetchall()
        sf_cols = [desc[0] for desc in sf_cur.description]
        sf_cur.close()

        if not sf_data:
            return True, 0, f"No records found in Snowflake source table '{sf_table_name}'."

        df = pd.DataFrame(sf_data, columns=sf_cols)

        has_collision, collision_err, norm_map = check_column_collisions(sf_cols)
        if has_collision:
            return False, 0, collision_err

        df.columns = [norm_map[c] for c in df.columns]

        keys_valid, missing_keys = verify_unique_keys(list(df.columns), unique_keys)
        if not keys_valid:
            return False, 0, f"SYNC ABORTED — Configured unique key(s) {missing_keys} missing from Snowflake table '{sf_table_name}'."

        pg_conn.rollback()

        safe_align_postgres_schema(pg_conn, pg_table_name, df, unique_keys)
        count = upsert_dataframe_to_postgres(pg_conn, pg_table_name, df, unique_keys)
        pg_conn.commit()

        return True, count, ""

    except Exception as e:
        try:
            pg_conn.rollback()
        except Exception:
            pass
        return False, 0, f"Dataset sync failed for '{pg_table_name}': {str(e)}"

def sync_snowflake_to_postgres():
    load_dotenv(override=True)
    sync_started_at = datetime.datetime.now()
    
    sf_account = os.getenv("SNOWFLAKE_ACCOUNT")
    sf_user = os.getenv("SNOWFLAKE_USER")
    sf_password = os.getenv("SNOWFLAKE_PASSWORD")
    sf_warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    sf_database = os.getenv("SNOWFLAKE_DATABASE")
    sf_schema = os.getenv("SNOWFLAKE_SCHEMA")
    sf_role = os.getenv("SNOWFLAKE_ROLE")

    if not sf_account or not sf_user or not sf_password:
        err_msg = "Snowflake connection parameters are missing. Please populate SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD in .env."
        log_sync_result(sync_started_at, datetime.datetime.now(), "FAILED", 0, 0, 0, err_msg)
        return {
            "success": False,
            "status": "FAILED",
            "message": err_msg,
            "timestamp": sync_started_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    sf_conn = None
    pg_conn = None
    try:
        import snowflake.connector

        sf_conn = snowflake.connector.connect(
            account=sf_account,
            user=sf_user,
            password=sf_password,
            warehouse=sf_warehouse,
            database=sf_database,
            schema=sf_schema,
            role=sf_role
        )

        pg_conn = database.get_postgres_connection()

        datasets = [
            ("SNOWFLAKE_PLANNING_TABLE", "planning_data", "POSTGRES_PLANNING_KEY"),
            ("SNOWFLAKE_CONSUMPTION_TABLE", "consumption_data", "POSTGRES_CONSUMPTION_KEY"),
            ("SNOWFLAKE_SHIPMENT_TABLE", "shipment_data", "POSTGRES_SHIPMENT_KEY")
        ]

        synced_counts = {"planning_data": 0, "consumption_data": 0, "shipment_data": 0}
        dataset_errors = []
        dataset_successes = []

        for sf_env_var, pg_table, key_env_var in datasets:
            sf_table = os.getenv(sf_env_var)
            if not sf_table:
                dataset_errors.append(f"Table name variable '{sf_env_var}' not configured.")
                continue

            success, count, err = sync_single_dataset(pg_conn, sf_conn, sf_table, pg_table, key_env_var)
            if success:
                synced_counts[pg_table] = count
                dataset_successes.append(f"{pg_table}: {count} records")
            else:
                dataset_errors.append(err)

        sync_completed_at = datetime.datetime.now()

        if len(dataset_successes) == len(datasets):
            status = "SUCCESS"
            summary_msg = f"Data sync completed successfully. ({', '.join(dataset_successes)})"
        elif len(dataset_successes) > 0:
            status = "PARTIAL_SUCCESS"
            summary_msg = f"Partial sync completed. Success: {', '.join(dataset_successes)}. Errors: {'; '.join(dataset_errors)}"
        else:
            status = "FAILED"
            summary_msg = f"Sync failed. Errors: {'; '.join(dataset_errors)}"

        log_sync_result(
            sync_started_at,
            sync_completed_at,
            status,
            synced_counts["planning_data"],
            synced_counts["consumption_data"],
            synced_counts["shipment_data"],
            "; ".join(dataset_errors) if dataset_errors else None
        )

        return {
            "success": status in ["SUCCESS", "PARTIAL_SUCCESS"],
            "status": status,
            "message": summary_msg,
            "timestamp": sync_completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "counts": synced_counts
        }

    except Exception as e:
        sync_completed_at = datetime.datetime.now()
        err_msg = f"Snowflake sync error: {str(e)}"
        log_sync_result(sync_started_at, sync_completed_at, "FAILED", 0, 0, 0, err_msg)
        return {
            "success": False,
            "status": "FAILED",
            "message": err_msg,
            "timestamp": sync_completed_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    finally:
        if sf_conn:
            try:
                sf_conn.close()
            except Exception:
                pass
        if pg_conn:
            try:
                pg_conn.close()
            except Exception:
                pass

def log_sync_result(started_at, completed_at, status, plan_cnt, cons_cnt, ship_cnt, err_msg):
    conn = None
    try:
        conn = database.get_postgres_connection()
        cur = conn.cursor()
        query = """
            INSERT INTO sync_logs (
                sync_started_at, sync_completed_at, status, 
                planning_records_synced, consumption_records_synced, shipment_records_synced, 
                error_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(query, (started_at, completed_at, status, plan_cnt, cons_cnt, ship_cnt, err_msg))
        conn.commit()
        cur.close()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
