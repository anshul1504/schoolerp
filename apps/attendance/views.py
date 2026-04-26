import csv

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.academics.models import AcademicClass
from apps.core.permissions import has_permission, role_required
from apps.core.ui import build_layout_context
from apps.schools.models import School
from apps.core.tenancy import school_scope_for_user, selected_school_for_request
from apps.students.models import Student

from .models import AttendanceSession, StudentAttendance


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
        action = request.POST.get("action", "").strip()
        if request.user.role == "SUPER_ADMIN":
            if school is None:
                messages.error(request, "Select a school before managing attendance.")
                return redirect("/attendance/")
            selected_class = get_object_or_404(_class_scope(request.user, school), id=request.POST.get("academic_class"))
        else:
            selected_class = get_object_or_404(_class_scope(request.user), id=request.POST.get("academic_class"))
        attendance_date = request.POST.get("attendance_date") or timezone.localdate().isoformat()
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
            student_ids = [value for value in request.POST.getlist("student_ids") if value.isdigit()]
            class_students = Student.objects.filter(
                id__in=student_ids,
                school=selected_class.school,
                class_name=selected_class.name,
                section=selected_class.section,
            )
            for student in class_students:
                StudentAttendance.objects.update_or_create(
                    session=session,
                    student=student,
                    defaults={
                        "status": request.POST.get(f"status_{student.id}", "PRESENT"),
                        "remark": request.POST.get(f"remark_{student.id}", "").strip(),
                    },
                )
            messages.success(request, "Attendance saved successfully.")
            return redirect(f"/attendance/?school={selected_class.school_id}&academic_class={selected_class.id}&date={attendance_date}")

    stats = {
        "sessions": sessions.count(),
        "today_sessions": sessions.filter(attendance_date=timezone.localdate()).count(),
        "classes": academic_classes.count(),
        "students_marked": StudentAttendance.objects.filter(session__in=sessions).count(),
    }

    existing_entries = {}
    if active_session:
        existing_entries = {
            entry.student_id: entry for entry in active_session.student_attendance.select_related("student")
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
    context["can_manage_attendance"] = request.user.role in {"SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER"}
    return render(request, "attendance/overview.html", context)
