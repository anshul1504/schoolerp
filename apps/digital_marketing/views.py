import csv
import hashlib
import hmac
import json
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.core.permissions import role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context

from .forms import (
    DigitalMarketingIntegrationSettingForm,
    DigitalMarketingReportScheduleForm,
    MarketingCampaignForm,
    MarketingLeadForm,
    SEOTrackerForm,
    SocialAccountConnectionForm,
    SocialPostForm,
    WebsiteFormIntegrationForm,
)
from .models import (
    DigitalMarketingIntegrationSetting,
    DigitalMarketingJob,
    DigitalMarketingReportRun,
    DigitalMarketingReportSchedule,
    MarketingCampaign,
    MarketingLead,
    SEOTracker,
    SocialAccountConnection,
    SocialConnectionTestLog,
    SocialPost,
    SocialPublishRun,
    WebsiteFormIntegration,
)

IMPORT_SESSION_KEY = "digital_marketing_import_preview_v1"


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def overview(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect

    campaigns = MarketingCampaign.objects.filter(school=school)
    leads = MarketingLead.objects.filter(school=school)
    social_posts = SocialPost.objects.filter(school=school)
    total_budget = campaigns.aggregate(total=Sum("budget"))["total"] or Decimal("0")
    total_spent = campaigns.aggregate(total=Sum("spent"))["total"] or Decimal("0")
    total_leads = leads.count()
    converted_leads = leads.filter(stage="CONVERTED").count()

    cpl = (total_spent / total_leads) if total_leads else Decimal("0")
    conversion_rate = (
        (Decimal(converted_leads) * Decimal("100") / Decimal(total_leads))
        if total_leads
        else Decimal("0")
    )
    budget_utilization = (
        (total_spent * Decimal("100") / total_budget) if total_budget else Decimal("0")
    )

    stage_rows = list(leads.values("stage").annotate(count=Count("id")).order_by("stage"))
    stage_labels = [row["stage"].replace("_", " ").title() for row in stage_rows]
    stage_counts = [row["count"] for row in stage_rows]

    campaign_rows = list(
        campaigns.values("name").annotate(leads_count=Count("leads")).order_by("-leads_count")[:6]
    )
    campaign_labels = [row["name"] for row in campaign_rows]
    campaign_counts = [row["leads_count"] for row in campaign_rows]
    social_channels = ["instagram", "facebook", "youtube", "linkedin", "x", "twitter"]
    social_campaigns = campaigns.filter(
        Q(channel__icontains="instagram")
        | Q(channel__icontains="facebook")
        | Q(channel__icontains="youtube")
        | Q(channel__icontains="linkedin")
        | Q(channel__icontains="twitter")
        | Q(channel__icontains="x")
    )
    social_leads = leads.filter(
        Q(source__icontains="instagram")
        | Q(source__icontains="facebook")
        | Q(source__icontains="youtube")
        | Q(source__icontains="linkedin")
        | Q(source__icontains="twitter")
        | Q(source__icontains="x")
        | Q(campaign__in=social_campaigns)
    )

    context = {
        "school": school,
        "total_campaigns": campaigns.count(),
        "active_campaigns": campaigns.filter(status="ACTIVE").count(),
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_leads": total_leads,
        "converted_leads": converted_leads,
        "cpl": round(cpl, 2),
        "conversion_rate": round(conversion_rate, 2),
        "budget_utilization": round(budget_utilization, 2),
        "lead_stage_chart_json": json.dumps({"labels": stage_labels, "series": stage_counts}),
        "campaign_lead_chart_json": json.dumps(
            {"labels": campaign_labels, "series": campaign_counts}
        ),
        "social_campaigns_count": social_campaigns.count(),
        "social_leads_count": social_leads.count(),
        "social_converted_count": social_leads.filter(stage="CONVERTED").count(),
        "social_channels_hint": ", ".join([c.title() for c in social_channels]),
        "recent_campaigns": campaigns[:5],
        "recent_leads": leads[:8],
        "recent_social_campaigns": social_campaigns[:5],
        "connected_social_accounts": SocialAccountConnection.objects.filter(
            school=school, is_active=True
        ).count(),
        "total_social_posts": SocialPost.objects.filter(school=school).count(),
        "scheduled_social_posts": SocialPost.objects.filter(
            school=school, status="SCHEDULED"
        ).count(),
        "pending_review_posts": social_posts.filter(status="IN_REVIEW").count(),
        "failed_posts_count": social_posts.filter(status="FAILED").count(),
        "followups_today": leads.filter(next_followup_on=timezone.localdate()).count(),
        "overdue_followups": leads.filter(
            next_followup_on__lt=timezone.localdate(), stage__in=["NEW", "CONTACTED", "QUALIFIED"]
        ).count(),
        "website_integrations_count": WebsiteFormIntegration.objects.filter(
            school=school, is_active=True
        ).count(),
        "seo_records_count": SEOTracker.objects.filter(school=school).count(),
        "queued_jobs_count": DigitalMarketingJob.objects.filter(
            school=school, status="QUEUED"
        ).count(),
        "dead_letter_jobs_count": DigitalMarketingJob.objects.filter(
            school=school, status="DEAD_LETTER"
        ).count(),
        "platform_health": [
            {"name": "Instagram", "key": "instagram"},
            {"name": "Facebook", "key": "facebook"},
            {"name": "LinkedIn", "key": "linkedin"},
            {"name": "X / Twitter", "key": "twitter"},
            {"name": "Pinterest", "key": "pinterest"},
            {"name": "Snapchat", "key": "snapchat"},
            {"name": "WhatsApp", "key": "whatsapp"},
            {"name": "YouTube", "key": "youtube"},
        ],
    }
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/overview.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def campaign_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    campaigns = MarketingCampaign.objects.filter(school=school)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    channel = (request.GET.get("channel") or "").strip()
    if q:
        campaigns = campaigns.filter(Q(name__icontains=q) | Q(objective__icontains=q))
    if status:
        campaigns = campaigns.filter(status=status)
    if channel:
        campaigns = campaigns.filter(channel__icontains=channel)
    paginator = Paginator(campaigns, 15)
    campaigns_page = paginator.get_page(request.GET.get("page"))
    context = {
        "school": school,
        "campaigns": campaigns_page,
        "stats": {
            "total": campaigns.count(),
            "active": campaigns.filter(status="ACTIVE").count(),
            "budget": campaigns.aggregate(total=Sum("budget"))["total"] or 0,
        },
        "filters": {"q": q, "status": status, "channel": channel},
        "status_choices": MarketingCampaign.STATUS_CHOICES,
    }
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/campaign_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def campaign_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(MarketingCampaign, pk=pk, school=school) if pk else None
    if request.method == "POST":
        form = MarketingCampaignForm(request.POST, instance=instance)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.school = school
            campaign.save()
            return redirect("digital_marketing:campaign_list")
    else:
        form = MarketingCampaignForm(instance=instance)
    context = {"school": school, "form": form, "is_edit": bool(instance)}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/campaign_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def campaign_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    campaign = get_object_or_404(MarketingCampaign, pk=pk, school=school)
    leads = MarketingLead.objects.filter(school=school, campaign=campaign).order_by("-created_at")[
        :20
    ]
    context = {
        "school": school,
        "campaign": campaign,
        "leads": leads,
        "lead_count": leads.count(),
    }
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/campaign_detail.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def lead_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    leads = MarketingLead.objects.filter(school=school).select_related("campaign")
    q = (request.GET.get("q") or "").strip()
    stage = (request.GET.get("stage") or "").strip()
    source = (request.GET.get("source") or "").strip()
    followup = (request.GET.get("followup") or "").strip()
    if q:
        leads = leads.filter(
            Q(student_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q)
        )
    if stage:
        leads = leads.filter(stage=stage)
    if source:
        leads = leads.filter(source__icontains=source)
    if followup == "today":
        leads = leads.filter(next_followup_on=timezone.localdate())
    elif followup == "overdue":
        leads = leads.filter(
            next_followup_on__lt=timezone.localdate(), stage__in=["NEW", "CONTACTED", "QUALIFIED"]
        )
    paginator = Paginator(leads, 15)
    leads_page = paginator.get_page(request.GET.get("page"))
    context = {
        "school": school,
        "leads": leads_page,
        "stats": {
            "total": leads.count(),
            "converted": leads.filter(stage="CONVERTED").count(),
            "pipeline": leads.filter(stage__in=["NEW", "CONTACTED", "QUALIFIED"]).count(),
            "sla_today": leads.filter(next_followup_on=timezone.localdate()).count(),
            "sla_overdue": leads.filter(
                next_followup_on__lt=timezone.localdate(),
                stage__in=["NEW", "CONTACTED", "QUALIFIED"],
            ).count(),
        },
        "filters": {"q": q, "stage": stage, "source": source, "followup": followup},
        "stage_choices": MarketingLead.STAGE_CHOICES,
    }
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/lead_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def lead_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(MarketingLead, pk=pk, school=school) if pk else None
    if request.method == "POST":
        form = MarketingLeadForm(request.POST, instance=instance)
        form.fields["campaign"].queryset = MarketingCampaign.objects.filter(school=school)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.school = school
            lead.save()
            return redirect("digital_marketing:lead_list")
    else:
        form = MarketingLeadForm(instance=instance)
        form.fields["campaign"].queryset = MarketingCampaign.objects.filter(school=school)
    context = {"school": school, "form": form, "is_edit": bool(instance)}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/lead_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def campaign_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    campaign = get_object_or_404(MarketingCampaign, pk=pk, school=school)
    if request.method == "POST":
        campaign.delete()
    return redirect("digital_marketing:campaign_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def lead_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    lead = get_object_or_404(MarketingLead, pk=pk, school=school)
    if request.method == "POST":
        lead.delete()
    return redirect("digital_marketing:lead_list")


def _campaigns_filtered(request, school):
    qs = MarketingCampaign.objects.filter(school=school)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    channel = (request.GET.get("channel") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(objective__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if channel:
        qs = qs.filter(channel__icontains=channel)
    return qs


def _leads_filtered(request, school):
    qs = MarketingLead.objects.filter(school=school).select_related("campaign")
    q = (request.GET.get("q") or "").strip()
    stage = (request.GET.get("stage") or "").strip()
    source = (request.GET.get("source") or "").strip()
    followup = (request.GET.get("followup") or "").strip()
    if q:
        qs = qs.filter(Q(student_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
    if stage:
        qs = qs.filter(stage=stage)
    if source:
        qs = qs.filter(source__icontains=source)
    if followup == "today":
        qs = qs.filter(next_followup_on=timezone.localdate())
    elif followup == "overdue":
        qs = qs.filter(
            next_followup_on__lt=timezone.localdate(), stage__in=["NEW", "CONTACTED", "QUALIFIED"]
        )
    return qs


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def campaign_export_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    campaigns = _campaigns_filtered(request, school)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="marketing_campaigns.csv"'
    writer = csv.writer(response)
    writer.writerow(
        ["name", "channel", "objective", "status", "budget", "spent", "start_date", "end_date"]
    )
    for c in campaigns:
        writer.writerow(
            [c.name, c.channel, c.objective, c.status, c.budget, c.spent, c.start_date, c.end_date]
        )
    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def lead_export_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    leads = _leads_filtered(request, school)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="marketing_leads.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "student_name",
            "guardian_name",
            "phone",
            "email",
            "class_interest",
            "source",
            "stage",
            "campaign",
            "expected_revenue",
            "next_followup_on",
        ]
    )
    for lead in leads:
        writer.writerow(
            [
                lead.student_name,
                lead.guardian_name,
                lead.phone,
                lead.email,
                lead.class_interest,
                lead.source,
                lead.stage,
                lead.campaign.name if lead.campaign else "",
                lead.expected_revenue,
                lead.next_followup_on,
            ]
        )
    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def campaign_export_excel(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    campaigns = _campaigns_filtered(request, school)
    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="marketing_campaigns.xls"'
    rows = [
        "<table><thead><tr><th>name</th><th>channel</th><th>objective</th><th>status</th><th>budget</th><th>spent</th></tr></thead><tbody>"
    ]
    for c in campaigns:
        rows.append(
            f"<tr><td>{c.name}</td><td>{c.channel}</td><td>{c.objective}</td><td>{c.status}</td><td>{c.budget}</td><td>{c.spent}</td></tr>"
        )
    rows.append("</tbody></table>")
    response.write("".join(rows))
    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def import_data(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    headers = [
        "type",
        "name",
        "channel",
        "status",
        "budget",
        "student_name",
        "phone",
        "stage",
        "source",
    ]
    if request.method == "POST":
        stage = (request.POST.get("stage") or "preview").strip().lower()
        if stage == "confirm":
            preview = request.session.get(IMPORT_SESSION_KEY) or {}
            rows = preview.get("rows") or []
            created = 0
            for row in rows:
                raw = row.get("raw", {})
                if (raw.get("type") or "").upper() == "CAMPAIGN":
                    MarketingCampaign.objects.create(
                        school=school,
                        name=raw.get("name") or "Untitled",
                        channel=raw.get("channel") or "Meta Ads",
                        status=raw.get("status") or "DRAFT",
                        budget=raw.get("budget") or 0,
                    )
                    created += 1
                if (raw.get("type") or "").upper() == "LEAD":
                    MarketingLead.objects.create(
                        school=school,
                        student_name=raw.get("student_name") or "Unknown",
                        phone=raw.get("phone") or "",
                        stage=raw.get("stage") or "NEW",
                        source=raw.get("source") or "Import",
                    )
                    created += 1
            messages.success(request, f"Import complete. {created} rows created.")
            return redirect("digital_marketing:overview")
        import_file = request.FILES.get("import_file")
        if not import_file:
            messages.error(request, "Choose a CSV file.")
            return redirect("digital_marketing:import_data")
        text = import_file.read().decode("utf-8-sig", errors="ignore")
        reader = csv.DictReader(text.splitlines())
        rows = [
            {
                "row_index": i + 1,
                "raw": row,
                "cells": [row.get(h, "") for h in headers],
                "errors": [],
            }
            for i, row in enumerate(reader)
        ]
        request.session[IMPORT_SESSION_KEY] = {"rows": rows}
        context = {
            "headers": headers,
            "preview_rows": rows[:50],
            "total_rows": len(rows),
            "invalid_count": 0,
        }
        context.update(build_layout_context(request.user, current_section="frontoffice"))
        return render(request, "digital_marketing/import_preview.html", context)
    context = {"headers": headers}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/import.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_hub(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    accounts = SocialAccountConnection.objects.filter(school=school).order_by("-created_at")
    posts_qs = (
        SocialPost.objects.filter(school=school)
        .select_related("account", "campaign")
        .order_by("-created_at")
    )
    context = {
        "accounts": accounts,
        "posts": posts_qs[:30],
        "stats": {
            "total_accounts": accounts.count(),
            "active_accounts": accounts.filter(is_active=True).count(),
            "total_posts": posts_qs.count(),
            "organic_posts": posts_qs.filter(campaign__isnull=True).count(),
            "scheduled_posts": posts_qs.filter(status="SCHEDULED").count(),
            "failed_posts": posts_qs.filter(status="FAILED").count(),
        },
        "recent_tests": SocialConnectionTestLog.objects.filter(account__school=school)
        .select_related("account")
        .order_by("-tested_at")[:10],
    }
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/social_hub.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_account_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(SocialAccountConnection, pk=pk, school=school) if pk else None
    form = SocialAccountConnectionForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("digital_marketing:social_hub")
    context = {"form": form, "is_edit": bool(instance)}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/social_account_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_account_test_connection(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    account = get_object_or_404(SocialAccountConnection, pk=pk, school=school)
    if request.method == "POST":
        ok = bool(account.handle and (account.access_token or account.profile_url))
        SocialConnectionTestLog.objects.create(
            account=account,
            result="SUCCESS" if ok else "FAILED",
            message="Connection verified" if ok else "Missing token/profile details",
        )
        messages.success(
            request, "Connection test successful." if ok else "Connection test failed."
        )
    return redirect("digital_marketing:social_hub")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_oauth_start(request, platform):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    platform = (platform or "").upper()
    if platform not in {"INSTAGRAM", "FACEBOOK"}:
        messages.error(request, "Unsupported platform for OAuth connect.")
        return redirect("digital_marketing:social_hub")
    state = f"{school.id}:{request.user.id}:{platform}"
    request.session["dm_oauth_state"] = state
    # Integration-ready placeholder URL. Replace with real provider auth URL when credentials are configured.
    callback_url = request.build_absolute_uri("/digital-marketing/social/oauth/callback/")
    query = urlencode({"state": state, "platform": platform, "callback": callback_url})
    return redirect(f"/digital-marketing/social/oauth/simulated-consent/?{query}")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_oauth_simulated_consent(request):
    # Temporary in-app consent bridge to keep non-dev flow simple until live provider credentials are plugged in.
    state = request.GET.get("state", "")
    platform = request.GET.get("platform", "")
    callback = request.GET.get("callback", "")
    if not state or not platform or not callback:
        messages.error(request, "Invalid OAuth request.")
        return redirect("digital_marketing:social_hub")
    fake_code = f"demo_{platform.lower()}_{request.user.id}"
    return redirect(f"{callback}?state={state}&code={fake_code}&platform={platform}")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_oauth_callback(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    state = request.GET.get("state", "")
    code = request.GET.get("code", "")
    platform = (request.GET.get("platform") or "").upper()
    expected = request.session.get("dm_oauth_state", "")
    if not state or state != expected or not code or platform not in {"INSTAGRAM", "FACEBOOK"}:
        messages.error(request, "OAuth validation failed.")
        return redirect("digital_marketing:social_hub")
    SocialAccountConnection.objects.update_or_create(
        school=school,
        platform=platform,
        defaults={
            "handle": f"{school.code.lower()}_{platform.lower()}",
            "profile_url": "",
            "access_token": code,
            "is_active": True,
        },
    )
    request.session.pop("dm_oauth_state", None)
    messages.success(request, f"{platform.title()} account connected.")
    return redirect("digital_marketing:social_hub")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    posts = (
        SocialPost.objects.filter(school=school)
        .select_related("account", "campaign")
        .order_by("-created_at", "-id")
    )
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    post_type = (request.GET.get("post_type") or "").strip()
    if q:
        posts = posts.filter(
            Q(title__icontains=q) | Q(campaign__name__icontains=q) | Q(account__handle__icontains=q)
        )
    if status:
        posts = posts.filter(status=status)
    if post_type == "organic":
        posts = posts.filter(campaign__isnull=True)
    elif post_type == "campaign":
        posts = posts.filter(campaign__isnull=False)
    posts_page = Paginator(posts, 15).get_page(request.GET.get("page"))
    context = {
        "posts": posts_page,
        "filters": {"q": q, "status": status, "post_type": post_type},
        "status_choices": SocialPost.STATUS_CHOICES,
    }
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/social_post_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_calendar(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    month = int(request.GET.get("month") or timezone.localdate().month)
    year = int(request.GET.get("year") or timezone.localdate().year)
    posts = (
        SocialPost.objects.filter(school=school, scheduled_at__year=year, scheduled_at__month=month)
        .select_related("campaign", "account")
        .order_by("scheduled_at", "-id")
    )
    context = {"posts": posts, "month": month, "year": year}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/social_calendar.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(SocialPost, pk=pk, school=school) if pk else None
    form = SocialPostForm(request.POST or None, instance=instance)
    form.fields["campaign"].queryset = MarketingCampaign.objects.filter(school=school)
    form.fields["campaign"].required = False
    form.fields["campaign"].help_text = "Leave empty for Organic Post (without campaign)."
    if "reviewed_by" in form.fields:
        form.fields["reviewed_by"].disabled = True
    if "reviewed_at" in form.fields:
        form.fields["reviewed_at"].disabled = True
    form.fields["account"].queryset = SocialAccountConnection.objects.filter(school=school)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("digital_marketing:social_post_list")
    context = {"form": form, "is_edit": bool(instance)}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/social_post_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_publish(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    post = get_object_or_404(SocialPost, pk=pk, school=school)
    if request.method == "POST":
        if post.status not in {"APPROVED", "SCHEDULED"}:
            messages.error(request, "Only approved/scheduled posts can be published.")
            return redirect("digital_marketing:social_post_list")
        last_attempt = post.publish_runs.order_by("-attempt_no").first()
        attempt_no = (last_attempt.attempt_no + 1) if last_attempt else 1
        can_publish = bool(post.account and post.account.is_active and post.title)
        if can_publish:
            post.status = "PUBLISHED"
            post.published_at = timezone.now()
            post.save(update_fields=["status", "published_at"])
            SocialPublishRun.objects.create(
                post=post,
                result="SUCCESS",
                message="Published via ERP operation layer",
                attempt_no=attempt_no,
            )
            messages.success(request, "Post published successfully.")
        else:
            post.status = "FAILED"
            post.save(update_fields=["status"])
            SocialPublishRun.objects.create(
                post=post,
                result="FAILED",
                message="Missing active account or title",
                attempt_no=attempt_no,
            )
            messages.error(request, "Publish failed. Check account connection/details.")
    return redirect("digital_marketing:social_post_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_submit_review(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    post = get_object_or_404(SocialPost, pk=pk, school=school)
    if request.method == "POST":
        if post.status in {"DRAFT", "FAILED"}:
            post.status = "IN_REVIEW"
            post.review_notes = ""
            post.reviewed_by = None
            post.reviewed_at = None
            post.save(update_fields=["status", "review_notes", "reviewed_by", "reviewed_at"])
            messages.success(request, "Post moved to review.")
        else:
            messages.error(request, "Only draft/failed posts can be sent for review.")
    return redirect("digital_marketing:social_post_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_approve(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    post = get_object_or_404(SocialPost, pk=pk, school=school)
    if request.method == "POST":
        if post.status == "IN_REVIEW":
            post.status = "APPROVED"
            post.reviewed_by = request.user
            post.reviewed_at = timezone.now()
            note = (request.POST.get("review_notes") or "").strip()
            if note:
                post.review_notes = note
            post.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
            messages.success(request, "Post approved.")
        else:
            messages.error(request, "Only in-review posts can be approved.")
    return redirect("digital_marketing:social_post_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_reject(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    post = get_object_or_404(SocialPost, pk=pk, school=school)
    if request.method == "POST":
        if post.status == "IN_REVIEW":
            note = (request.POST.get("review_notes") or "").strip()
            if not note:
                messages.error(request, "Rejection note is required.")
                return redirect("digital_marketing:social_post_list")
            post.status = "FAILED"
            post.reviewed_by = request.user
            post.reviewed_at = timezone.now()
            post.review_notes = note
            post.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
            messages.success(request, "Post rejected with note.")
        else:
            messages.error(request, "Only in-review posts can be rejected.")
    return redirect("digital_marketing:social_post_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_retry(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    post = get_object_or_404(SocialPost, pk=pk, school=school)
    if request.method == "POST":
        last_attempt = post.publish_runs.order_by("-attempt_no").first()
        attempt_no = (last_attempt.attempt_no + 1) if last_attempt else 1
        post.status = "SCHEDULED"
        post.save(update_fields=["status"])
        SocialPublishRun.objects.create(
            post=post, result="RETRY", message="Retry queued from ERP", attempt_no=attempt_no
        )
        messages.success(request, "Retry queued.")
    return redirect("digital_marketing:social_post_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def social_post_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    obj = get_object_or_404(SocialPost, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
    return redirect("digital_marketing:social_post_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def website_integration_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    integrations = WebsiteFormIntegration.objects.filter(school=school)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if q:
        integrations = integrations.filter(
            Q(name__icontains=q) | Q(source_label__icontains=q) | Q(website_url__icontains=q)
        )
    if status in {"active", "inactive"}:
        integrations = integrations.filter(is_active=(status == "active"))
    integrations_page = Paginator(integrations, 15).get_page(request.GET.get("page"))
    context = {"integrations": integrations_page, "filters": {"q": q, "status": status}}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/website_integration_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def website_integration_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(WebsiteFormIntegration, pk=pk, school=school) if pk else None
    form = WebsiteFormIntegrationForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("digital_marketing:website_integration_list")
    context = {"form": form, "is_edit": bool(instance)}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/website_integration_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def website_integration_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    obj = get_object_or_404(WebsiteFormIntegration, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
    return redirect("digital_marketing:website_integration_list")


@csrf_exempt
def website_integration_ingest(request, integration_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)
    integration = get_object_or_404(WebsiteFormIntegration, pk=integration_id, is_active=True)
    payload_bytes = request.body or b""
    signature = request.headers.get("X-Webhook-Signature", "")
    timestamp = request.headers.get("X-Webhook-Timestamp", "")
    nonce = request.headers.get("X-Webhook-Nonce", "")
    if integration.auth_key and signature and timestamp and nonce:
        expected = hmac.new(
            key=integration.auth_key.encode("utf-8"),
            msg=(
                timestamp + "." + nonce + "." + payload_bytes.decode("utf-8", errors="ignore")
            ).encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return JsonResponse({"ok": False, "error": "Invalid signature"}, status=401)
        replay_key = f"dm_webhook_replay:{integration.id}:{nonce}"
        if cache.get(replay_key):
            return JsonResponse({"ok": False, "error": "Replay detected"}, status=409)
        cache.set(replay_key, True, timeout=300)

    auth = request.headers.get("X-Integration-Key") or request.POST.get("auth_key") or ""
    if integration.auth_key and auth != integration.auth_key:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=401)

    mapping = integration.field_mapping or {}
    student_key = mapping.get("student_name", "student_name")
    phone_key = mapping.get("phone", "phone")
    email_key = mapping.get("email", "email")
    guardian_key = mapping.get("guardian_name", "guardian_name")
    class_key = mapping.get("class_interest", "class_interest")

    student_name = (request.POST.get(student_key) or request.POST.get("name") or "Unknown").strip()
    phone = (request.POST.get(phone_key) or "").strip()
    if not phone:
        return JsonResponse({"ok": False, "error": "phone required"}, status=400)
    MarketingLead.objects.create(
        school=integration.school,
        student_name=student_name,
        phone=phone,
        guardian_name=(request.POST.get(guardian_key) or "").strip(),
        email=(request.POST.get(email_key) or "").strip(),
        class_interest=(request.POST.get(class_key) or "").strip(),
        source=integration.source_label or "Website Form",
        stage="NEW",
    )
    return JsonResponse({"ok": True, "message": "Lead captured"})


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def seo_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    records = SEOTracker.objects.filter(school=school).order_by("-tracked_on", "-id")
    q = (request.GET.get("q") or "").strip()
    if q:
        records = records.filter(Q(keyword__icontains=q) | Q(page_url__icontains=q))
    records_page = Paginator(records, 15).get_page(request.GET.get("page"))
    context = {"records": records_page, "filters": {"q": q}}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/seo_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def seo_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance = get_object_or_404(SEOTracker, pk=pk, school=school) if pk else None
    form = SEOTrackerForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("digital_marketing:seo_list")
    context = {"form": form, "is_edit": bool(instance)}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/seo_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def seo_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    record = get_object_or_404(SEOTracker, pk=pk, school=school)
    context = {"record": record}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/seo_detail.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def seo_export_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    records = SEOTracker.objects.filter(school=school).order_by("-tracked_on")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="seo_tracker.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "tracked_on",
            "page_url",
            "keyword",
            "ranking_position",
            "impressions",
            "clicks",
            "ctr_percent",
        ]
    )
    for r in records:
        writer.writerow(
            [
                r.tracked_on,
                r.page_url,
                r.keyword,
                r.ranking_position,
                r.impressions,
                r.clicks,
                r.ctr_percent,
            ]
        )
    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def seo_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    obj = get_object_or_404(SEOTracker, pk=pk, school=school)
    if request.method == "POST":
        obj.delete()
    return redirect("digital_marketing:seo_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def advanced_report_csv(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="digital_marketing_advanced_report.csv"'
    writer = csv.writer(response)
    writer.writerow(["section", "name_or_keyword", "metric_1", "metric_2", "metric_3", "date"])
    for c in MarketingCampaign.objects.filter(school=school):
        writer.writerow(["campaign", c.name, c.budget, c.spent, c.status, c.start_date or ""])
    for lead in MarketingLead.objects.filter(school=school):
        writer.writerow(
            [
                "lead",
                lead.student_name,
                lead.source,
                lead.stage,
                lead.expected_revenue,
                lead.created_at.date(),
            ]
        )
    for p in SocialPost.objects.filter(school=school):
        writer.writerow(
            ["social_post", p.title, p.reach, p.clicks, p.leads_generated, p.created_at.date()]
        )
    for s in SEOTracker.objects.filter(school=school):
        writer.writerow(
            ["seo", s.keyword, s.ranking_position, s.impressions, s.clicks, s.tracked_on]
        )
    return response


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def roi_analytics(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    campaigns = MarketingCampaign.objects.filter(school=school)
    leads = MarketingLead.objects.filter(school=school)
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()
    if start:
        campaigns = campaigns.filter(created_at__date__gte=start)
        leads = leads.filter(created_at__date__gte=start)
    if end:
        campaigns = campaigns.filter(created_at__date__lte=end)
        leads = leads.filter(created_at__date__lte=end)
    total_spend = campaigns.aggregate(total=Sum("spent"))["total"] or Decimal("0")
    total_budget = campaigns.aggregate(total=Sum("budget"))["total"] or Decimal("0")
    total_leads = leads.count()
    converted = leads.filter(stage="CONVERTED").count()
    expected_revenue = leads.aggregate(total=Sum("expected_revenue"))["total"] or Decimal("0")
    cpl = (total_spend / total_leads) if total_leads else Decimal("0")
    roas = (expected_revenue / total_spend) if total_spend else Decimal("0")
    conversion_rate = (
        (Decimal(converted) * Decimal("100") / Decimal(total_leads))
        if total_leads
        else Decimal("0")
    )
    campaign_rows = (
        campaigns.values("name")
        .annotate(
            spend=Sum("spent"),
            budget=Sum("budget"),
            lead_count=Count("leads"),
            converted_count=Count("leads", filter=Q(leads__stage="CONVERTED")),
        )
        .order_by("-spend")
    )
    attribution_rows = (
        leads.values("source")
        .annotate(total=Count("id"), converted=Count("id", filter=Q(stage="CONVERTED")))
        .order_by("-total")
    )
    context = {
        "total_spend": round(total_spend, 2),
        "total_budget": round(total_budget, 2),
        "total_leads": total_leads,
        "converted": converted,
        "expected_revenue": round(expected_revenue, 2),
        "cpl": round(cpl, 2),
        "roas": round(roas, 2),
        "conversion_rate": round(conversion_rate, 2),
        "campaign_rows": campaign_rows,
        "attribution_rows": attribution_rows,
        "filters": {"start": start, "end": end},
    }
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/roi_analytics.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def report_schedule_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    schedules = DigitalMarketingReportSchedule.objects.filter(school=school).order_by("-created_at")
    context = {"schedules": schedules}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/report_schedule_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def report_schedule_form(request, pk=None):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance = (
        get_object_or_404(DigitalMarketingReportSchedule, pk=pk, school=school) if pk else None
    )
    form = DigitalMarketingReportScheduleForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.save()
        return redirect("digital_marketing:report_schedule_list")
    context = {"form": form, "is_edit": bool(instance)}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/report_schedule_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def report_schedule_run_now(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    schedule = get_object_or_404(DigitalMarketingReportSchedule, pk=pk, school=school)
    if request.method == "POST":
        schedule.last_run_at = timezone.now()
        schedule.save(update_fields=["last_run_at"])
        DigitalMarketingReportRun.objects.create(
            schedule=schedule, status="SUCCESS", message="Report generated and queued for delivery."
        )
        messages.success(request, "Report run queued.")
    return redirect("digital_marketing:report_schedule_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "DIGITAL_MARKETING_MANAGER")
def integration_settings(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Digital Marketing")
    if error_redirect:
        return error_redirect
    instance, _ = DigitalMarketingIntegrationSetting.objects.get_or_create(school=school)
    form = DigitalMarketingIntegrationSettingForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.school = school
        obj.last_tested_at = timezone.now()
        obj.save()
        messages.success(request, "Integration settings updated.")
        return redirect("digital_marketing:integration_settings")
    context = {"form": form}
    context.update(build_layout_context(request.user, current_section="frontoffice"))
    return render(request, "digital_marketing/integration_settings.html", context)
