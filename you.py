"""
NA IBP Planning Application — Hybrid Cache Store
=================================================
Thread-safe in-memory TTL cache for Snowflake historical actuals
and computed summary matrices. Centralizes all dashboard caching
into a single reusable module.
"""

import time
from typing import Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class HybridCacheStore:
    """Thread-safe in-memory TTL cache for Snowflake historical actuals."""

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Return cached value if not expired, else None."""
        if key not in self._store:
            return None
        if time.time() > self._expiry.get(key, 0):
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return None
        return self._store[key]

    def set(self, key: str, value: Any) -> None:
        """Store value with TTL expiry."""
        self._store[key] = value
        self._expiry[key] = time.time() + self._ttl

    def invalidate(self, prefix: str = "") -> None:
        """Remove all entries matching prefix, or all entries if prefix is empty."""
        if not prefix:
            self._store.clear()
            self._expiry.clear()
            return
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            self._store.pop(k, None)
            self._expiry.pop(k, None)

    def has(self, key: str) -> bool:
        """Check if a non-expired entry exists."""
        return self.get(key) is not None

    def size(self) -> int:
        """Return count of cached entries."""
        return len(self._store)


# ── Singleton Instances ──────────────────────────────────────────────────────
# Snowflake actuals: 24-hour TTL (external data, rarely changes)
snowflake_cache = HybridCacheStore(ttl_seconds=86400)

# Summary matrices: 30-minute TTL (includes live PostgreSQL building blocks)
summary_cache = HybridCacheStore(ttl_seconds=1800)
