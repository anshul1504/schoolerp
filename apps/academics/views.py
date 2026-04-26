from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import redirect, render
import csv

from apps.core.permissions import has_permission, role_required
from apps.core.ui import build_layout_context
from apps.schools.models import School
from apps.core.tenancy import school_scope_for_user, selected_school_for_request

from .models import AcademicClass, AcademicSubject, TeacherAllocation, AcademicYear, ClassMaster, SectionMaster, SubjectMaster


def _school_scope(user):
    return school_scope_for_user(user)


def _selected_school(request):
    return selected_school_for_request(request)


def _academics_queryset_for_user(user):
    schools = _school_scope(user)
    return {
        "classes": AcademicClass.objects.select_related("school", "class_teacher").filter(school__in=schools),
        "subjects": AcademicSubject.objects.select_related("school", "academic_class").filter(school__in=schools),
        "allocations": TeacherAllocation.objects.select_related("school", "teacher", "academic_class", "subject").filter(school__in=schools),
    }


def _sanitize_cell(value) -> str:
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def _esc(value) -> str:
    return (
        _sanitize_cell(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _parse_ids(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
    return sorted(set(ids))


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER")
def academics_export_csv(request):
    if not has_permission(request.user, "academics.view"):
        messages.error(request, "You do not have permission to view academics.")
        return redirect("dashboard")

    school = _selected_school(request)
    scoped = _academics_queryset_for_user(request.user)
    dataset = (request.GET.get("dataset") or "").strip().lower()

    if request.user.role == "SUPER_ADMIN" and school is None:
        messages.error(request, "Select a school before exporting academics.")
        return redirect("/academics/")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="academics_export.csv"'
    writer = csv.writer(response)

    if dataset == "classes":
        qs = scoped["classes"]
        if school:
            qs = qs.filter(school=school)
        ids = _parse_ids(request.GET.get("class_ids") or request.GET.get("ids") or "")
        if ids:
            qs = qs.filter(id__in=ids)
        writer.writerow(["id", "school", "name", "section", "room_name", "capacity", "class_teacher", "is_active"])
        for c in qs.order_by("name", "section", "id")[:20000]:
            teacher = c.class_teacher.get_full_name() if c.class_teacher else ""
            if not teacher and c.class_teacher:
                teacher = c.class_teacher.username
            writer.writerow(
                [
                    c.id,
                    _sanitize_cell(c.school.name if c.school else ""),
                    _sanitize_cell(c.name),
                    _sanitize_cell(c.section),
                    _sanitize_cell(c.room_name),
                    _sanitize_cell(c.capacity),
                    _sanitize_cell(teacher),
                    _sanitize_cell("yes" if c.is_active else "no"),
                ]
            )
        return response

    if dataset == "subjects":
        qs = scoped["subjects"]
        if school:
            qs = qs.filter(school=school)
        ids = _parse_ids(request.GET.get("subject_ids") or request.GET.get("ids") or "")
        if ids:
            qs = qs.filter(id__in=ids)
        writer.writerow(["id", "school", "name", "code", "class", "section", "is_optional"])
        for s in qs.order_by("name", "id")[:20000]:
            writer.writerow(
                [
                    s.id,
                    _sanitize_cell(s.school.name if s.school else ""),
                    _sanitize_cell(s.name),
                    _sanitize_cell(s.code),
                    _sanitize_cell(s.academic_class.name if s.academic_class else ""),
                    _sanitize_cell(s.academic_class.section if s.academic_class else ""),
                    _sanitize_cell("yes" if s.is_optional else "no"),
                ]
            )
        return response

    messages.error(request, "Invalid export dataset.")
    return redirect("/academics/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER")
def academics_export_excel(request):
    if not has_permission(request.user, "academics.view"):
        messages.error(request, "You do not have permission to view academics.")
        return redirect("dashboard")

    school = _selected_school(request)
    scoped = _academics_queryset_for_user(request.user)
    dataset = (request.GET.get("dataset") or "").strip().lower()

    if request.user.role == "SUPER_ADMIN" and school is None:
        messages.error(request, "Select a school before exporting academics.")
        return redirect("/academics/")

    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="academics_export.xls"'

    if dataset == "classes":
        qs = scoped["classes"]
        if school:
            qs = qs.filter(school=school)
        ids = _parse_ids(request.GET.get("class_ids") or request.GET.get("ids") or "")
        if ids:
            qs = qs.filter(id__in=ids)
        rows = []
        for c in qs.order_by("name", "section", "id")[:20000]:
            teacher = c.class_teacher.get_full_name() if c.class_teacher else ""
            if not teacher and c.class_teacher:
                teacher = c.class_teacher.username
            rows.append(
                "<tr>"
                f"<td>{_esc(c.id)}</td>"
                f"<td>{_esc(c.school.name if c.school else '')}</td>"
                f"<td>{_esc(c.name)}</td>"
                f"<td>{_esc(c.section)}</td>"
                f"<td>{_esc(c.room_name)}</td>"
                f"<td>{_esc(c.capacity)}</td>"
                f"<td>{_esc(teacher)}</td>"
                f"<td>{_esc('yes' if c.is_active else 'no')}</td>"
                "</tr>"
            )
        response.write(
            "<table><thead><tr>"
            "<th>id</th><th>school</th><th>name</th><th>section</th><th>room_name</th><th>capacity</th><th>class_teacher</th><th>is_active</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        )
        return response

    if dataset == "subjects":
        qs = scoped["subjects"]
        if school:
            qs = qs.filter(school=school)
        ids = _parse_ids(request.GET.get("subject_ids") or request.GET.get("ids") or "")
        if ids:
            qs = qs.filter(id__in=ids)
        rows = []
        for s in qs.order_by("name", "id")[:20000]:
            rows.append(
                "<tr>"
                f"<td>{_esc(s.id)}</td>"
                f"<td>{_esc(s.school.name if s.school else '')}</td>"
                f"<td>{_esc(s.name)}</td>"
                f"<td>{_esc(s.code)}</td>"
                f"<td>{_esc(s.academic_class.name if s.academic_class else '')}</td>"
                f"<td>{_esc(s.academic_class.section if s.academic_class else '')}</td>"
                f"<td>{_esc('yes' if s.is_optional else 'no')}</td>"
                "</tr>"
            )
        response.write(
            "<table><thead><tr>"
            "<th>id</th><th>school</th><th>name</th><th>code</th><th>class</th><th>section</th><th>is_optional</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        )
        return response

    messages.error(request, "Invalid export dataset.")
    return redirect("/academics/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL", "TEACHER")
def academics_overview(request):
    if request.method == "POST" and not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    if not has_permission(request.user, "academics.view"):
        messages.error(request, "You do not have permission to view academics.")
        return redirect("dashboard")

    school = _selected_school(request) if request.method == "POST" else _selected_school(request)
    scoped = _academics_queryset_for_user(request.user)
    classes = scoped["classes"]
    subjects = scoped["subjects"]
    allocations = scoped["allocations"]

    if school:
        classes = classes.filter(school=school)
        subjects = subjects.filter(school=school)
        allocations = allocations.filter(school=school)

    if request.method == "POST" and request.user.role in {"SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL"}:
        action = request.POST.get("action", "").strip()
        if school is None:
            messages.error(request, "Select a valid school before saving academics.")
            return redirect("/academics/")

        if action == "create_class":
            class_name = request.POST.get("name", "").strip()
            section = request.POST.get("section", "").strip()
            if not class_name or not section:
                messages.error(request, "Class name and section are both required.")
            else:
                # Keep master lists updated so dropdown suggestions stay useful.
                ClassMaster.objects.get_or_create(school=school, name=class_name)
                SectionMaster.objects.get_or_create(school=school, name=section)

                teacher_id = request.POST.get("class_teacher")
                teacher = None
                if teacher_id:
                    teacher = get_user_model().objects.filter(id=teacher_id, role="TEACHER", school=school).first()
                AcademicClass.objects.get_or_create(
                    school=school,
                    name=class_name,
                    section=section,
                    defaults={
                        "class_teacher": teacher,
                        "room_name": request.POST.get("room_name", "").strip(),
                        "capacity": request.POST.get("capacity") or 40,
                    },
                )
                messages.success(request, "Academic class created successfully.")
            return redirect(f"/academics/?school={school.id}")

        if action == "create_subject":
            class_id = request.POST.get("academic_class")
            academic_class = AcademicClass.objects.filter(id=class_id, school=school).first()
            subject_name = request.POST.get("name", "").strip()
            if not academic_class or not subject_name:
                messages.error(request, "Choose a class and subject name before saving.")
            else:
                SubjectMaster.objects.get_or_create(school=school, name=subject_name)
                AcademicSubject.objects.get_or_create(
                    school=school,
                    academic_class=academic_class,
                    name=subject_name,
                    defaults={
                        "code": request.POST.get("code", "").strip(),
                        "is_optional": request.POST.get("is_optional") == "on",
                    },
                )
                messages.success(request, "Subject added successfully.")
            return redirect(f"/academics/?school={school.id}")

        if action == "create_allocation":
            teacher = get_user_model().objects.filter(
                id=request.POST.get("teacher"),
                role="TEACHER",
                school=school,
            ).first()
            academic_class = AcademicClass.objects.filter(id=request.POST.get("academic_class"), school=school).first()
            subject = AcademicSubject.objects.filter(id=request.POST.get("subject"), school=school).first()
            if not teacher or not academic_class or not subject:
                messages.error(request, "Choose a valid teacher, class, and subject.")
            elif subject.academic_class_id != academic_class.id:
                messages.error(request, "Selected subject does not belong to that class.")
            else:
                TeacherAllocation.objects.get_or_create(
                    school=school,
                    teacher=teacher,
                    academic_class=academic_class,
                    subject=subject,
                    defaults={"is_class_lead": request.POST.get("is_class_lead") == "on"},
                )
                messages.success(request, "Teacher allocation saved successfully.")
            return redirect(f"/academics/?school={school.id}")

    context = build_layout_context(request.user, current_section="academics")
    context["school_options"] = _school_scope(request.user)
    context["selected_school"] = school
    context["academic_classes"] = classes.order_by("name", "section")
    context["academic_subjects"] = subjects.order_by("academic_class__name", "name")
    context["teacher_allocations"] = allocations.order_by("academic_class__name", "subject__name")
    context["class_masters"] = ClassMaster.objects.filter(school=school if school else request.user.school, is_active=True).order_by("name") if (school or request.user.school_id) else ClassMaster.objects.none()
    context["section_masters"] = SectionMaster.objects.filter(school=school if school else request.user.school, is_active=True).order_by("name") if (school or request.user.school_id) else SectionMaster.objects.none()
    context["subject_masters"] = SubjectMaster.objects.filter(school=school if school else request.user.school, is_active=True).order_by("name") if (school or request.user.school_id) else SubjectMaster.objects.none()
    context["teacher_options"] = get_user_model().objects.filter(
        role="TEACHER",
        school=school if school else request.user.school,
    ).order_by("first_name", "username") if (school or request.user.school_id) else get_user_model().objects.none()
    context["academics_stats"] = {
        "classes": context["academic_classes"].count(),
        "subjects": context["academic_subjects"].count(),
        "allocations": context["teacher_allocations"].count(),
        "teachers": context["teacher_options"].count(),
    }
    context["can_manage_academics"] = has_permission(request.user, "academics.manage")
    return render(request, "academics/overview.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def master_list(request, master_type):
    if not has_permission(request.user, "academics.view"):
        messages.error(request, "You do not have permission to view academics.")
        return redirect("dashboard")

    school = _selected_school(request)
    if master_type == "classes":
        qs = ClassMaster.objects.filter(school__in=_school_scope(request.user)).select_related("school")
        title = "Class Master"
    elif master_type == "sections":
        qs = SectionMaster.objects.filter(school__in=_school_scope(request.user)).select_related("school")
        title = "Section Master"
    else:
        qs = SubjectMaster.objects.filter(school__in=_school_scope(request.user)).select_related("school")
        title = "Subject Master"

    if school:
        qs = qs.filter(school=school)

    context = build_layout_context(request.user, current_section="academics")
    context.update(
        {
            "master_type": master_type,
            "title": title,
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "items": qs.order_by("name")[:300],
            "can_manage": has_permission(request.user, "academics.manage"),
        }
    )
    return render(request, "academics/masters_list.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def master_create(request, master_type):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    if request.method != "POST":
        return redirect(f"/academics/masters/{master_type}/")

    school = _selected_school(request)
    if school is None:
        messages.error(request, "Select a valid school first.")
        return redirect(f"/academics/masters/{master_type}/")

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Name is required.")
        return redirect(f"/academics/masters/{master_type}/?school={school.id}")

    if master_type == "classes":
        ClassMaster.objects.get_or_create(school=school, name=name)
    elif master_type == "sections":
        SectionMaster.objects.get_or_create(school=school, name=name)
    else:
        SubjectMaster.objects.get_or_create(school=school, name=name)

    messages.success(request, "Saved.")
    return redirect(f"/academics/masters/{master_type}/?school={school.id}")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def master_edit(request, master_type, item_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    if master_type == "classes":
        model = ClassMaster
    elif master_type == "sections":
        model = SectionMaster
    else:
        model = SubjectMaster
    item = model.objects.select_related("school").filter(id=item_id, school_id__in=school_ids).first()
    if not item:
        messages.error(request, "Item not found.")
        return redirect(f"/academics/masters/{master_type}/")

    if request.method == "POST":
        item.name = (request.POST.get("name") or item.name).strip()
        item.is_active = request.POST.get("is_active") == "on"
        item.save()
        messages.success(request, "Updated.")
        return redirect(f"/academics/masters/{master_type}/?school={item.school_id}")

    context = build_layout_context(request.user, current_section="academics")
    context.update(
        {
            "master_type": master_type,
            "item": item,
        }
    )
    return render(request, "academics/master_edit.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def master_delete(request, master_type, item_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    if master_type == "classes":
        model = ClassMaster
    elif master_type == "sections":
        model = SectionMaster
    else:
        model = SubjectMaster
    item = model.objects.filter(id=item_id, school_id__in=school_ids).first()
    if not item:
        messages.error(request, "Item not found.")
        return redirect(f"/academics/masters/{master_type}/")

    if request.method == "POST":
        school_id = item.school_id
        item.delete()
        messages.success(request, "Deleted.")
        return redirect(f"/academics/masters/{master_type}/?school={school_id}")

    messages.error(request, "Invalid delete request.")
    return redirect(f"/academics/masters/{master_type}/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_year_list(request):
    if not has_permission(request.user, "academics.view"):
        messages.error(request, "You do not have permission to view academics.")
        return redirect("dashboard")

    school = _selected_school(request)
    years = AcademicYear.objects.filter(school__in=_school_scope(request.user)).select_related("school")
    if school:
        years = years.filter(school=school)

    context = build_layout_context(request.user, current_section="academics")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": school,
            "years": years.order_by("-start_date")[:250],
        }
    )
    return render(request, "academics/years_list.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_year_create(request):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/years/")

    if request.method == "POST":
        school = _selected_school(request)
        if school is None:
            messages.error(request, "Select a valid school first.")
            return redirect("/academics/years/create/")

        name = (request.POST.get("name") or "").strip()
        start_date = request.POST.get("start_date") or None
        end_date = request.POST.get("end_date") or None
        if not name or not start_date or not end_date:
            messages.error(request, "Name, start date, and end date are required.")
            return redirect("/academics/years/create/")

        is_current = request.POST.get("is_current") == "on"
        if is_current:
            AcademicYear.objects.filter(school=school, is_current=True).update(is_current=False)

        AcademicYear.objects.create(
            school=school,
            name=name,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
        )
        messages.success(request, "Academic year saved.")
        return redirect(f"/academics/years/?school={school.id}")

    context = build_layout_context(request.user, current_section="academics")
    context.update(
        {
            "school_options": _school_scope(request.user),
            "selected_school": _selected_school(request),
        }
    )
    return render(request, "academics/year_form.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_year_edit(request, year_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/years/")

    year = AcademicYear.objects.select_related("school").filter(id=year_id, school__in=_school_scope(request.user)).first()
    if not year:
        messages.error(request, "Academic year not found.")
        return redirect("/academics/years/")

    if request.method == "POST":
        year.name = (request.POST.get("name") or year.name).strip()
        year.start_date = request.POST.get("start_date") or year.start_date
        year.end_date = request.POST.get("end_date") or year.end_date

        is_current = request.POST.get("is_current") == "on"
        if is_current:
            AcademicYear.objects.filter(school=year.school, is_current=True).exclude(id=year.id).update(is_current=False)
        year.is_current = is_current

        year.save()
        messages.success(request, "Academic year updated.")
        return redirect(f"/academics/years/?school={year.school_id}")

    context = build_layout_context(request.user, current_section="academics")
    context.update(
        {
            "mode": "edit",
            "year": year,
            "school_options": _school_scope(request.user),
            "selected_school": year.school,
        }
    )
    return render(request, "academics/year_form.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_year_delete(request, year_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/years/")

    year = AcademicYear.objects.filter(id=year_id, school__in=_school_scope(request.user)).first()
    if not year:
        messages.error(request, "Academic year not found.")
        return redirect("/academics/years/")

    if request.method == "POST":
        school_id = year.school_id
        year.delete()
        messages.success(request, "Academic year deleted.")
        return redirect(f"/academics/years/?school={school_id}")

    messages.error(request, "Invalid delete request.")
    return redirect("/academics/years/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_class_edit(request, class_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    academic_class = AcademicClass.objects.select_related("school", "class_teacher").filter(id=class_id, school_id__in=school_ids).first()
    if not academic_class:
        messages.error(request, "Class not found.")
        return redirect("/academics/")

    if request.method == "POST":
        academic_class.name = (request.POST.get("name") or academic_class.name).strip()
        academic_class.section = (request.POST.get("section") or academic_class.section).strip()
        academic_class.room_name = (request.POST.get("room_name") or "").strip()
        academic_class.capacity = int(request.POST.get("capacity") or academic_class.capacity or 40)
        academic_class.is_active = request.POST.get("is_active") == "on"

        teacher_id = (request.POST.get("class_teacher") or "").strip()
        teacher = None
        if teacher_id.isdigit():
            teacher = get_user_model().objects.filter(id=int(teacher_id), role="TEACHER", school=academic_class.school).first()
        academic_class.class_teacher = teacher

        academic_class.save()
        messages.success(request, "Class updated.")
        return redirect(f"/academics/?school={academic_class.school_id}")

    teachers = get_user_model().objects.filter(role="TEACHER", school=academic_class.school).order_by("first_name", "username")
    context = build_layout_context(request.user, current_section="academics")
    context.update(
        {
            "mode": "edit",
            "entity": "class",
            "academic_class": academic_class,
            "teacher_options": teachers,
        }
    )
    return render(request, "academics/entity_edit.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_class_delete(request, class_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    academic_class = AcademicClass.objects.filter(id=class_id, school_id__in=school_ids).first()
    if not academic_class:
        messages.error(request, "Class not found.")
        return redirect("/academics/")

    if request.method == "POST":
        school_id = academic_class.school_id
        academic_class.delete()
        messages.success(request, "Class deleted.")
        return redirect(f"/academics/?school={school_id}")

    messages.error(request, "Invalid delete request.")
    return redirect("/academics/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_subject_edit(request, subject_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    subject = AcademicSubject.objects.select_related("school", "academic_class").filter(id=subject_id, school_id__in=school_ids).first()
    if not subject:
        messages.error(request, "Subject not found.")
        return redirect("/academics/")

    if request.method == "POST":
        subject.name = (request.POST.get("name") or subject.name).strip()
        subject.code = (request.POST.get("code") or "").strip()
        subject.is_optional = request.POST.get("is_optional") == "on"
        subject.save()
        messages.success(request, "Subject updated.")
        return redirect(f"/academics/?school={subject.school_id}")

    context = build_layout_context(request.user, current_section="academics")
    context.update(
        {
            "mode": "edit",
            "entity": "subject",
            "subject": subject,
        }
    )
    return render(request, "academics/entity_edit.html", context)


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def academic_subject_delete(request, subject_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    subject = AcademicSubject.objects.filter(id=subject_id, school_id__in=school_ids).first()
    if not subject:
        messages.error(request, "Subject not found.")
        return redirect("/academics/")

    if request.method == "POST":
        school_id = subject.school_id
        subject.delete()
        messages.success(request, "Subject deleted.")
        return redirect(f"/academics/?school={school_id}")

    messages.error(request, "Invalid delete request.")
    return redirect("/academics/")


@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "PRINCIPAL")
def teacher_allocation_delete(request, allocation_id):
    if not has_permission(request.user, "academics.manage"):
        messages.error(request, "You do not have permission to manage academics.")
        return redirect("/academics/")

    school_ids = list(_school_scope(request.user).values_list("id", flat=True))
    allocation = TeacherAllocation.objects.select_related("school").filter(id=allocation_id, school_id__in=school_ids).first()
    if not allocation:
        messages.error(request, "Allocation not found.")
        return redirect("/academics/")

    if request.method == "POST":
        school_id = allocation.school_id
        allocation.delete()
        messages.success(request, "Allocation removed.")
        return redirect(f"/academics/?school={school_id}")

    messages.error(request, "Invalid delete request.")
    return redirect("/academics/")
