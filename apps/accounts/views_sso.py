import json
import secrets
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _is_enabled() -> bool:
    return bool(getattr(settings, "GOOGLE_OIDC_ENABLED", False))


def sso_google_start(request):
    if not _is_enabled():
        messages.error(request, "Google SSO is not configured.")
        return redirect("login")

    state = secrets.token_urlsafe(24)
    request.session["google_oidc_state"] = state
    request.session.set_expiry(10 * 60)

    params = {
        "client_id": settings.GOOGLE_OIDC_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OIDC_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    uri = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(uri)


def sso_google_callback(request):
    if not _is_enabled():
        messages.error(request, "Google SSO is not configured.")
        return redirect("login")

    state = (request.GET.get("state") or "").strip()
    code = (request.GET.get("code") or "").strip()
    if not code:
        messages.error(request, "SSO callback missing code.")
        return redirect("login")

    expected = request.session.get("google_oidc_state")
    if not expected or state != expected:
        messages.error(request, "SSO session invalid. Please try again.")
        return redirect("login")

    try:
        token_req = {
            "client_id": settings.GOOGLE_OIDC_CLIENT_ID,
            "client_secret": settings.GOOGLE_OIDC_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_OIDC_REDIRECT_URI,
        }
        req = urllib.request.Request(
            GOOGLE_TOKEN_URL,
            data=urllib.parse.urlencode(token_req).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            token = json.loads(resp.read().decode("utf-8"))
        access_token = str(token.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("missing access_token")

        userinfo_req = urllib.request.Request(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        with urllib.request.urlopen(userinfo_req, timeout=10) as resp2:
            userinfo = json.loads(resp2.read().decode("utf-8"))
    except Exception:
        messages.error(request, "Google SSO failed. Contact administrator.")
        return redirect("login")

    email = str(userinfo.get("email") or "").strip().lower()
    if not email:
        messages.error(request, "Google account has no email.")
        return redirect("login")

    User = get_user_model()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        messages.error(request, "No active ERP user found for this Google account email.")
        return redirect("login")

    login(request, user)
    request.session.pop("google_oidc_state", None)
    request.session.set_expiry(12 * 60 * 60)
    return redirect("dashboard")
