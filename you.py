import os
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
    database = os.getenv("SNOWFLAKE_DATABASE", "CONSUMPTION_VALIDATION_DB")
    schema = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
    role = os.getenv("SNOWFLAKE_ROLE")

    if not account or not user or not password:
        raise ValueError("Snowflake environment variables (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD) must be set.")

    return snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
        autocommit=True
    )

def fetch_joined_snowflake_data(
    brand=None,
    category=None,
    retailer=None,
    business_segment=None,
    channel=None,
    region=None
):
    """
    STRICTLY READ-ONLY Snowflake Query.
    Reads from CONSUMPTION_VALIDATION_DB.PUBLIC:
    - POS_DATA (p)
    - GMC_PRODUCT_HIERARCHY (g)
    - SHIPMENT_DATA (s)
    """
    conn = None
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute("USE DATABASE CONSUMPTION_VALIDATION_DB;")
        cur.execute("USE SCHEMA PUBLIC;")

        query = """
        SELECT
            p.ID AS POS_ID,
            p.GLOBAL_DATE_SHORT_DESC,
            p.RETAILER,
            p.CHANNEL,
            p.BRAND AS POS_BRAND,
            p.CATEGORY AS POS_CATEGORY,
            p.SUB_CATEGORY AS POS_SUB_CATEGORY,
            p.BUSINESS_SEGMENT AS POS_BUSINESS_SEGMENT,
            p.LOCAL_UPC,
            p.GLOBAL_PRODUCT_SKU,
            p.GLOBAL_VALUE_LC AS POS_VALUE,
            p.GLOBAL_UNIT_TDP AS POS_UNITS,

            g.GMC_SKU,
            g.GMC_SKU_NAME,
            g.UPC AS GMC_UPC,
            g.GMC_DESCRIPTION,
            g.BRAND AS GMC_BRAND,
            g.CATEGORY AS GMC_CATEGORY,
            g.BUSINESS_SEGMENT AS GMC_BUSINESS_SEGMENT,
            g.REGION AS GMC_REGION,

            s.ITM_ID,
            s.KV_ITEM_NO,
            s.ITM_UPC,
            s.GROSS_SHIPMENT_AM,
            s.RETURN_SHIP_AM,
            s.GROSS_QTY_CASE,
            s.RETURN_QTY_CASE,
            s.GROSS_QTY_CU,
            s.RETURN_QTY_CU

        FROM POS_DATA p
        LEFT JOIN GMC_PRODUCT_HIERARCHY g ON p.LOCAL_UPC = g.UPC
        LEFT JOIN SHIPMENT_DATA s ON p.LOCAL_UPC = s.ITM_UPC
        WHERE 1=1
        """

        params = []
        if brand and brand != "All":
            query += " AND (p.BRAND = %s OR g.BRAND = %s)"
            params.extend([brand, brand])
        if category and category != "All":
            query += " AND (p.CATEGORY = %s OR g.CATEGORY = %s)"
            params.extend([category, category])
        if retailer and retailer != "All":
            query += " AND p.RETAILER = %s"
            params.append(retailer)
        if business_segment and business_segment != "All":
            query += " AND (p.BUSINESS_SEGMENT = %s OR g.BUSINESS_SEGMENT = %s)"
            params.extend([business_segment, business_segment])
        if channel and channel != "All":
            query += " AND p.CHANNEL = %s"
            params.append(channel)
        if region and region != "All":
            query += " AND g.REGION = %s"
            params.append(region)

        query += " ORDER BY p.GLOBAL_DATE_SHORT_DESC ASC, p.ID ASC;"

        df = pd.read_sql_query(query, conn, params=params) if params else pd.read_sql_query(query, conn)
        df.columns = [c.upper() for c in df.columns]
        return df

    except Exception as e:
        print(f"Error reading Snowflake data: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_filter_options():
    conn = None
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute("USE DATABASE CONSUMPTION_VALIDATION_DB;")
        cur.execute("USE SCHEMA PUBLIC;")

        brands = pd.read_sql_query("SELECT DISTINCT BRAND FROM POS_DATA WHERE BRAND IS NOT NULL UNION SELECT DISTINCT BRAND FROM GMC_PRODUCT_HIERARCHY WHERE BRAND IS NOT NULL;", conn)['BRAND'].tolist()
        categories = pd.read_sql_query("SELECT DISTINCT CATEGORY FROM POS_DATA WHERE CATEGORY IS NOT NULL UNION SELECT DISTINCT CATEGORY FROM GMC_PRODUCT_HIERARCHY WHERE CATEGORY IS NOT NULL;", conn)['CATEGORY'].tolist()
        retailers = pd.read_sql_query("SELECT DISTINCT RETAILER FROM POS_DATA WHERE RETAILER IS NOT NULL;", conn)['RETAILER'].tolist()
        segments = pd.read_sql_query("SELECT DISTINCT BUSINESS_SEGMENT FROM POS_DATA WHERE BUSINESS_SEGMENT IS NOT NULL;", conn)['BUSINESS_SEGMENT'].tolist()

        return {
            "brands": ["All"] + sorted([str(b) for b in brands if b]),
            "categories": ["All"] + sorted([str(c) for c in categories if c]),
            "retailers": ["All"] + sorted([str(r) for r in retailers if r]),
            "segments": ["All"] + sorted([str(s) for s in segments if s]),
        }
    except Exception as e:
        print(f"Error fetching options: {e}")
        return {"brands": ["All"], "categories": ["All"], "retailers": ["All"], "segments": ["All"]}
    finally:
        if conn:
            conn.close()
