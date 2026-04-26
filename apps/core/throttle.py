from django.core.cache import cache


def throttle_hit(key: str, *, limit: int, window_seconds: int) -> bool:
    """
    Cache-based throttle.

    Returns True if the caller has exceeded the limit in the current window.
    """
    try:
        current = int(cache.get(key, 0))
    except Exception:
        current = 0
    current += 1
    cache.set(key, current, timeout=window_seconds)
    return current > limit

