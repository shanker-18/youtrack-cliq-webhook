    for attempt in range(1, 3):
        try:
            conn = get_snowflake_connection(force_new=(attempt > 1))
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            cur.close()
            gts_base, gts_plan_actual = _aggregate_snowflake_gts_months(rows, base_year, plan_year)
            break
        except Exception as e:
            if attempt < 2 and is_token_expired_error(e):
                logger.warning("Snowflake GTS cold start retry: %s", e)
                continue
            logger.exception("Snowflake shipment GTS query error: %s", e)
