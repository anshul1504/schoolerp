import calendar
import csv
import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.academics.models import AcademicClass
from apps.core.permissions import has_permission, role_required
from apps.core.tenancy import school_scope_for_user, selected_school_for_request
from apps.core.ui import build_layout_context
from apps.students.models import Student

from .models import AttendanceSession, StudentAttendance

logger = logging.getLogger(__name__)


ATTENDANCE_STATUS_OPTIONS = [choice[0] for choice in StudentAttendance.STATUS_CHOICES]


def _school_scope(user):
    return school_scope_for_user(user)


def _selected_school(request):
    return selected_school_for_request(request)


def _class_scope(user, school=None):
    classes = AcademicClass.objects.select_related("school", "class_teacher")
    if school:
        return classes.filter(school=school)
    if user.role == "SUPER_ADMIN":
        return classes.filter(school__is_active=True)
    if user.school_id:
        return classes.filter(school_id=user.school_id)
    return classes.none()


def _send_absence_notifications(session, absent_students):
    """
    Sends email notifications to guardians of absent students.
    """
    if not absent_students:
        return

    subject = f"Absence Notification: {session.academic_class}"
    for student in absent_students:
        email = student.guardian_email or student.father_email or student.mother_email
        if not email:
            logger.warning(f"No email found for student {student.id} to send absence alert.")
            continue

        message = (
            f"Dear Parent/Guardian,\n\n"
            f"This is to inform you that {student.first_name} {student.last_name} was marked ABSENT "
            f"for the class {session.academic_class} on {session.attendance_date}.\n\n"
            f"Note: {session.note}\n\n"
            f"If this is an error, please contact the school office.\n\n"
            f"Regards,\n"
            f"{session.school.name}"
        )
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
        except Exception:
            logger.exception(f"Failed to send absence email to {email}")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "STUDENT", "PARENT")
