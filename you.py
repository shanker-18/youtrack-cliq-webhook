    cache_key = f"{domain}:{snapshot_id}:{building_block_id}:{model_id}:{year}:{is_editable}:{plan_type}:{is_historical}:{is_demand}"

    if _is_duplicate_refresh(cache_key):
        return (no_update, no_update, no_update, no_update, no_update, no_update)

    # If cached and not explicitly bypassed by a fresh mutation event
    is_mutation_refresh = isinstance(refresh_trigger, dict) and bool(refresh_trigger.get("trigger"))
