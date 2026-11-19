_LAST_CONTEXT_FINGERPRINT: Dict[str, Any] = {"key": None, "ts": 0.0}


def _is_duplicate_refresh(cache_key: str, debounce_ms: float = 150.0) -> bool:
    """Return True if the same context was processed within debounce_ms."""
    now = time.time()
    if (_LAST_CONTEXT_FINGERPRINT["key"] == cache_key
            and (now - _LAST_CONTEXT_FINGERPRINT["ts"]) * 1000 < debounce_ms):
        return True
    _LAST_CONTEXT_FINGERPRINT["key"] = cache_key
    _LAST_CONTEXT_FINGERPRINT["ts"] = now
    return False
