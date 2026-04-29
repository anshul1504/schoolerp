import csv
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML

from apps.core.permissions import role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context
from apps.staff.models import StaffMember

from .forms import GrantForm, ResearchPaperForm, ResearchProjectForm
from .models import EthicsReview, Grant, ResearchPaper, ResearchProject


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def research_overview(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    projects = ResearchProject.objects.filter(school=school)

    from django.db.models.functions import TruncMonth

    monthly_papers = list(
        ResearchPaper.objects.filter(project__school=school)
        .annotate(month=TruncMonth("publication_date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    import json

    chart_data = {
        "status_distribution": [
            projects.filter(status="PROPOSED").count(),
            projects.filter(status="ONGOING").count(),
            projects.filter(status="COMPLETED").count(),
            projects.filter(status="SUSPENDED").count(),
        ],
        "publication_trend": [p["count"] for p in monthly_papers],
        "publication_labels": [str(p["month"])[:7] for p in monthly_papers],
    }

    context = {
        "school": school,
        "total_projects": projects.count(),
        "ongoing_projects": projects.filter(status="ONGOING").count(),
        "total_budget": projects.aggregate(Sum("budget"))["budget__sum"] or Decimal("0"),
        "recent_projects": projects.order_by("-created_at")[:5],
        "recent_papers": ResearchPaper.objects.filter(project__school=school).order_by(
            "-publication_date"
        )[:5],
        "pending_reviews": EthicsReview.objects.filter(
            project__school=school, status="PENDING"
        ).count(),
        "chart_data_json": json.dumps(chart_data),
    }

    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/overview.html", context)


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def project_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    projects_list = (
        ResearchProject.objects.filter(school=school).select_related("pi").order_by("-created_at")
    )

    # Filter by search query
    q = request.GET.get("q")
    if q:
        projects_list = projects_list.filter(title__icontains=q) | projects_list.filter(
            pi__full_name__icontains=q
        )

    # Filter by status
    status = request.GET.get("status")
    if status:
        projects_list = projects_list.filter(status=status)

    paginator = Paginator(projects_list, 10)
    page = request.GET.get("page")
    try:
        projects = paginator.page(page)
    except PageNotAnInteger:
        projects = paginator.page(1)
    except EmptyPage:
        projects = paginator.page(paginator.num_pages)

    context = {"projects": projects, "school": school}
    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/project_list.html", context)


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def project_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    project = get_object_or_404(ResearchProject, pk=pk, school=school)
    grants = project.grants.all()
    papers = project.papers.all()
    review = getattr(project, "ethics_review", None)
    school_staff = StaffMember.objects.filter(school=school)

    context = {
        "project": project,
        "grants": grants,
        "papers": papers,
        "review": review,
        "school": school,
        "school_staff": school_staff,
    }
    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/project_detail.html", context)


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def project_create(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    if request.method == "POST":
        form = ResearchProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.school = school
            project.save()
            return redirect("research:project_detail", pk=project.pk)
    else:
        form = ResearchProjectForm()
        form.fields["pi"].queryset = StaffMember.objects.filter(school=school)

    context = {"form": form, "school": school}
    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/project_form.html", context)


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def project_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    project = get_object_or_404(ResearchProject, pk=pk, school=school)
    if request.method == "POST":
        form = ResearchProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            return redirect("research:project_detail", pk=project.pk)
    else:
        form = ResearchProjectForm(instance=project)
        form.fields["pi"].queryset = StaffMember.objects.filter(school=school)

    context = {"form": form, "project": project, "school": school, "is_edit": True}
    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/project_form.html", context)


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def project_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect
    project = get_object_or_404(ResearchProject, pk=pk, school=school)
    project.delete()
    return redirect("research:project_list")


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def grant_add(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect
    project = get_object_or_404(ResearchProject, pk=pk, school=school)
    if request.method == "POST":
        form = GrantForm(request.POST)
        if form.is_valid():
            grant = form.save(commit=False)
            grant.project = project
            grant.save()
    return redirect("research:project_detail", pk=project.pk)


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def paper_add(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect
    project = get_object_or_404(ResearchProject, pk=pk, school=school)
    if request.method == "POST":
        form = ResearchPaperForm(request.POST)
        if form.is_valid():
            paper = form.save(commit=False)
            paper.project = project
            paper.save()
    return redirect("research:project_detail", pk=project.pk)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def grant_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    grants_list = (
        Grant.objects.filter(project__school=school)
        .select_related("project")
        .order_by("-received_date")
    )

    paginator = Paginator(grants_list, 10)
    page = request.GET.get("page")
    try:
        grants = paginator.page(page)
    except PageNotAnInteger:
        grants = paginator.page(1)
    except EmptyPage:
        grants = paginator.page(paginator.num_pages)

    total_funding = Grant.objects.filter(project__school=school).aggregate(Sum("amount"))[
        "amount__sum"
    ] or Decimal("0")
    context = {"grants": grants, "school": school, "total_funding": total_funding}
    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/grant_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def paper_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    papers_list = (
        ResearchPaper.objects.filter(project__school=school)
        .select_related("project")
        .order_by("-publication_date")
    )

    paginator = Paginator(papers_list, 10)
    page = request.GET.get("page")
    try:
        papers = paginator.page(page)
    except PageNotAnInteger:
        papers = paginator.page(1)
    except EmptyPage:
        papers = paginator.page(paginator.num_pages)

    context = {"papers": papers, "school": school}
    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/paper_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def ethics_queue(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    reviews_list = (
        EthicsReview.objects.filter(project__school=school)
        .select_related("project", "reviewer")
        .order_by("-updated_at")
    )

    paginator = Paginator(reviews_list, 10)
    page = request.GET.get("page")
    try:
        reviews = paginator.page(page)
    except PageNotAnInteger:
        reviews = paginator.page(1)
    except EmptyPage:
        reviews = paginator.page(paginator.num_pages)

    context = {"reviews": reviews, "school": school}
    context.update(build_layout_context(request.user, current_section="research"))
    return render(request, "research/ethics_queue.html", context)


@login_required
@role_required(
    "SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR", "CAREER_COUNSELOR"
)
def ethics_update(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect
    project = get_object_or_404(ResearchProject, pk=pk, school=school)
    review, created = EthicsReview.objects.get_or_create(project=project)

    if request.method == "POST":
        status = request.POST.get("status")
        comments = request.POST.get("comments")
        reviewer_id = request.POST.get("reviewer")

        if status:
            review.status = status
        if comments is not None:
            review.comments = comments

        if reviewer_id:
            review.reviewer = StaffMember.objects.filter(id=reviewer_id, school=school).first()
        else:
            review.reviewer = None

        review.save()

    next_url = request.GET.get("next") or request.POST.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("research:project_detail", pk=project.pk)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def export_projects_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="research_projects_{timezone.now().strftime("%Y%m%d")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Title", "Lead Investigator", "Status", "Budget", "Start Date", "End Date"])

    projects = ResearchProject.objects.filter(school=school).select_related("pi")
    for p in projects:
        writer.writerow(
            [
                p.title,
                p.pi.full_name if p.pi else "N/A",
                p.get_status_display(),
                p.budget,
                p.start_date,
                p.end_date,
            ]
        )

    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def export_projects_pdf(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    projects = ResearchProject.objects.filter(school=school).select_related("pi")
    html_string = render_to_string(
        "research/exports/project_list_pdf.html",
        {"projects": projects, "school": school, "generated_at": timezone.now()},
    )

    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="research_portfolio_{timezone.now().strftime("%Y%m%d")}.pdf"'
    )
    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def export_grants_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="grants_funding_{timezone.now().strftime("%Y%m%d")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Grant ID", "Project", "Funding Agency", "Amount", "Receipt Date"])

    grants = Grant.objects.filter(project__school=school).select_related("project")
    for g in grants:
        writer.writerow([g.grant_id, g.project.title, g.agency, g.amount, g.received_date])

    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def export_project_detail_pdf(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    project = get_object_or_404(ResearchProject, pk=pk, school=school)
    html_string = render_to_string(
        "research/exports/project_detail_pdf.html",
        {
            "project": project,
            "grants": project.grants.all(),
            "papers": project.papers.all(),
            "review": getattr(project, "ethics_review", None),
            "school": school,
            "generated_at": timezone.now(),
        },
    )

    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="project_report_{project.pk}_{timezone.now().strftime("%Y%m%d")}.pdf"'
    )
    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "RESEARCH_COORDINATOR")
def export_papers_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Research")
    if error_redirect:
        return error_redirect

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="research_papers_{timezone.now().strftime("%Y%m%d")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Title", "Project", "Journal", "Publication Date", "Link"])

    papers = ResearchPaper.objects.filter(project__school=school).select_related("project")
    for p in papers:
        writer.writerow([p.title, p.project.title, p.journal, p.publication_date, p.link])

    return response
