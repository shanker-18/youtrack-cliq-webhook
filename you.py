import os
import uuid
import datetime
import warnings
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

warnings.filterwarnings('ignore', category=UserWarning)

load_dotenv()

def get_postgres_connection():
    load_dotenv(override=True)
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DATABASE", "kenvue_ibp")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    if not database or not user:
        raise ValueError("PostgreSQL environment variables (POSTGRES_DATABASE, POSTGRES_USER) must be set.")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password
    )
    return conn

def initialize_database():
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS planning_data (
                planning_id VARCHAR(50) PRIMARY KEY,
                planning_date DATE,
                region VARCHAR(100),
                business_unit VARCHAR(100),
                product VARCHAR(150),
                product_category VARCHAR(100),
                planned_volume NUMERIC(18,2),
                actual_consumption NUMERIC(18,2),
                forecast_accuracy NUMERIC(5,2),
                plan_variance NUMERIC(10,2),
                status VARCHAR(50),
                created_at TIMESTAMP,
                data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
                is_manually_edited BOOLEAN DEFAULT FALSE,
                last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS consumption_data (
                consumption_id VARCHAR(50) PRIMARY KEY,
                consumption_date DATE,
                region VARCHAR(100),
                business_unit VARCHAR(100),
                product VARCHAR(150),
                product_category VARCHAR(100),
                consumption_volume NUMERIC(18,2),
                previous_month_volume NUMERIC(18,2),
                consumption_growth NUMERIC(10,2),
                status VARCHAR(50),
                created_at TIMESTAMP,
                data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
                is_manually_edited BOOLEAN DEFAULT FALSE,
                last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS shipment_data (
                shipment_id VARCHAR(50) PRIMARY KEY,
                shipment_date DATE,
                region VARCHAR(100),
                business_unit VARCHAR(100),
                product VARCHAR(150),
                product_category VARCHAR(100),
                planned_shipment_volume NUMERIC(18,2),
                actual_shipment_volume NUMERIC(18,2),
                fulfillment_rate NUMERIC(5,2),
                shipment_status VARCHAR(50),
                created_at TIMESTAMP,
                data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
                is_manually_edited BOOLEAN DEFAULT FALSE,
                last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_logs (
                id SERIAL PRIMARY KEY,
                sync_started_at TIMESTAMP,
                sync_completed_at TIMESTAMP,
                status VARCHAR(50),
                planning_records_synced INTEGER DEFAULT 0,
                consumption_records_synced INTEGER DEFAULT 0,
                shipment_records_synced INTEGER DEFAULT 0,
                error_message TEXT
            );
        """)

        conn.commit()
        cur.close()
        return {"success": True, "message": "PostgreSQL database initialized successfully."}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"PostgreSQL initialization failed: {str(e)}"}
    finally:
        if conn:
            conn.close()

def fetch_planning_data():
    conn = None
    try:
        conn = get_postgres_connection()
        query = "SELECT * FROM planning_data ORDER BY planning_date DESC, product ASC;"
        df = pd.read_sql_query(query, conn)
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
        conn = get_postgres_connection()
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

        query = """
            INSERT INTO planning_data (
                planning_id, planning_date, region, business_unit, product, product_category,
                planned_volume, actual_consumption, forecast_accuracy, plan_variance, status,
                created_at, data_source, is_manually_edited, last_modified_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'MANUAL_PLANNING', TRUE, CURRENT_TIMESTAMP);
        """
        cur.execute(query, (planning_id, planning_date, region, business_unit, product, product_category, planned_vol, actual_cons, forecast_acc, plan_variance, status))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' inserted successfully.", "id": planning_id}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"Failed to insert planning record: {str(e)}"}
    finally:
        if conn:
            conn.close()

def update_planning_record(planning_id, data_dict):
    conn = None
    try:
        conn = get_postgres_connection()
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

        query = """
            UPDATE planning_data SET
                planning_date = %s,
                region = %s,
                business_unit = %s,
                product = %s,
                product_category = %s,
                planned_volume = %s,
                actual_consumption = %s,
                forecast_accuracy = %s,
                plan_variance = %s,
                status = %s,
                is_manually_edited = TRUE,
                last_modified_at = CURRENT_TIMESTAMP
            WHERE planning_id = %s;
        """
        cur.execute(query, (planning_date, region, business_unit, product, product_category, planned_vol, actual_cons, forecast_acc, plan_variance, status, planning_id))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' updated successfully."}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"Failed to update planning record: {str(e)}"}
    finally:
        if conn:
            conn.close()

def delete_planning_record(planning_id):
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM planning_data WHERE planning_id = %s;", (planning_id,))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' deleted successfully."}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"Failed to delete planning record: {str(e)}"}
    finally:
        if conn:
            conn.close()

def fetch_dashboard_data():
    conn = None
    try:
        conn = get_postgres_connection()
        
        try:
            planning_df = pd.read_sql_query("SELECT * FROM planning_data;", conn)
        except Exception:
            planning_df = pd.DataFrame()

        try:
            consumption_df = pd.read_sql_query("SELECT * FROM consumption_data;", conn)
        except Exception:
            consumption_df = pd.DataFrame()

        try:
            shipment_df = pd.read_sql_query("SELECT * FROM shipment_data;", conn)
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
        conn = get_postgres_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM sync_logs ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        if conn:
            conn.close()