def attendance_overview(request):
    if request.method == "POST" and not has_permission(request.user, "attendance.manage"):
        messages.error(request, "You do not have permission to manage attendance.")
        return redirect("/attendance/")

    if not has_permission(request.user, "attendance.view"):
        messages.error(request, "You do not have permission to view attendance.")
        return redirect("dashboard")

    school = _selected_school(request)
    if request.user.role == "SUPER_ADMIN" and school is None:
        if request.method == "POST":
            messages.error(request, "Select a school before managing attendance.")
            return redirect("/attendance/")
    selected_class_id = request.GET.get("academic_class", "").strip()
    selected_date = request.GET.get("date", "").strip() or timezone.localdate().isoformat()

    academic_classes = _class_scope(request.user, school).order_by("name", "section")
    sessions = AttendanceSession.objects.select_related("academic_class", "marked_by", "school")
    if school:
        sessions = sessions.filter(school=school)
    elif request.user.school_id:
        sessions = sessions.filter(school_id=request.user.school_id)
    elif request.user.role == "SUPER_ADMIN":
        sessions = sessions.none()
        academic_classes = academic_classes.none()

    def sanitize_cell(value) -> str:
        text = str(value or "")
        if text and text[0] in ("=", "+", "-", "@"):
            return f"'{text}"
        return text

    def esc(value) -> str:
        return (
            sanitize_cell(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    export_format = (request.GET.get("export") or "").strip().lower()
    dataset = (request.GET.get("dataset") or "").strip().lower()
    if export_format in {"csv", "excel"} and dataset == "sessions":
        if request.user.role == "SUPER_ADMIN" and school is None:
            messages.error(request, "Select a school before exporting attendance.")
            return redirect("/attendance/")

        qs = sessions.order_by("-attendance_date", "-id")
        raw_ids = (request.GET.get("session_ids") or request.GET.get("ids") or "").strip()
        if raw_ids:
            ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
            if ids:
                qs = qs.filter(id__in=sorted(set(ids)))

        if export_format == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="attendance_sessions.csv"'
            writer = csv.writer(response)
            writer.writerow(["id", "school", "date", "class", "section", "marked_by", "note"])
            for row in qs[:10000]:
                marker = row.marked_by.get_full_name() if row.marked_by else ""
                if not marker and row.marked_by:
                    marker = row.marked_by.username
                writer.writerow(
                    [
                        row.id,
                        sanitize_cell(row.school.name if row.school else ""),
                        sanitize_cell(row.attendance_date),
                        sanitize_cell(row.academic_class.name if row.academic_class else ""),
                        sanitize_cell(row.academic_class.section if row.academic_class else ""),
                        sanitize_cell(marker),
                        sanitize_cell(row.note),
                    ]
                )
            return response

        response = HttpResponse(content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = 'attachment; filename="attendance_sessions.xls"'
        rows_html = []
        for row in qs[:10000]:
            marker = row.marked_by.get_full_name() if row.marked_by else ""
            if not marker and row.marked_by:
                marker = row.marked_by.username
            rows_html.append(
                "<tr>"
                f"<td>{esc(row.id)}</td>"
                f"<td>{esc(row.school.name if row.school else '')}</td>"
                f"<td>{esc(row.attendance_date)}</td>"
                f"<td>{esc(row.academic_class.name if row.academic_class else '')}</td>"
                f"<td>{esc(row.academic_class.section if row.academic_class else '')}</td>"
                f"<td>{esc(marker)}</td>"
                f"<td>{esc(row.note)}</td>"
                "</tr>"
            )
        response.write(
            "<table><thead><tr>"
            "<th>id</th><th>school</th><th>date</th><th>class</th><th>section</th><th>marked_by</th><th>note</th>"
            f"</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"
        )
        return response

    students = Student.objects.none()
    selected_class = None
    active_session = None
    if selected_class_id:
        selected_class = academic_classes.filter(id=selected_class_id).first()
        if selected_class:
            students = Student.objects.filter(
                school=selected_class.school,
                class_name=selected_class.name,
                section=selected_class.section,
                is_active=True,
            ).order_by("first_name", "last_name")
            active_session = AttendanceSession.objects.filter(
                academic_class=selected_class,
                attendance_date=selected_date,
            ).first()

    if request.method == "POST":
        try:
            with transaction.atomic():
                action = request.POST.get("action", "").strip()
                if request.user.role == "SUPER_ADMIN":
                    if school is None:
                        messages.error(request, "Select a school before managing attendance.")
                        return redirect("/attendance/")
                    selected_class = get_object_or_404(
                        _class_scope(request.user, school), id=request.POST.get("academic_class")
                    )
                else:
                    selected_class = get_object_or_404(
                        _class_scope(request.user), id=request.POST.get("academic_class")
                    )
                attendance_date = (
                    request.POST.get("attendance_date") or timezone.localdate().isoformat()
                )
                session, _ = AttendanceSession.objects.get_or_create(
                    school=selected_class.school,
                    academic_class=selected_class,
                    attendance_date=attendance_date,
                    defaults={
                        "marked_by": request.user,
                        "note": request.POST.get("note", "").strip(),
                    },
                )
                session.marked_by = request.user
                session.note = request.POST.get("note", "").strip()
                session.save(update_fields=["marked_by", "note"])

                if action == "mark_attendance":
                    student_ids = [
                        value for value in request.POST.getlist("student_ids") if value.isdigit()
                    ]
                    class_students = Student.objects.filter(
                        id__in=student_ids,
                        school=selected_class.school,
                        class_name=selected_class.name,
                        section=selected_class.section,
                    )
                    absent_students = []
                    for student in class_students:
                        status = request.POST.get(f"status_{student.id}", "PRESENT")
                        StudentAttendance.objects.update_or_create(
                            session=session,
                            student=student,
                            defaults={
                                "status": status,
                                "remark": request.POST.get(f"remark_{student.id}", "").strip(),
                            },
                        )
                        if status == "ABSENT":
                            absent_students.append(student)

                    if absent_students:
                        _send_absence_notifications(session, absent_students)

                    messages.success(request, "Attendance saved and notifications sent (if any).")
                    return redirect(
                        f"/attendance/?school={selected_class.school_id}&academic_class={selected_class.id}&date={attendance_date}"
                    )
        except Exception as e:
            logger.exception("Error saving attendance")
            messages.error(request, f"An error occurred while saving attendance: {str(e)}")
            return redirect(
                f"/attendance/?school={school.id if school else ''}&academic_class={selected_class_id}&date={selected_date}"
            )

    stats = {
        "sessions": sessions.count(),
        "today_sessions": sessions.filter(attendance_date=timezone.localdate()).count(),
        "classes": academic_classes.count(),
        "students_marked": StudentAttendance.objects.filter(session__in=sessions).count(),
    }

    existing_entries = {}
    if active_session:
        existing_entries = {
            entry.student_id: entry
            for entry in active_session.student_attendance.select_related("student")
        }
    attendance_rows = []
    for student in students:
        attendance_rows.append(
            {
                "student": student,
                "entry": existing_entries.get(student.id),
            }
        )

    context = build_layout_context(request.user, current_section="attendance")
    context["school_options"] = _school_scope(request.user)
    context["selected_school"] = school
    context["academic_classes"] = academic_classes
    context["selected_class"] = selected_class
    context["selected_date"] = selected_date
    context["students"] = students
    context["active_session"] = active_session
    context["attendance_rows"] = attendance_rows
    context["attendance_status_options"] = ATTENDANCE_STATUS_OPTIONS
    context["attendance_sessions"] = sessions[:8]
    context["attendance_stats"] = stats
    context["can_manage_attendance"] = request.user.role in {
        "SUPER_ADMIN",
        "SCHOOL_OWNER",
        "PRINCIPAL",
        "TEACHER",
    }
    return render(request, "attendance/overview.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER")
def monthly_report(request):
    school = selected_school_for_request(request)
    if not school and request.user.school:
        school = request.user.school

    if not school:
        messages.error(request, "Please select a school to view monthly report.")
        return redirect("attendance_overview")

    class_id = request.GET.get("academic_class")
    month = int(request.GET.get("month", timezone.localdate().month))
    year = int(request.GET.get("year", timezone.localdate().year))

    academic_classes = AcademicClass.objects.filter(school=school)
    selected_class = None
    report_data = []
    days_in_month = calendar.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))

    if class_id:
        selected_class = get_object_or_404(AcademicClass, id=class_id, school=school)
        students = Student.objects.filter(
            school=school,
            class_name=selected_class.name,
            section=selected_class.section,
            is_active=True,
        ).order_by("first_name", "last_name")

        # Get all sessions for this month
        sessions = AttendanceSession.objects.filter(
            academic_class=selected_class, attendance_date__year=year, attendance_date__month=month
        )

        # Get all attendance entries for these sessions
        attendance_entries = StudentAttendance.objects.filter(session__in=sessions).select_related(
            "session", "student"
        )

        # Build a lookup dictionary
        # {student_id: {day: status}}
        lookup = {}
        for entry in attendance_entries:
            student_id = entry.student_id
            day = entry.session.attendance_date.day
            if student_id not in lookup:
                lookup[student_id] = {}
            lookup[student_id][day] = entry.status

        for student in students:
            student_row = {"student": student, "days": []}
            present_count = 0
            for d in days:
                status = lookup.get(student.id, {}).get(d, "-")
                student_row["days"].append(status)
                if status == "PRESENT":
                    present_count += 1

            student_row["present_count"] = present_count
            student_row["attendance_percentage"] = (
                (present_count / len(sessions) * 100) if sessions.exists() else 0
            )
            report_data.append(student_row)

    context = build_layout_context(request.user, current_section="attendance")
    context.update(
        {
            "school": school,
            "academic_classes": academic_classes,
            "selected_class": selected_class,
            "month": month,
            "year": year,
            "days": days,
            "report_data": report_data,
            "month_name": calendar.month_name[month],
            "years": range(datetime.now().year - 2, datetime.now().year + 2),
            "months": list(enumerate(calendar.month_name))[1:],
        }
    )
    return render(request, "attendance/monthly_report.html", context)
