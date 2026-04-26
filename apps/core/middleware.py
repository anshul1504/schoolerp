from django.utils.deprecation import MiddlewareMixin

from apps.core.models import ActivityLog
from apps.core.request_context import clear_current_request, set_current_request


class ActivityLogMiddleware(MiddlewareMixin):
    LOG_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def process_request(self, request):
        set_current_request(request)

    def process_response(self, request, response):
        try:
            user = getattr(request, "user", None)
            if not user or not getattr(user, "is_authenticated", False):
                return response

            if request.method not in self.LOG_METHODS:
                return response

            view_name = ""
            try:
                match = getattr(request, "resolver_match", None)
                view_name = getattr(match, "view_name", "") or ""
            except Exception:
                view_name = ""

            ActivityLog.objects.create(
                actor=user,
                school_id=getattr(user, "school_id", None),
                view_name=view_name,
                action=f"{request.method} {request.path}",
                method=request.method,
                path=request.path[:255],
                status_code=getattr(response, "status_code", None),
                ip_address=(request.META.get("REMOTE_ADDR") or "")[:64],
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:5000],
            )
            return response
        except Exception:
            # Never break requests because of logging.
            return response
        finally:
            clear_current_request()
