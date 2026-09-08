import os
import uuid
import datetime
import warnings
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

warnings.filterwarnings('ignore', category=UserWarning)

load_dotenv()

def get_snowflake_connection():
    load_dotenv(override=True)
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    role = os.getenv("SNOWFLAKE_ROLE")

    if not account or not user or not password:
        raise ValueError("Snowflake environment variables (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD) must be set.")

    conn = snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
        autocommit=True
    )
    return conn

def initialize_database():
    conn = None
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()

        tbl_plan = os.getenv("SNOWFLAKE_PLANNING_TABLE", "PLANNING_DATA")
        tbl_cons = os.getenv("SNOWFLAKE_CONSUMPTION_TABLE", "CONSUMPTION_DATA")
        tbl_ship = os.getenv("SNOWFLAKE_SHIPMENT_TABLE", "SHIPMENT_DATA")

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_plan} (
                PLANNING_ID VARCHAR(50) PRIMARY KEY,
                PLANNING_DATE DATE,
                REGION VARCHAR(100),
                BUSINESS_UNIT VARCHAR(100),
                PRODUCT VARCHAR(150),
                PRODUCT_CATEGORY VARCHAR(100),
                PLANNED_VOLUME NUMBER(18,2),
                ACTUAL_CONSUMPTION NUMBER(18,2),
                FORECAST_ACCURACY NUMBER(5,2),
                PLAN_VARIANCE NUMBER(10,2),
                STATUS VARCHAR(50),
                CREATED_AT TIMESTAMP_NTZ(9),
                DATA_SOURCE VARCHAR(50) DEFAULT 'SNOWFLAKE',
                IS_MANUALLY_EDITED BOOLEAN DEFAULT FALSE,
                LAST_MODIFIED_AT TIMESTAMP_NTZ(9)
            );
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_cons} (
                CONSUMPTION_ID VARCHAR(50) PRIMARY KEY,
                CONSUMPTION_DATE DATE,
                REGION VARCHAR(100),
                BUSINESS_UNIT VARCHAR(100),
                PRODUCT VARCHAR(150),
                PRODUCT_CATEGORY VARCHAR(100),
                CONSUMPTION_VOLUME NUMBER(18,2),
                PREVIOUS_MONTH_VOLUME NUMBER(18,2),
                CONSUMPTION_GROWTH NUMBER(10,2),
                STATUS VARCHAR(50),
                CREATED_AT TIMESTAMP_NTZ(9),
                DATA_SOURCE VARCHAR(50) DEFAULT 'SNOWFLAKE',
                IS_MANUALLY_EDITED BOOLEAN DEFAULT FALSE,
                LAST_MODIFIED_AT TIMESTAMP_NTZ(9)
            );
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl_ship} (
                SHIPMENT_ID VARCHAR(50) PRIMARY KEY,
                SHIPMENT_DATE DATE,
                REGION VARCHAR(100),
                BUSINESS_UNIT VARCHAR(100),
                PRODUCT VARCHAR(150),
                PRODUCT_CATEGORY VARCHAR(100),
                PLANNED_SHIPMENT_VOLUME NUMBER(18,2),
                ACTUAL_SHIPMENT_VOLUME NUMBER(18,2),
                FULFILLMENT_RATE NUMBER(5,2),
                SHIPMENT_STATUS VARCHAR(50),
                CREATED_AT TIMESTAMP_NTZ(9),
                DATA_SOURCE VARCHAR(50) DEFAULT 'SNOWFLAKE',
                IS_MANUALLY_EDITED BOOLEAN DEFAULT FALSE,
                LAST_MODIFIED_AT TIMESTAMP_NTZ(9)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS SYNC_LOGS (
                ID NUMBER AUTOINCREMENT START 1 INCREMENT 1 PRIMARY KEY,
                SYNC_STARTED_AT TIMESTAMP_NTZ(9),
                SYNC_COMPLETED_AT TIMESTAMP_NTZ(9),
                STATUS VARCHAR(50),
                PLANNING_RECORDS_SYNCED NUMBER DEFAULT 0,
                CONSUMPTION_RECORDS_SYNCED NUMBER DEFAULT 0,
                SHIPMENT_RECORDS_SYNCED NUMBER DEFAULT 0,
                ERROR_MESSAGE TEXT
            );
        """)

        for tbl in [tbl_plan, tbl_cons, tbl_ship]:
            for col_def in ["DATA_SOURCE VARCHAR(50)", "IS_MANUALLY_EDITED BOOLEAN", "LAST_MODIFIED_AT TIMESTAMP_NTZ(9)"]:
                try:
                    cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_def};")
                except Exception:
                    pass

        conn.commit()
        cur.close()
        return {"success": True, "message": "Snowflake database initialized successfully."}
    except Exception as e:
        return {"success": False, "message": f"Snowflake initialization failed: {str(e)}"}
    finally:
        if conn:
            conn.close()

def fetch_planning_data():
    conn = None
    try:
        conn = get_snowflake_connection()
        table_name = os.getenv("SNOWFLAKE_PLANNING_TABLE", "PLANNING_DATA")
        query = f"SELECT * FROM {table_name} ORDER BY PLANNING_DATE DESC, PRODUCT ASC;"
        df = pd.read_sql_query(query, conn)
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception:
        cols = ["planning_id", "planning_date", "region", "business_unit", "product", "product_category", "planned_volume", "actual_consumption", "forecast_accuracy", "plan_variance", "status", "created_at", "data_source", "is_manually_edited", "last_modified_at"]
        return pd.DataFrame(columns=cols)
    finally:
        if conn:
            conn.close()

def insert_planning_record(data_dict):
    conn = None
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()

        planning_id = data_dict.get("planning_id") or f"PLN-{uuid.uuid4().hex[:8].upper()}"
        planning_date = data_dict.get("planning_date") or datetime.date.today().strftime("%Y-%m-%d")
        region = data_dict.get("region", "")
        business_unit = data_dict.get("business_unit", "")
        product = data_dict.get("product", "")
        product_category = data_dict.get("product_category", "")
        
        try:
            planned_vol = float(data_dict.get("planned_volume", 0) or 0)
        except (ValueError, TypeError):
            planned_vol = 0.0

        try:
            actual_cons = float(data_dict.get("actual_consumption", 0) or 0)
        except (ValueError, TypeError):
            actual_cons = 0.0

        plan_variance = planned_vol - actual_cons
        forecast_acc = ((1 - abs(plan_variance) / planned_vol) * 100) if planned_vol > 0 else 0.0
        status = data_dict.get("status", "Active")

        table_name = os.getenv("SNOWFLAKE_PLANNING_TABLE", "PLANNING_DATA")
        for col_def in ["DATA_SOURCE VARCHAR(50)", "IS_MANUALLY_EDITED BOOLEAN", "LAST_MODIFIED_AT TIMESTAMP_NTZ(9)"]:
            try:
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_def};")
            except Exception:
                pass

        query = f"""
            INSERT INTO {table_name} (
                PLANNING_ID, PLANNING_DATE, REGION, BUSINESS_UNIT, PRODUCT, PRODUCT_CATEGORY,
                PLANNED_VOLUME, ACTUAL_CONSUMPTION, FORECAST_ACCURACY, PLAN_VARIANCE, STATUS,
                CREATED_AT, DATA_SOURCE, IS_MANUALLY_EDITED, LAST_MODIFIED_AT
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(), 'MANUAL_PLANNING', TRUE, CURRENT_TIMESTAMP());
        """
        cur.execute(query, (planning_id, planning_date, region, business_unit, product, product_category, planned_vol, actual_cons, forecast_acc, plan_variance, status))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' inserted successfully into Snowflake.", "id": planning_id}
    except Exception as e:
        return {"success": False, "message": f"Failed to insert planning record into Snowflake: {str(e)}"}
    finally:
        if conn:
            conn.close()

def update_planning_record(planning_id, data_dict):
    conn = None
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()

        planning_date = data_dict.get("planning_date") or datetime.date.today().strftime("%Y-%m-%d")
        region = data_dict.get("region", "")
        business_unit = data_dict.get("business_unit", "")
        product = data_dict.get("product", "")
        product_category = data_dict.get("product_category", "")

        try:
            planned_vol = float(data_dict.get("planned_volume", 0) or 0)
        except (ValueError, TypeError):
            planned_vol = 0.0

        try:
            actual_cons = float(data_dict.get("actual_consumption", 0) or 0)
        except (ValueError, TypeError):
            actual_cons = 0.0

        plan_variance = planned_vol - actual_cons
        forecast_acc = ((1 - abs(plan_variance) / planned_vol) * 100) if planned_vol > 0 else 0.0
        status = data_dict.get("status", "Active")

        table_name = os.getenv("SNOWFLAKE_PLANNING_TABLE", "PLANNING_DATA")
        query = f"""
            UPDATE {table_name} SET
                PLANNING_DATE = %s,
                REGION = %s,
                BUSINESS_UNIT = %s,
                PRODUCT = %s,
                PRODUCT_CATEGORY = %s,
                PLANNED_VOLUME = %s,
                ACTUAL_CONSUMPTION = %s,
                FORECAST_ACCURACY = %s,
                PLAN_VARIANCE = %s,
                STATUS = %s,
                IS_MANUALLY_EDITED = TRUE,
                LAST_MODIFIED_AT = CURRENT_TIMESTAMP()
            WHERE PLANNING_ID = %s;
        """
        cur.execute(query, (planning_date, region, business_unit, product, product_category, planned_vol, actual_cons, forecast_acc, plan_variance, status, planning_id))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' updated successfully in Snowflake."}
    except Exception as e:
        return {"success": False, "message": f"Failed to update planning record in Snowflake: {str(e)}"}
    finally:
        if conn:
            conn.close()

def delete_planning_record(planning_id):
    conn = None
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()

        table_name = os.getenv("SNOWFLAKE_PLANNING_TABLE", "PLANNING_DATA")
        cur.execute(f"DELETE FROM {table_name} WHERE PLANNING_ID = %s;", (planning_id,))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' deleted successfully from Snowflake."}
    except Exception as e:
        return {"success": False, "message": f"Failed to delete planning record from Snowflake: {str(e)}"}
    finally:
        if conn:
            conn.close()

def fetch_dashboard_data():
    conn = None
    try:
        conn = get_snowflake_connection()
        
        tbl_plan = os.getenv("SNOWFLAKE_PLANNING_TABLE", "PLANNING_DATA")
        tbl_cons = os.getenv("SNOWFLAKE_CONSUMPTION_TABLE", "CONSUMPTION_DATA")
        tbl_ship = os.getenv("SNOWFLAKE_SHIPMENT_TABLE", "SHIPMENT_DATA")

        try:
            planning_df = pd.read_sql_query(f"SELECT * FROM {tbl_plan};", conn)
            planning_df.columns = [c.lower() for c in planning_df.columns]
        except Exception:
            planning_df = pd.DataFrame()

        try:
            consumption_df = pd.read_sql_query(f"SELECT * FROM {tbl_cons};", conn)
            consumption_df.columns = [c.lower() for c in consumption_df.columns]
        except Exception:
            consumption_df = pd.DataFrame()

        try:
            shipment_df = pd.read_sql_query(f"SELECT * FROM {tbl_ship};", conn)
            shipment_df.columns = [c.lower() for c in shipment_df.columns]
        except Exception:
            shipment_df = pd.DataFrame()

        total_planning_records = len(planning_df)
        total_consumption = float(consumption_df['consumption_volume'].sum()) if not consumption_df.empty and 'consumption_volume' in consumption_df.columns else 0.0
        total_shipments = float(shipment_df['actual_shipment_volume'].sum()) if not shipment_df.empty and 'actual_shipment_volume' in shipment_df.columns else 0.0

        planned_vol = float(planning_df['planned_volume'].sum()) if not planning_df.empty and 'planned_volume' in planning_df.columns else 0.0
        actual_cons = float(planning_df['actual_consumption'].sum()) if not planning_df.empty and 'actual_consumption' in planning_df.columns else 0.0
        variance = planned_vol - actual_cons

        kpis = {
            "total_planning_records": total_planning_records,
            "total_consumption": total_consumption,
            "total_shipments": total_shipments,
            "planned_volume": planned_vol,
            "actual_volume": actual_cons,
            "variance": variance
        }

        return {
            "has_data": not (planning_df.empty and consumption_df.empty and shipment_df.empty),
            "kpis": kpis,
            "planning_df": planning_df,
            "consumption_df": consumption_df,
            "shipment_df": shipment_df
        }
    except Exception as e:
        return {
            "has_data": False,
            "kpis": {
                "total_planning_records": 0,
                "total_consumption": 0.0,
                "total_shipments": 0.0,
                "planned_volume": 0.0,
                "actual_volume": 0.0,
                "variance": 0.0
            },
            "planning_df": pd.DataFrame(),
            "consumption_df": pd.DataFrame(),
            "shipment_df": pd.DataFrame(),
            "error": str(e)
        }
    finally:
        if conn:
            conn.close()

def get_last_sync_info():
    conn = None
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM SYNC_LOGS ORDER BY ID DESC LIMIT 1;")
        row = cur.fetchone()
        if row:
            cols = [desc[0].lower() for desc in cur.description]
            row_dict = dict(zip(cols, row))
            cur.close()
            return row_dict
        cur.close()
        return None
    except Exception:
        return None
    finally:
        if conn:
            conn.close()
