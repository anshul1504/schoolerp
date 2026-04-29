from django.shortcuts import render

from apps.core.permissions import permission_required, role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context

from .models import Driver, Route, TransportAllocation, Vehicle


@role_required(
    "SUPER_ADMIN",
    "SCHOOL_OWNER",
    "ADMIN",
    "PRINCIPAL",
    "TRANSPORT_MANAGER",
    "STAFF",
    "STUDENT",
    "PARENT",
)
@permission_required("transport.view")
def transport_overview(request):
    school, error_redirect = get_selected_school_or_redirect(request, "transport")
    if error_redirect:
        return error_redirect

    drivers = Driver.objects.filter(school=school)
    vehicles = Vehicle.objects.filter(school=school)
    routes = Route.objects.filter(school=school)
    allocations = TransportAllocation.objects.filter(route__school=school)

    context = build_layout_context(request.user, current_section="transport")
    context.update(
        {
            "school": school,
            "drivers": drivers,
            "vehicles": vehicles,
            "routes": routes,
            "allocations": allocations,
        }
    )
    return render(request, "transport/overview.html", context)
