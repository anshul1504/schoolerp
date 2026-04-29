from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

DEMO_PAGES = {
    "index.html",
    "index-2.html",
    "index-3.html",
    "index-4.html",
    "index-5.html",
    "login.html",
    "register.html",
    "student-list.html",
    "student-details.html",
    "add-new-student.html",
    "edit-student.html",
    "suspended-student.html",
    "student-attendance.html",
    "student-category.html",
    "teacher-list.html",
    "teacher-details.html",
    "add-new-teacher.html",
    "edit-teacher.html",
    "teacher-attendance.html",
    "teacher-timetable.html",
    "employee-list.html",
    "employee-details.html",
    "add-new-employee.html",
    "edit-employee.html",
    "employee-attendance.html",
    "guardian-list.html",
    "guardian-details.html",
    "add-new-guardian.html",
    "edit-guardian.html",
    "class-list.html",
    "class-room-list.html",
    "section-list.html",
    "subject-list.html",
    "department.html",
    "designation.html",
    "fees-collect.html",
    "fees-discount.html",
    "fees-group.html",
    "fees-type.html",
    "income-list.html",
    "income-head.html",
    "expense-list.html",
    "expense-head.html",
    "transaction.html",
    "payroll.html",
    "exam.html",
    "exam-schedule.html",
    "exam-result.html",
    "notice-board.html",
    "message.html",
    "notification.html",
    "event.html",
    "role-access.html",
    "assign-role-plan.html",
    "subscription-plan.html",
    "books-list.html",
    "members-list.html",
    "member-details.html",
    "issue-return.html",
    "leave-request.html",
    "leave-types.html",
    "certificate.html",
    "general.html",
    "languages.html",
    "currencies.html",
}


def demo_index(request):
    if not getattr(settings, "ENABLE_DEMO_PAGES", False):
        raise Http404("Demo pages disabled")
    try:
        get_template("demo/index.html")
    except TemplateDoesNotExist as err:
        raise Http404("Demo index template not found") from err
    return render(request, "demo/index.html", {"demo_page": "index.html"})


def demo_page(request, page):
    if not getattr(settings, "ENABLE_DEMO_PAGES", False):
        raise Http404("Demo pages disabled")
    if page not in DEMO_PAGES:
        raise Http404("Demo page not found")
    try:
        get_template(f"demo/{page}")
    except TemplateDoesNotExist as err:
        raise Http404("Demo page template not found") from err

    return render(request, f"demo/{page}", {"demo_page": page})
