import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.models import EntityChangeLog
from apps.core.permissions import role_required
from apps.core.tenancy import get_selected_school_or_redirect

from .forms import AlumniEventForm, AlumniForm, SuccessStoryForm
from .models import Alumni, AlumniContribution, AlumniEvent, SuccessStory


def _log_alumni_change(request, entity, object_id, action, changes=None):
    EntityChangeLog.objects.create(
        actor=request.user if getattr(request.user, "is_authenticated", False) else None,
        entity=entity,
        object_id=str(object_id),
        action=action,
        changes=changes or {},
        ip_address=request.META.get("REMOTE_ADDR", "")[:64],
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def alumni_dashboard(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    alumni_qs = Alumni.objects.filter(school=school)
    total_alumni = alumni_qs.count()
    upcoming_events = AlumniEvent.objects.filter(school=school, date__gte=timezone.now()).count()
    total_contributions = (
        AlumniContribution.objects.filter(alumni__school=school).aggregate(total=Sum("amount"))[
            "total"
        ]
        or 0
    )
    featured_stories = SuccessStory.objects.filter(alumni__school=school, is_featured=True).count()

    recent_alumni = alumni_qs.order_by("-created_at")[:5]
    # Filter for future events and sort by soonest first
    recent_events = AlumniEvent.objects.filter(school=school, date__gte=timezone.now()).order_by(
        "date"
    )[:5]

    # Real Chart Data: Batch Distribution

    batch_data = (
        alumni_qs.values("graduation_year")
        .annotate(count=Count("id"))
        .order_by("-graduation_year")[:5]
    )
    batch_labels = [str(item["graduation_year"]) for item in batch_data]
    batch_distribution = [item["count"] for item in batch_data]

    # Fallback for batch chart
    if not batch_distribution:
        batch_labels = ["No Data"]
        batch_distribution = [1]  # Single slice for "No Data"

    # Chart Data: Contribution Trend (Last 6 months - Continuous)
    import datetime

    from django.db.models.functions import TruncMonth

    # Get last 6 months labels starting from current month
    end_date = timezone.now().date().replace(day=1)
    months_list = []
    for i in range(5, -1, -1):
        m_idx = (end_date.month - i - 1) % 12 + 1
        y_idx = end_date.year + (end_date.month - i - 1) // 12
        months_list.append(datetime.date(y_idx, m_idx, 1))

    real_data = (
        AlumniContribution.objects.filter(alumni__school=school, date__gte=months_list[0])
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
    )

    data_dict = {}
    for item in real_data:
        m_val = item["month"]
        # datetime has .date(), date does not.
        d_val = m_val.date() if hasattr(m_val, "date") else m_val
        data_dict[d_val] = float(item["total"])

    contribution_trend = []
    contribution_labels = []
    for m in months_list:
        contribution_labels.append(m.strftime("%b %Y"))
        contribution_trend.append(data_dict.get(m, 0.0))

    import json

    chart_data = {
        "batch_distribution": batch_distribution,
        "batch_labels": batch_labels,
        "contribution_trend": contribution_trend,
        "contribution_labels": contribution_labels,
        "currency_symbol": school.currency or "₹",
    }

    context = {
        "total_alumni": total_alumni,
        "upcoming_events": upcoming_events,
        "total_contributions": total_contributions,
        "featured_stories": featured_stories,
        "recent_alumni": recent_alumni,
        "recent_events": recent_events,
        "school": school,
        "current_section": "alumni",
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "alumni/dashboard.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def alumni_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    from django.core.paginator import Paginator

    alumni_queryset = Alumni.objects.filter(school=school)

    # Filters
    q = request.GET.get("q")
    year = request.GET.get("year")
    status = request.GET.get("status")

    if q:
        from django.db.models import Q

        alumni_queryset = alumni_queryset.filter(
            Q(full_name__icontains=q) | Q(email__icontains=q) | Q(current_organization__icontains=q)
        )

    if year:
        alumni_queryset = alumni_queryset.filter(graduation_year=year)

    if status == "verified":
        alumni_queryset = alumni_queryset.filter(is_verified=True)
    elif status == "pending":
        alumni_queryset = alumni_queryset.filter(is_verified=False)

    # Get all unique years for the filter dropdown
    available_years = (
        Alumni.objects.filter(school=school)
        .values_list("graduation_year", flat=True)
        .distinct()
        .order_by("-graduation_year")
    )

    paginator = Paginator(alumni_queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "alumni_list": page_obj,
        "school": school,
        "current_section": "alumni",
        "years": available_years,
    }
    return render(request, "alumni/alumni_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def event_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    from django.core.paginator import Paginator

    events_queryset = AlumniEvent.objects.filter(school=school)

    # Year Filter
    year = request.GET.get("year")
    if year:
        events_queryset = events_queryset.filter(date__year=year)

    # Get available years from event dates
    available_years = AlumniEvent.objects.filter(school=school).dates("date", "year", order="DESC")
    years_list = [d.year for d in available_years]

    paginator = Paginator(events_queryset, 9)  # 3x3 grid
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "events": page_obj,
        "school": school,
        "current_section": "alumni",
        "years": years_list,
    }
    return render(request, "alumni/event_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def success_stories(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    from django.core.paginator import Paginator

    stories_queryset = SuccessStory.objects.filter(alumni__school=school)

    # Year Filter
    year = request.GET.get("year")
    if year:
        stories_queryset = stories_queryset.filter(alumni__graduation_year=year)

    # Available graduation years for filtering
    available_years = (
        Alumni.objects.filter(school=school)
        .values_list("graduation_year", flat=True)
        .distinct()
        .order_by("-graduation_year")
    )

    paginator = Paginator(stories_queryset, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "stories": page_obj,
        "school": school,
        "current_section": "alumni",
        "years": available_years,
    }
    return render(request, "alumni/success_stories.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def alumni_create(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    from apps.students.models import Student

    existing_alumni_students = Alumni.objects.filter(
        school=school, student__isnull=False
    ).values_list("student_id", flat=True)
    allowed_students = Student.objects.filter(school=school).exclude(
        id__in=existing_alumni_students
    )

    if request.method == "POST":
        form = AlumniForm(request.POST)
        form.fields["student"].queryset = allowed_students
        if form.is_valid():
            alumni = form.save(commit=False)
            alumni.school = school
            alumni.save()
            return redirect("alumni:alumni_list")
    else:
        form = AlumniForm()
        # Filter student choices to current school and exclude those who are already alumni
        form.fields["student"].queryset = allowed_students

    context = {
        "form": form,
        "school": school,
        "current_section": "alumni",
        "title": "Add New Alumni",
    }
    return render(request, "alumni/alumni_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def event_create(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    if request.method == "POST":
        form = AlumniEventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.school = school
            event.save()
            return redirect("alumni:event_list")
    else:
        form = AlumniEventForm()

    context = {
        "form": form,
        "school": school,
        "current_section": "alumni",
        "title": "Schedule New Event",
    }
    return render(request, "alumni/event_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def story_create(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    allowed_alumni = Alumni.objects.filter(school=school)

    if request.method == "POST":
        form = SuccessStoryForm(request.POST, request.FILES)
        form.fields["alumni"].queryset = allowed_alumni
        if form.is_valid():
            story = form.save(commit=False)
            story.save()
            return redirect("alumni:success_stories")
    else:
        form = SuccessStoryForm()
        # Filter alumni choices to current school
        form.fields["alumni"].queryset = allowed_alumni

    context = {
        "form": form,
        "school": school,
        "current_section": "alumni",
        "title": "Publish Success Story",
    }
    return render(request, "alumni/story_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def alumni_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    from apps.students.models import Student

    # Exclude students already linked to OTHER alumni records
    existing_alumni_students = (
        Alumni.objects.filter(school=school, student__isnull=False)
        .exclude(pk=pk)
        .values_list("student_id", flat=True)
    )
    allowed_students = Student.objects.filter(school=school).exclude(
        id__in=existing_alumni_students
    )

    alumni = get_object_or_404(Alumni, pk=pk, school=school)
    if request.method == "POST":
        form = AlumniForm(request.POST, instance=alumni)
        form.fields["student"].queryset = allowed_students
        if form.is_valid():
            form.save()
            return redirect("alumni:alumni_list")
    else:
        form = AlumniForm(instance=alumni)
        form.fields["student"].queryset = allowed_students

    context = {
        "form": form,
        "school": school,
        "current_section": "alumni",
        "title": "Edit Alumni Member",
    }
    return render(request, "alumni/alumni_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def alumni_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    person = get_object_or_404(Alumni, pk=pk, school=school)

    # Metrics for the profile
    contribution_count = person.contributions.count()
    total_donated = (
        person.contributions.filter(type="DONATION").aggregate(total=Sum("amount"))["total"] or 0
    )
    story_count = person.success_stories.count()

    context = {
        "person": person,
        "contribution_count": contribution_count,
        "total_donated": total_donated,
        "story_count": story_count,
        "school": school,
        "current_section": "alumni",
        "title": f"Alumni Profile - {person.full_name}",
    }
    return render(request, "alumni/alumni_detail.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def event_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    event = get_object_or_404(AlumniEvent, pk=pk, school=school)
    if request.method == "POST":
        form = AlumniEventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            return redirect("alumni:event_list")
    else:
        form = AlumniEventForm(instance=event)

    context = {"form": form, "school": school, "current_section": "alumni", "title": "Edit Event"}
    return render(request, "alumni/event_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def story_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    allowed_alumni = Alumni.objects.filter(school=school)

    story = get_object_or_404(SuccessStory, pk=pk, alumni__school=school)
    if request.method == "POST":
        form = SuccessStoryForm(request.POST, request.FILES, instance=story)
        form.fields["alumni"].queryset = allowed_alumni
        if form.is_valid():
            form.save()
            return redirect("alumni:success_stories")
    else:
        form = SuccessStoryForm(instance=story)
        form.fields["alumni"].queryset = allowed_alumni

    context = {
        "form": form,
        "school": school,
        "current_section": "alumni",
        "title": "Edit Success Story",
    }
    return render(request, "alumni/story_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def event_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    event = get_object_or_404(AlumniEvent, pk=pk, school=school)
    context = {
        "event": event,
        "school": school,
        "current_section": "alumni",
        "is_past": event.date < timezone.now(),
    }
    return render(request, "alumni/event_detail.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def story_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    story = get_object_or_404(SuccessStory, pk=pk, alumni__school=school)
    context = {"story": story, "school": school, "current_section": "alumni"}
    return render(request, "alumni/story_detail.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def alumni_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    person = get_object_or_404(Alumni, pk=pk, school=school)
    if request.method == "POST":
        person_id = person.pk
        person_name = person.full_name
        person.delete()
        _log_alumni_change(
            request,
            "alumni.Alumni",
            person_id,
            "DELETED",
            {"full_name": {"before": person_name, "after": None}},
        )
    return redirect("alumni:alumni_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def event_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    event = get_object_or_404(AlumniEvent, pk=pk, school=school)
    if request.method == "POST":
        event_id = event.pk
        event_title = event.title
        event.delete()
        _log_alumni_change(
            request,
            "alumni.AlumniEvent",
            event_id,
            "DELETED",
            {"title": {"before": event_title, "after": None}},
        )
    return redirect("alumni:event_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def story_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    story = get_object_or_404(SuccessStory, pk=pk, alumni__school=school)
    if request.method == "POST":
        story_id = story.pk
        story_title = story.title
        story.delete()
        _log_alumni_change(
            request,
            "alumni.SuccessStory",
            story_id,
            "DELETED",
            {"title": {"before": story_title, "after": None}},
        )
    return redirect("alumni:success_stories")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def toggle_verification(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    person = get_object_or_404(Alumni, pk=pk, school=school)
    if request.method == "POST":
        before = person.is_verified
        person.is_verified = not person.is_verified
        person.save(update_fields=["is_verified"])
        _log_alumni_change(
            request,
            "alumni.Alumni",
            person.pk,
            "UPDATED",
            {"is_verified": {"before": before, "after": person.is_verified}},
        )
    next_url = request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("alumni:alumni_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def add_contribution(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect
    person = get_object_or_404(Alumni, pk=pk, school=school)

    if request.method == "POST":
        ctype = request.POST.get("type")
        amount_raw = request.POST.get("amount", 0)
        notes = request.POST.get("notes", "")
        valid_types = {choice[0] for choice in AlumniContribution.TYPE_CHOICES}
        if ctype not in valid_types:
            messages.error(request, "Invalid contribution type.")
            return redirect("alumni:alumni_detail", pk=pk)
        try:
            amount = Decimal(str(amount_raw or "0"))
        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid contribution amount.")
            return redirect("alumni:alumni_detail", pk=pk)
        if amount < 0:
            messages.error(request, "Contribution amount cannot be negative.")
            return redirect("alumni:alumni_detail", pk=pk)
        contribution = AlumniContribution.objects.create(
            alumni=person, type=ctype, amount=amount, notes=notes
        )
        _log_alumni_change(
            request,
            "alumni.AlumniContribution",
            contribution.pk,
            "CREATED",
            {
                "amount": {"before": None, "after": str(amount)},
                "type": {"before": None, "after": ctype},
            },
        )
    return redirect("alumni:alumni_detail", pk=pk)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def delete_contribution(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    # Using filter with school indirectly through alumni to ensure security
    contribution = get_object_or_404(AlumniContribution, pk=pk, alumni__school=school)
    alumni_pk = contribution.alumni.pk

    if request.method == "POST":
        contribution_id = contribution.pk
        contribution_type = contribution.type
        contribution.delete()
        messages.success(request, "Contribution record deleted successfully.")
        _log_alumni_change(
            request,
            "alumni.AlumniContribution",
            contribution_id,
            "DELETED",
            {"type": {"before": contribution_type, "after": None}},
        )

    return redirect("alumni:alumni_detail", pk=alumni_pk)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "ALUMNI_MANAGER")
def export_alumni_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Alumni")
    if error_redirect:
        return error_redirect

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="alumni_export_{school.name}.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Full Name",
            "Graduation Year",
            "Batch",
            "Occupation",
            "Organization",
            "Email",
            "Phone",
            "Verified",
        ]
    )

    alumni = Alumni.objects.filter(school=school)
    _log_alumni_change(
        request, "alumni.Alumni", school.pk, "UPDATED", {"export": {"before": None, "after": "csv"}}
    )
    for person in alumni:
        writer.writerow(
            [
                person.full_name,
                person.graduation_year,
                person.batch,
                person.current_occupation,
                person.current_organization,
                person.email,
                person.phone,
                "Yes" if person.is_verified else "No",
            ]
        )

    return response
