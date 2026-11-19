def _get_mutation_year_idx(refresh_trigger: Any) -> Optional[int]:
    """Extract which year (1 or 2) was mutated, or None if full refresh needed."""
    if not isinstance(refresh_trigger, dict):
        return None
    if refresh_trigger.get("trigger") not in ("cell_edit",):
        return None
    return refresh_trigger.get("year_idx")
