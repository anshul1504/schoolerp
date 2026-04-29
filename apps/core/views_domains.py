from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context
from apps.schools.models import School, SchoolDomain


def _normalize_domain(raw: str) -> str:
    domain = (raw or "").strip().lower()
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.split("/", 1)[0]
    domain = domain.split(":", 1)[0]
    return domain


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def domain_list(request):
    domains = SchoolDomain.objects.select_related("school").all()
    context = build_layout_context(request.user, current_section="platform")
    context["domains"] = domains[:300]
    context["schools"] = School.objects.filter(is_active=True).order_by("name")
    return render(request, "platform/domains_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def domain_create(request):
    schools = School.objects.filter(is_active=True).order_by("name")
    if request.method == "POST":
        school_id = (request.POST.get("school_id") or "").strip()
        domain = _normalize_domain(request.POST.get("domain") or "")
        is_primary = request.POST.get("is_primary") == "on"
        is_active = request.POST.get("is_active") == "on"

        if (
            not school_id.isdigit()
            or not School.objects.filter(id=int(school_id), is_active=True).exists()
        ):
            messages.error(request, "Valid school is required.")
        elif not domain:
            messages.error(request, "Domain is required.")
        elif SchoolDomain.objects.filter(domain=domain).exists():
            messages.error(request, "That domain is already mapped.")
        else:
            SchoolDomain.objects.create(
                school_id=int(school_id), domain=domain, is_primary=is_primary, is_active=is_active
            )
            messages.success(request, "Domain mapped.")
            return redirect("/platform/domains/")

    context = build_layout_context(request.user, current_section="platform")
    context["schools"] = schools
    context["mode"] = "create"
    return render(request, "platform/domains_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def domain_update(request, id):
    obj = get_object_or_404(SchoolDomain.objects.select_related("school"), id=id)
    schools = School.objects.filter(is_active=True).order_by("name")
    if request.method == "POST":
        school_id = (request.POST.get("school_id") or "").strip()
        domain = _normalize_domain(request.POST.get("domain") or obj.domain)
        is_primary = request.POST.get("is_primary") == "on"
        is_active = request.POST.get("is_active") == "on"

        if (
            not school_id.isdigit()
            or not School.objects.filter(id=int(school_id), is_active=True).exists()
        ):
            messages.error(request, "Valid school is required.")
        elif not domain:
            messages.error(request, "Domain is required.")
        elif SchoolDomain.objects.filter(domain=domain).exclude(id=obj.id).exists():
            messages.error(request, "That domain is already mapped.")
        else:
            obj.school_id = int(school_id)
            obj.domain = domain
            obj.is_primary = is_primary
            obj.is_active = is_active
            obj.save()
            messages.success(request, "Domain updated.")
            return redirect("/platform/domains/")

    context = build_layout_context(request.user, current_section="platform")
    context.update({"schools": schools, "domain_obj": obj, "mode": "edit"})
    return render(request, "platform/domains_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def domain_delete(request, id):
    obj = get_object_or_404(SchoolDomain, id=id)
    if request.method != "POST":
        messages.error(request, "Invalid delete request.")
        return redirect("/platform/domains/")
    obj.delete()
    messages.success(request, "Domain deleted.")
    return redirect("/platform/domains/")
