from django.shortcuts import render

from apps.core.permissions import permission_required, role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context

from .models import Hostel, HostelAllocation, MessPlan


@role_required(
    "SUPER_ADMIN",
    "SCHOOL_OWNER",
    "ADMIN",
    "PRINCIPAL",
    "HOSTEL_MANAGER",
    "STAFF",
    "STUDENT",
    "PARENT",
)
@permission_required("hostel.view")
def hostel_overview(request):
    school, error_redirect = get_selected_school_or_redirect(request, "hostel")
    if error_redirect:
        return error_redirect

    hostels = Hostel.objects.filter(school=school)
    mess_plans = MessPlan.objects.filter(school=school)
    allocations = HostelAllocation.objects.filter(hostel__school=school)

    context = build_layout_context(request.user, current_section="hostel")
    context.update(
        {
            "school": school,
            "hostels": hostels,
            "mess_plans": mess_plans,
            "allocations": allocations,
        }
    )
    return render(request, "hostel/overview.html", context)
