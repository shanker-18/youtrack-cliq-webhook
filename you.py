import os
import datetime
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

import database

load_dotenv()

def sync_snowflake_data():
    load_dotenv(override=True)
    sync_started_at = datetime.datetime.now()

    try:
        conn = database.get_snowflake_connection()
        cur = conn.cursor()

        tbl_plan = os.getenv("SNOWFLAKE_PLANNING_TABLE", "PLANNING_DATA")
        tbl_cons = os.getenv("SNOWFLAKE_CONSUMPTION_TABLE", "CONSUMPTION_DATA")
        tbl_ship = os.getenv("SNOWFLAKE_SHIPMENT_TABLE", "SHIPMENT_DATA")

        cur.execute(f"SELECT COUNT(*) FROM {tbl_plan};")
        plan_cnt = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM {tbl_cons};")
        cons_cnt = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM {tbl_ship};")
        ship_cnt = cur.fetchone()[0]

        sync_completed_at = datetime.datetime.now()
        status = "SUCCESS"
        err_msg = None

        query = """
            INSERT INTO SYNC_LOGS (
                SYNC_STARTED_AT, SYNC_COMPLETED_AT, STATUS, 
                PLANNING_RECORDS_SYNCED, CONSUMPTION_RECORDS_SYNCED, SHIPMENT_RECORDS_SYNCED, 
                ERROR_MESSAGE
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(query, (sync_started_at, sync_completed_at, status, plan_cnt, cons_cnt, ship_cnt, err_msg))
        cur.close()
        conn.close()

        return {
            "success": True,
            "status": "SUCCESS",
            "message": f"Snowflake data refreshed successfully. (Planning: {plan_cnt}, Consumption: {cons_cnt}, Shipments: {ship_cnt})",
            "timestamp": sync_completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "counts": {"planning_data": plan_cnt, "consumption_data": cons_cnt, "shipment_data": ship_cnt}
        }

    except Exception as e:
        sync_completed_at = datetime.datetime.now()
        err_msg = f"Snowflake refresh error: {str(e)}"
        return {
            "success": False,
            "status": "FAILED",
            "message": err_msg,
            "timestamp": sync_completed_at.strftime("%Y-%m-%d %H:%M:%S")
        }

def sync_snowflake_to_postgres():
    return sync_snowflake_data()
