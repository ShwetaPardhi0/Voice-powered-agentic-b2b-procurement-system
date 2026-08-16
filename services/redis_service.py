"""
services/redis_service.py
-------------------------
Redis Cache Service for transient PO status caching and Slack message timestamp tracking.
PostgreSQL remains the single authoritative source of truth.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    import redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True,
        socket_timeout=1.0,
        socket_connect_timeout=1.0,
    )
except Exception as e:
    redis_client = None
    print(f"[Redis Warning] Failed to initialize Redis client: {e}")


def is_redis_available() -> bool:
    """Checks if Redis server is reachable."""
    if not redis_client:
        return False
    try:
        return redis_client.ping()
    except Exception:
        return False


def cache_po_state(po_id: str, po_data: dict, ttl: int = 86400):
    """Caches transient PO approval data in Redis (24-hour default TTL)."""
    if not is_redis_available():
        return
    try:
        key = f"po:{po_id}"
        redis_client.setex(key, ttl, json.dumps(po_data))
    except Exception as e:
        print(f"[Redis Cache Error] {e}")


def get_cached_po_state(po_id: str) -> dict | None:
    """Fetches cached PO data from Redis."""
    if not is_redis_available():
        return None
    try:
        raw = redis_client.get(f"po:{po_id}")
        return json.loads(raw) if raw else None
    except Exception as e:
        print(f"[Redis Cache Error] {e}")
        return None


def update_cached_po_status(po_id: str, status: str):
    """Updates PO status in Redis cache."""
    if not is_redis_available():
        return
    try:
        data = get_cached_po_state(po_id) or {}
        data["status"] = status
        cache_po_state(po_id, data)
    except Exception as e:
        print(f"[Redis Cache Error] {e}")
