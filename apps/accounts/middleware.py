from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone


class IdleLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            idle_seconds = getattr(request, "IDLE_TIMEOUT_SECONDS", None)
            if idle_seconds is None:
                try:
                    from django.conf import settings

                    idle_seconds = int(getattr(settings, "IDLE_TIMEOUT_SECONDS", 0))
                except Exception:
                    idle_seconds = 0

            if idle_seconds and request.method == "GET":
                last = request.session.get("last_activity_at")
                now = timezone.now().timestamp()
                if last and (now - float(last)) > float(idle_seconds):
                    logout(request)
                    messages.info(request, "Logged out due to inactivity.")
                    return redirect("login")
                request.session["last_activity_at"] = now

        return self.get_response(request)
