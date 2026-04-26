import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    # Safe fallback for local dev only. In production, you must set DJANGO_SECRET_KEY.
    SECRET_KEY = "dev-unsafe-secret-key"

DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
ENABLE_DEMO_PAGES = os.getenv("ENABLE_DEMO_PAGES", "false").lower() in {"1", "true", "yes"}

# SSO (Google OIDC)
GOOGLE_OIDC_CLIENT_ID = os.getenv("GOOGLE_OIDC_CLIENT_ID", "")
GOOGLE_OIDC_CLIENT_SECRET = os.getenv("GOOGLE_OIDC_CLIENT_SECRET", "")
GOOGLE_OIDC_REDIRECT_URI = os.getenv("GOOGLE_OIDC_REDIRECT_URI", "")
GOOGLE_OIDC_ENABLED = bool(GOOGLE_OIDC_CLIENT_ID and GOOGLE_OIDC_CLIENT_SECRET and GOOGLE_OIDC_REDIRECT_URI)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts.apps.AccountsConfig",
    "apps.schools.apps.SchoolsConfig",
    "apps.admissions.apps.AdmissionsConfig",
    "apps.students.apps.StudentsConfig",
    "apps.staff.apps.StaffConfig",
    "apps.academics.apps.AcademicsConfig",
    "apps.attendance.apps.AttendanceConfig",
    "apps.fees.apps.FeesConfig",
    "apps.exams.apps.ExamsConfig",
    "apps.communication.apps.CommunicationConfig",
    "apps.frontoffice.apps.FrontofficeConfig",
    "apps.core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.accounts.middleware.IdleLogoutMiddleware",
    "apps.schools.middleware.SubscriptionEnforcementMiddleware",
    "apps.core.middleware.ActivityLogMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.platform_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Session / auto logout
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(12 * 60 * 60)))
SESSION_SAVE_EVERY_REQUEST = os.getenv("SESSION_SAVE_EVERY_REQUEST", "true").lower() in {"1", "true", "yes"}
IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", str(30 * 60)))

# 2FA (Email OTP) for all roles
EMAIL_OTP_2FA_ENABLED = os.getenv("EMAIL_OTP_2FA_ENABLED", "false").lower() in {"1", "true", "yes"}

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email (SMTP)
# Set these env vars locally / on server:
# - EMAIL_HOST_PASSWORD (required to send mail)
# - EMAIL_HOST_USER (optional override; defaults to noreply@thewebfix.in)
# - DEFAULT_FROM_EMAIL (optional)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "mail.thewebfix.in")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "true").lower() in {"1", "true", "yes"}
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() in {"1", "true", "yes"}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "noreply@thewebfix.in")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Security (recommended for production)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() in {"1", "true", "yes"}
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() in {"1", "true", "yes"}
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "false").lower() in {"1", "true", "yes"}

# Billing webhook hardening
BILLING_WEBHOOK_REQUIRE_SIGNATURE = os.getenv("BILLING_WEBHOOK_REQUIRE_SIGNATURE", "true").lower() in {"1", "true", "yes"}
BILLING_WEBHOOK_MAX_SKEW_SECONDS = int(os.getenv("BILLING_WEBHOOK_MAX_SKEW_SECONDS", "300"))
BILLING_WEBHOOK_REPLAY_TTL_SECONDS = int(os.getenv("BILLING_WEBHOOK_REPLAY_TTL_SECONDS", "600"))
BILLING_WEBHOOK_SECRET = os.getenv("BILLING_WEBHOOK_SECRET", "")

# Optional strict production guardrails.
# Enable with ENFORCE_PROD_SECURITY=true in production to fail fast on unsafe config.
ENFORCE_PROD_SECURITY = os.getenv("ENFORCE_PROD_SECURITY", "false").lower() in {"1", "true", "yes"}
if ENFORCE_PROD_SECURITY and not DEBUG:
    prod_errors = []
    if SECRET_KEY == "dev-unsafe-secret-key":
        prod_errors.append("DJANGO_SECRET_KEY must be set (dev fallback is not allowed).")
    if not ALLOWED_HOSTS:
        prod_errors.append("DJANGO_ALLOWED_HOSTS must include production hostnames.")
    if not SESSION_COOKIE_SECURE:
        prod_errors.append("SESSION_COOKIE_SECURE must be true.")
    if not CSRF_COOKIE_SECURE:
        prod_errors.append("CSRF_COOKIE_SECURE must be true.")
    if not SECURE_SSL_REDIRECT:
        prod_errors.append("SECURE_SSL_REDIRECT must be true.")
    if prod_errors:
        raise RuntimeError("Production security guardrails failed: " + " | ".join(prod_errors))
