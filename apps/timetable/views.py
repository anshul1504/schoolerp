from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.academics.models import AcademicClass
from apps.core.permissions import role_required
from apps.core.tenancy import selected_school_for_request
from apps.core.ui import build_layout_context

from .models import PeriodMaster, TimetableSlot


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "TEACHER", "STUDENT", "PARENT")
def timetable_overview(request):
    school = selected_school_for_request(request)
    if not school and request.user.school:
        school = request.user.school

    if not school:
        messages.error(request, "Please select a school to view timetable.")
        return redirect("dashboard")

    selected_class_id = request.GET.get("class_id")
    academic_classes = AcademicClass.objects.filter(school=school)

    periods = PeriodMaster.objects.filter(school=school).order_by("start_time")
    slots = []
    selected_class = None

    if selected_class_id:
        selected_class = get_object_or_404(AcademicClass, id=selected_class_id, school=school)
        slots = TimetableSlot.objects.filter(academic_class=selected_class).select_related(
            "period", "subject", "teacher"
        )

    context = build_layout_context(request.user, current_section="timetable")
    context.update(
        {
            "school": school,
            "academic_classes": academic_classes,
            "selected_class": selected_class,
            "periods": periods,
            "slots": slots,
            "days": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
        }
    )
    return render(request, "timetable/overview.html", context)
