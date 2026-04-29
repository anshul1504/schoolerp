from decimal import Decimal

from django.shortcuts import render

from apps.academics.models import AcademicClass
from apps.attendance.models import AttendanceSession, StudentAttendance
from apps.core.permissions import permission_required
from apps.core.tenancy import allowed_school_ids_for_user
from apps.core.ui import build_layout_context
from apps.exams.models import Exam, ExamMark
from apps.fees.models import FeePayment, StudentFeeLedger
from apps.schools.models import School
from apps.students.models import Student


def _school_ids_for_user(user) -> list[int] | None:
    if getattr(user, "role", None) == "SUPER_ADMIN":
        return None
    ids = allowed_school_ids_for_user(user)
    return ids


@permission_required("reports.view")
def reports_overview(request):
    school_ids = _school_ids_for_user(request.user)

    students = Student.objects.all()
    classes = AcademicClass.objects.all()
    attendance_sessions = AttendanceSession.objects.all()
    attendance_entries = StudentAttendance.objects.all()
    ledgers = StudentFeeLedger.objects.all()
    payments = FeePayment.objects.all()
    exams = Exam.objects.all()
    exam_marks = ExamMark.objects.all()
    schools = School.objects.filter(is_active=True)

    if school_ids is not None:
        if not school_ids:
            students = Student.objects.none()
            classes = AcademicClass.objects.none()
            attendance_sessions = AttendanceSession.objects.none()
            attendance_entries = StudentAttendance.objects.none()
            ledgers = StudentFeeLedger.objects.none()
            payments = FeePayment.objects.none()
            exams = Exam.objects.none()
            exam_marks = ExamMark.objects.none()
            schools = School.objects.none()
        else:
            students = students.filter(school_id__in=school_ids)
            classes = classes.filter(school_id__in=school_ids)
            attendance_sessions = attendance_sessions.filter(school_id__in=school_ids)
            attendance_entries = attendance_entries.filter(session__school_id__in=school_ids)
            ledgers = ledgers.filter(school_id__in=school_ids)
            payments = payments.filter(school_id__in=school_ids)
            exams = exams.filter(school_id__in=school_ids)
            exam_marks = exam_marks.filter(exam__school_id__in=school_ids)
            schools = schools.filter(id__in=school_ids)

    active_students = students.filter(is_active=True).count()
    total_students = students.count()
    attendance_present = attendance_entries.filter(status="PRESENT").count()
    attendance_total = attendance_entries.count()
    attendance_rate = int((attendance_present / attendance_total) * 100) if attendance_total else 0
    outstanding = sum(
        max((ledger.amount_due - ledger.amount_paid), Decimal("0")) for ledger in ledgers
    )

    metrics = [
        {"label": "Schools", "value": schools.count(), "copy": "Active school scope"},
        {"label": "Students", "value": total_students, "copy": f"{active_students} active records"},
        {
            "label": "Attendance",
            "value": f"{attendance_rate}%",
            "copy": f"{attendance_sessions.count()} marked sessions",
        },
        {
            "label": "Outstanding Fees",
            "value": f"Rs {outstanding}",
            "copy": f"{payments.count()} collections recorded",
        },
        {"label": "Exams", "value": exams.count(), "copy": f"{exam_marks.count()} marks entered"},
        {"label": "Classes", "value": classes.count(), "copy": "Academic structure configured"},
    ]

    panels = [
        {
            "title": "Students And Classes",
            "body": f"{total_students} students are mapped across {classes.count()} academic class records.",
        },
        {
            "title": "Attendance Health",
            "body": f"{attendance_rate}% present rate across {attendance_total} attendance entries.",
        },
        {
            "title": "Finance Position",
            "body": f"Outstanding due stands at Rs {outstanding} with {payments.count()} payment entries already recorded.",
        },
        {
            "title": "Exam Coverage",
            "body": f"{exams.count()} exam sessions and {exam_marks.count()} marks entries are currently available.",
        },
    ]

    context = build_layout_context(request.user, current_section="reports")
    context["report_metrics"] = metrics
    context["report_panels"] = panels
    return render(request, "reports/overview.html", context)
