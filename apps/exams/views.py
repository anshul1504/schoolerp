import csv
from decimal import Decimal

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from weasyprint import HTML

from apps.academics.models import AcademicClass, AcademicSubject
from apps.core.permissions import has_permission, permission_required, role_required
from apps.core.tenancy import (
    allowed_school_ids_for_user,
    get_selected_school_or_redirect,
    school_scope_for_user,
)
from apps.core.ui import build_layout_context
from apps.students.models import Student

from .models import Exam, ExamMark


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
@permission_required("exams.view")
def exams_overview(request):
    if request.method == "POST" and not has_permission(request.user, "exams.manage"):
        messages.error(request, "You do not have permission to manage exams.")
        return redirect("/exams/")

    if not has_permission(request.user, "exams.view"):
        messages.error(request, "You do not have permission to view exams.")
        return redirect("dashboard")

    school, error_redirect = get_selected_school_or_redirect(request, "exams")
    if error_redirect:
        return error_redirect
    selected_class_id = request.GET.get("academic_class", "").strip()
    selected_exam_id = request.GET.get("exam", "").strip()

    academic_classes = _class_scope(request.user, school).order_by("name", "section")
    exams = Exam.objects.select_related("school", "academic_class", "created_by")
    exams = exams.filter(school=school)
    subjects = AcademicSubject.objects.filter(school=school).select_related("academic_class")
    students_scope = Student.objects.filter(school=school, is_active=True)

    selected_class = (
        academic_classes.filter(id=selected_class_id).first() if selected_class_id else None
    )
    if selected_class:
        subjects = subjects.filter(academic_class=selected_class)
        students_scope = students_scope.filter(
            class_name=selected_class.name, section=selected_class.section
        )
        exams = exams.filter(academic_class=selected_class)

    selected_exam = exams.filter(id=selected_exam_id).first() if selected_exam_id else None

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
    if export_format in {"csv", "excel"} and dataset == "marks":
        if not selected_exam:
            messages.error(request, "Select an exam before exporting marks.")
            return redirect("/exams/")
        if request.user.role == "SUPER_ADMIN" and school is None:
            messages.error(request, "Select a school before exporting marks.")
            return redirect("/exams/")

        marks_qs = (
            ExamMark.objects.select_related("student", "subject", "exam")
            .filter(exam=selected_exam)
            .order_by("student__first_name", "student__last_name", "subject__name")
        )
        raw_student_ids = (request.GET.get("student_ids") or request.GET.get("ids") or "").strip()
        if raw_student_ids:
            ids = [int(x) for x in raw_student_ids.split(",") if x.strip().isdigit()]
            if ids:
                marks_qs = marks_qs.filter(student_id__in=sorted(set(ids)))
        if export_format == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = (
                f'attachment; filename="exam_{selected_exam.id}_marks.csv"'
            )
            writer = csv.writer(response)
            writer.writerow(
                [
                    "exam_id",
                    "exam_name",
                    "class",
                    "section",
                    "student_admission_no",
                    "student_name",
                    "subject",
                    "marks_obtained",
                    "remark",
                ]
            )
            for row in marks_qs[:200000]:
                writer.writerow(
                    [
                        selected_exam.id,
                        sanitize_cell(selected_exam.name),
                        sanitize_cell(
                            selected_exam.academic_class.name
                            if selected_exam.academic_class
                            else ""
                        ),
                        sanitize_cell(
                            selected_exam.academic_class.section
                            if selected_exam.academic_class
                            else ""
                        ),
                        sanitize_cell(getattr(row.student, "admission_no", "")),
                        sanitize_cell(
                            f"{row.student.first_name} {row.student.last_name}".strip()
                            if row.student
                            else ""
                        ),
                        sanitize_cell(row.subject.name if row.subject else ""),
                        sanitize_cell(row.marks_obtained),
                        sanitize_cell(row.remark),
                    ]
                )
            return response

        response = HttpResponse(content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = (
            f'attachment; filename="exam_{selected_exam.id}_marks.xls"'
        )
        rows_html = []
        for row in marks_qs[:200000]:
            rows_html.append(
                "<tr>"
                f"<td>{esc(selected_exam.id)}</td>"
                f"<td>{esc(selected_exam.name)}</td>"
                f"<td>{esc(selected_exam.academic_class.name if selected_exam.academic_class else '')}</td>"
                f"<td>{esc(selected_exam.academic_class.section if selected_exam.academic_class else '')}</td>"
                f"<td>{esc(getattr(row.student, 'admission_no', ''))}</td>"
                f"<td>{esc(f'{row.student.first_name} {row.student.last_name}'.strip() if row.student else '')}</td>"
                f"<td>{esc(row.subject.name if row.subject else '')}</td>"
                f"<td>{esc(row.marks_obtained)}</td>"
                f"<td>{esc(row.remark)}</td>"
                "</tr>"
            )
        response.write(
            "<table><thead><tr>"
            "<th>exam_id</th><th>exam_name</th><th>class</th><th>section</th>"
            "<th>student_admission_no</th><th>student_name</th><th>subject</th><th>marks_obtained</th><th>remark</th>"
            f"</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"
        )
        return response

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if request.user.role == "SUPER_ADMIN" and school is None:
            messages.error(request, "Select a school before managing exams.")
            return redirect("/exams/")
        if action == "create_exam":
            if request.user.role == "SUPER_ADMIN":
                selected_class = get_object_or_404(
                    _class_scope(request.user, school), id=request.POST.get("academic_class")
                )
            else:
                selected_class = get_object_or_404(
                    _class_scope(request.user), id=request.POST.get("academic_class")
                )
            exam = Exam.objects.create(
                school=selected_class.school,
                name=request.POST.get("name", "").strip(),
                academic_class=selected_class,
                exam_date=request.POST.get("exam_date"),
                total_marks=request.POST.get("total_marks") or 100,
                passing_marks=request.POST.get("passing_marks") or 33,
                created_by=request.user,
            )
            messages.success(request, "Exam created successfully.")
            return redirect(
                f"/exams/?school={selected_class.school_id}&academic_class={selected_class.id}&exam={exam.id}"
            )

        if action == "save_marks":
            school_ids = allowed_school_ids_for_user(request.user)
            selected_exam = get_object_or_404(
                Exam.objects.filter(school_id__in=school_ids), id=request.POST.get("exam")
            )
            if school and selected_exam.school_id != school.id:
                messages.error(request, "Selected exam does not belong to the selected school.")
                return redirect("/exams/")
            class_students = Student.objects.filter(
                school=selected_exam.school,
                class_name=selected_exam.academic_class.name,
                section=selected_exam.academic_class.section,
                is_active=True,
            )
            class_subjects = AcademicSubject.objects.filter(
                academic_class=selected_exam.academic_class, school=selected_exam.school
            )
            for student in class_students:
                for subject in class_subjects:
                    key = f"marks_{student.id}_{subject.id}"
                    value = request.POST.get(key, "").strip()
                    if not value:
                        continue
                    ExamMark.objects.update_or_create(
                        exam=selected_exam,
                        student=student,
                        subject=subject,
                        defaults={
                            "marks_obtained": Decimal(value),
                            "remark": request.POST.get(
                                f"remark_{student.id}_{subject.id}", ""
                            ).strip(),
                        },
                    )
            messages.success(request, "Exam marks saved successfully.")
            return redirect(
                f"/exams/?school={selected_exam.school_id}&academic_class={selected_exam.academic_class_id}&exam={selected_exam.id}"
            )

    marks_map = {}
    result_rows = []
    if selected_exam:
        exam_subjects = AcademicSubject.objects.filter(
            academic_class=selected_exam.academic_class
        ).order_by("name")
        exam_students = Student.objects.filter(
            school=selected_exam.school,
            class_name=selected_exam.academic_class.name,
            section=selected_exam.academic_class.section,
            is_active=True,
        ).order_by("first_name", "last_name")
        for mark in selected_exam.marks.select_related("student", "subject"):
            marks_map[(mark.student_id, mark.subject_id)] = mark

        for student in exam_students:
            subject_scores = []
            total = Decimal("0")
            entered = 0
            for subject in exam_subjects:
                entry = marks_map.get((student.id, subject.id))
                score = entry.marks_obtained if entry else None
                if score is not None:
                    total += score
                    entered += 1
                subject_scores.append({"subject": subject, "entry": entry})
            result_rows.append(
                {
                    "student": student,
                    "subject_scores": subject_scores,
                    "total": total,
                    "entered": entered,
                    "status": "Complete"
                    if entered == exam_subjects.count() and exam_subjects.count()
                    else "Pending",
                }
            )
    else:
        exam_subjects = subjects.order_by("name")

    context = build_layout_context(request.user, current_section="exams")
    context["school_options"] = school_scope_for_user(request.user)
    context["selected_school"] = school
    context["academic_classes"] = academic_classes
    context["selected_class"] = selected_class
    context["exams"] = exams.order_by("-exam_date", "name")
    context["selected_exam"] = selected_exam
    context["subjects"] = subjects.order_by("name")
    context["students"] = students_scope.order_by("first_name", "last_name")
    context["exam_subjects"] = exam_subjects
    context["result_rows"] = result_rows
    context["exams_stats"] = {
        "exams": exams.count(),
        "subjects": subjects.count(),
        "students": students_scope.count(),
        "marks": ExamMark.objects.filter(exam__in=exams).count(),
    }
    return render(request, "exams/overview.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER", "PARENT", "STUDENT")
def generate_report_card_pdf(request, exam_id, student_id):
    school, error_redirect = get_selected_school_or_redirect(request, "exams")
    if error_redirect:
        return error_redirect
    exam = get_object_or_404(Exam, id=exam_id)
    student = get_object_or_404(Student, id=student_id)

    # Security check: Ensure the exam and student belong to the user's school
    if not request.user.role == "SUPER_ADMIN" and exam.school != request.user.school:
        messages.error(request, "Unauthorized access to report card.")
        return redirect("exams_overview")

    marks = ExamMark.objects.filter(exam=exam, student=student).select_related("subject")

    total_obtained = sum(m.marks_obtained for m in marks)
    subject_count = marks.count()
    grand_total = exam.total_marks * subject_count if subject_count else 0
    percentage = (total_obtained / grand_total * 100) if grand_total else 0

    # Determine result (Pass/Fail)
    failed_subjects = marks.filter(marks_obtained__lt=exam.passing_marks).count()
    result = "PASSED" if failed_subjects == 0 and subject_count > 0 else "FAILED"

    # Determine overall remark based on percentage (optional)
    overall_remark = (
        "Excellent"
        if percentage >= 90
        else "Good"
        if percentage >= 75
        else "Satisfactory"
        if percentage >= 50
        else "Needs Improvement"
    )

    context = {
        "school": exam.school,
        "exam": exam,
        "student": student,
        "marks": marks,
        "total_obtained": total_obtained,
        "grand_total": grand_total,
        "percentage": round(percentage, 2),
        "result": result,
        "overall_remark": overall_remark,
    }

    html_string = render_to_string("exams/report_card_pdf.html", context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="report_{student.admission_no}_{exam.id}.pdf"'
    )
    return response
