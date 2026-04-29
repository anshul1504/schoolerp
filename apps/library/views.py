from django.shortcuts import render

from apps.core.permissions import permission_required, role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context

from .models import Author, Book, BookIssue, Category


@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "LIBRARIAN", "STAFF", "STUDENT", "PARENT"
)
@permission_required("library.view")
def library_overview(request):
    school, error_redirect = get_selected_school_or_redirect(request, "library")
    if error_redirect:
        return error_redirect

    categories = Category.objects.filter(school=school)
    authors = Author.objects.filter(school=school)
    books = Book.objects.filter(school=school)
    issues = BookIssue.objects.filter(book__school=school).order_by("-issue_date")

    context = build_layout_context(request.user, current_section="library")
    context.update(
        {
            "school": school,
            "categories": categories,
            "authors": authors,
            "books": books,
            "issues": issues,
        }
    )
    return render(request, "library/overview.html", context)
