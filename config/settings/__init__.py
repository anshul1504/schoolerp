import os

env = (os.getenv("DJANGO_ENV") or "dev").strip().lower()
if env in {"prod", "production"}:
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
