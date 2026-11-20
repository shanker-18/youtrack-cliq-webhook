# ─── Snowflake Warehouse Pre-Warming ─────────────────────────────────────────
# Establish Snowflake connection at startup so the warehouse is awake
# before any user hits Summary or Validation dashboards.
try:
    import threading as _sf_threading
    from services.validation_service import get_snowflake_connection

    def _warm_snowflake():
        try:
            conn = get_snowflake_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except Exception:
            pass

    _sf_thread = _sf_threading.Thread(target=_warm_snowflake, daemon=True)
    _sf_thread.start()
    logger.info("Snowflake warehouse pre-warm initiated")
except Exception as _sf_init_err:
    logger.warning("Snowflake will be initialized on first request: %s", _sf_init_err)
