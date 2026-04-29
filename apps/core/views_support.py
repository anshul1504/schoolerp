from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import SupportTicket, SupportTicketMessage
from apps.core.permissions import permission_required, role_required
from apps.core.ui import build_layout_context
from apps.schools.models import School


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def support_ticket_list(request):
    qs = SupportTicket.objects.select_related("school", "created_by", "assigned_to").all()

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    priority = (request.GET.get("priority") or "").strip().upper()
    school_id = (request.GET.get("school_id") or "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(requester_email__icontains=q)
        )
    if status in dict(SupportTicket.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if priority in dict(SupportTicket.PRIORITY_CHOICES):
        qs = qs.filter(priority=priority)
    if school_id.isdigit():
        qs = qs.filter(school_id=int(school_id))

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "tickets": qs[:200],
            "schools": School.objects.filter(is_active=True).order_by("name"),
            "filters": {"q": q, "status": status, "priority": priority, "school_id": school_id},
            "status_choices": SupportTicket.STATUS_CHOICES,
            "priority_choices": SupportTicket.PRIORITY_CHOICES,
        }
    )
    return render(request, "platform/support_ticket_list.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def support_ticket_create(request):
    schools = School.objects.filter(is_active=True).order_by("name")
    agents = User.objects.filter(role="SUPER_ADMIN", is_active=True).order_by("username")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        status = (request.POST.get("status") or "OPEN").strip().upper()
        priority = (request.POST.get("priority") or "NORMAL").strip().upper()
        school_id = (request.POST.get("school_id") or "").strip()
        assigned_to_id = (request.POST.get("assigned_to_id") or "").strip()
        requester_email = (request.POST.get("requester_email") or "").strip()
        requester_phone = (request.POST.get("requester_phone") or "").strip()

        if not title:
            messages.error(request, "Title is required.")
        elif status not in dict(SupportTicket.STATUS_CHOICES) or priority not in dict(
            SupportTicket.PRIORITY_CHOICES
        ):
            messages.error(request, "Invalid status/priority.")
        else:
            ticket = SupportTicket.objects.create(
                title=title,
                description=description,
                status=status,
                priority=priority,
                school_id=int(school_id) if school_id.isdigit() else None,
                assigned_to_id=int(assigned_to_id) if assigned_to_id.isdigit() else None,
                created_by=request.user,
                requester_email=requester_email,
                requester_phone=requester_phone,
            )
            SupportTicketMessage.objects.create(
                ticket=ticket, author=request.user, body="Ticket created.", is_internal=True
            )
            messages.success(request, "Ticket created.")
            return redirect(f"/platform/support/{ticket.id}/")

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "mode": "create",
            "schools": schools,
            "agents": agents,
            "status_choices": SupportTicket.STATUS_CHOICES,
            "priority_choices": SupportTicket.PRIORITY_CHOICES,
        }
    )
    return render(request, "platform/support_ticket_form.html", context)


@role_required("SUPER_ADMIN")
@permission_required("platform.view")
def support_ticket_detail(request, id):
    ticket = get_object_or_404(
        SupportTicket.objects.select_related("school", "created_by", "assigned_to"), id=id
    )
    messages_qs = ticket.messages.select_related("author").all()

    schools = School.objects.filter(is_active=True).order_by("name")
    agents = User.objects.filter(role="SUPER_ADMIN", is_active=True).order_by("username")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "add_message":
            body = (request.POST.get("body") or "").strip()
            is_internal = request.POST.get("is_internal") == "on"
            if not body:
                messages.error(request, "Message body is required.")
            else:
                SupportTicketMessage.objects.create(
                    ticket=ticket, author=request.user, body=body, is_internal=is_internal
                )
                messages.success(request, "Message added.")
            return redirect(f"/platform/support/{ticket.id}/")

        if action == "update_ticket":
            status = (request.POST.get("status") or ticket.status).strip().upper()
            priority = (request.POST.get("priority") or ticket.priority).strip().upper()
            assigned_to_id = (request.POST.get("assigned_to_id") or "").strip()
            school_id = (request.POST.get("school_id") or "").strip()

            if status not in dict(SupportTicket.STATUS_CHOICES) or priority not in dict(
                SupportTicket.PRIORITY_CHOICES
            ):
                messages.error(request, "Invalid status/priority.")
                return redirect(f"/platform/support/{ticket.id}/")

            ticket.status = status
            ticket.priority = priority
            ticket.assigned_to_id = int(assigned_to_id) if assigned_to_id.isdigit() else None
            ticket.school_id = int(school_id) if school_id.isdigit() else None

            now = timezone.now()
            if status == "RESOLVED" and ticket.resolved_at is None:
                ticket.resolved_at = now
            if status == "CLOSED" and ticket.closed_at is None:
                ticket.closed_at = now
            ticket.save()
            SupportTicketMessage.objects.create(
                ticket=ticket, author=request.user, body="Ticket updated.", is_internal=True
            )
            messages.success(request, "Ticket updated.")
            return redirect(f"/platform/support/{ticket.id}/")

        messages.error(request, "Invalid action.")
        return redirect(f"/platform/support/{ticket.id}/")

    context = build_layout_context(request.user, current_section="platform")
    context.update(
        {
            "ticket": ticket,
            "ticket_messages": messages_qs,
            "schools": schools,
            "agents": agents,
            "status_choices": SupportTicket.STATUS_CHOICES,
            "priority_choices": SupportTicket.PRIORITY_CHOICES,
        }
    )
    return render(request, "platform/support_ticket_detail.html", context)
