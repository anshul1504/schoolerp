import os

from .base import *

DEBUG = False
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Production safety: require a real secret key and explicit allowed hosts.
if SECRET_KEY == "dev-unsafe-secret-key":
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")
if not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production.")

# Secure-by-default cookies/headers in production.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "true").lower() in {"1", "true", "yes"}
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "true").lower() in {"1", "true", "yes"}
