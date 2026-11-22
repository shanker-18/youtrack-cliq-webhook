# ─── Snowflake & Summary Cache Keep-Alive ────────────────────────────────────
try:
    import threading as _sf_threading
    from services.validation_service import get_snowflake_connection

    def _snowflake_keep_alive():
        import time as _time
        # Warm Snowflake warehouse
        try:
            conn = get_snowflake_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            logger.info("Snowflake warehouse warmed up")
        except Exception:
            pass
        # Pre-compute default summary cache on startup
        try:
            from services.summary_calculations import compute_consumption_summary_matrix
            compute_consumption_summary_matrix(["Children's Motrin"])
            logger.info("Default summary cache pre-warmed at startup")
        except Exception:
            pass
        # Keep-alive loop
        while True:
            _time.sleep(300)
            try:
                conn = get_snowflake_connection()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
            except Exception:
                pass

    _sf_thread = _sf_threading.Thread(target=_snowflake_keep_alive, daemon=True)
    _sf_thread.start()
    logger.info("Snowflake keep-alive thread started")
except Exception as _sf_init_err:
    logger.warning("Keep-alive could not start: %s", _sf_init_err)
