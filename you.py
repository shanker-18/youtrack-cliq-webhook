def clear_summary_cache() -> None:
    """Clears the server-side summary cache and triggers background re-computation."""
    import threading
    stale_keys = list(_SUM_SNOWFLAKE_CACHE.keys())
    _SUM_SNOWFLAKE_CACHE.clear()
    _SUM_SNOWFLAKE_CACHE_TS.clear()

    def _recompute():
        for key in stale_keys:
            try:
                parts = key.split(":")
                domain = parts[0].lower() if parts else "consumption"
                models_str = parts[-1] if len(parts) >= 2 else ""
                models = [m.strip() for m in models_str.split(",") if m.strip()]
                if models:
                    matrix = _compute_summary_matrix_for_domain(domain, models)
                    _SUM_SNOWFLAKE_CACHE[key] = matrix
                    _SUM_SNOWFLAKE_CACHE_TS[key] = time.monotonic()
            except Exception:
                pass

    threading.Thread(target=_recompute, daemon=True).start()
