"""File-based cache with configurable TTL. Stores JSON blobs keyed by MD5 hash or string key."""

import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TTL_HOURS = float(os.getenv("RESEARCH_DIGEST_CACHE_TTL_HOURS", 24))


def _cache_path(key: str) -> Path:
    safe_key = key.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"{safe_key}.json"


def cache_get(key: str, ttl_hours: float | None = None) -> dict | None:
    """Return cached value if it exists and is within TTL, else None."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
        cached_at = datetime.fromisoformat(blob["_cached_at"])
        effective_ttl = ttl_hours if ttl_hours is not None else TTL_HOURS
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours > effective_ttl:
            return None
        return blob
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def cache_set(key: str, data: dict) -> None:
    """Write data to cache with current timestamp."""
    path = _cache_path(key)
    data["_cached_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def cache_get_force(key: str) -> dict | None:
    """Return cached value regardless of TTL (fallback when source is unavailable)."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return None


def cache_clear(key: str | None = None) -> None:
    """Clear a specific cache entry or all entries if key is None."""
    if key:
        path = _cache_path(key)
        if path.exists():
            path.unlink()
    else:
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()


def cache_age_str(key: str) -> str:
    """Return human-readable cache age string, e.g. 'Cached 3h ago'."""
    path = _cache_path(key)
    if not path.exists():
        return "No cache"
    try:
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
        cached_at = datetime.fromisoformat(blob["_cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < 1:
            mins = int(age_hours * 60)
            return f"Cached {mins}m ago"
        return f"Cached {age_hours:.1f}h ago"
    except Exception:
        return "Unknown age"


def make_digest_key(title: str, abstract: str) -> str:
    """Generate a stable cache key for a per-article Claude digest."""
    payload = title + abstract[:500]
    return "digest_" + hashlib.md5(payload.encode()).hexdigest()
