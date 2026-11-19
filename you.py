def _get_or_compute_summary_matrix(
    domain: str, clean_models: list[str], cache_key: str
) -> tuple[dict[str, Any], bool]:
    """Retrieve matrix data from server cache or compute and store."""
    cached = summary_cache.get(cache_key)
    if cached is not None:
        return cached, True

    matrix_data = _compute_summary_matrix_for_domain(domain, clean_models)
    summary_cache.set(cache_key, matrix_data)
    return matrix_data, False
