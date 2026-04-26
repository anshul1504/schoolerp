from __future__ import annotations

import threading


_local = threading.local()


def set_current_request(request) -> None:
    _local.request = request


def get_current_request():
    return getattr(_local, "request", None)


def clear_current_request() -> None:
    if hasattr(_local, "request"):
        delattr(_local, "request")

