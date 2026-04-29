from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.permissions import role_required
from apps.core.tenancy import get_selected_school_or_redirect
from apps.core.ui import build_layout_context
from apps.students.models import Student

from .models import Application, CareerEvent, CareerProfile, CounselingSession, University


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def counseling_overview(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    students = Student.objects.filter(school=school)
    applications = Application.objects.filter(student__school=school)
    sessions = CounselingSession.objects.filter(school=school)

    # Data for charts
    app_status_counts = list(applications.values("status").annotate(count=Count("status")))

    # Simple keyword extraction for interests (demo logic)
    interests_raw = CareerProfile.objects.filter(student__school=school).exclude(interests="")
    interests_map = {
        "Engineering": 0,
        "Medical": 0,
        "Management": 0,
        "Design": 0,
        "Abroad": 0,
        "Other": 0,
    }
    for p in interests_raw:
        txt = p.interests.lower()
        if "eng" in txt or "btech" in txt:
            interests_map["Engineering"] += 1
        elif "med" in txt or "doctor" in txt:
            interests_map["Medical"] += 1
        elif "manage" in txt or "bba" in txt:
            interests_map["Management"] += 1
        elif "abroad" in txt or "intl" in txt:
            interests_map["Abroad"] += 1
        else:
            interests_map["Other"] += 1

    import json

    from django.db.models.functions import TruncMonth

    monthly_sessions = list(
        sessions.annotate(month=TruncMonth("scheduled_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    chart_data = {
        "app_status": app_status_counts,
        "interests": [{"label": k, "count": v} for k, v in interests_map.items() if v > 0],
        "monthly_sessions": [
            {"month": str(m["month"])[:7], "count": m["count"]} for m in monthly_sessions
        ],
    }

    context = {
        "school": school,
        "total_students": students.count(),
        "counseled_students": sessions.values("student").distinct().count(),
        "total_applications": applications.count(),
        "accepted_offers": applications.filter(status="ACCEPTED").count(),
        "recent_sessions": sessions.order_by("-scheduled_at")[:5],
        "today_sessions": sessions.filter(scheduled_at__date=timezone.localdate()).order_by(
            "scheduled_at"
        ),
        "upcoming_deadlines": Application.objects.filter(
            student__school=school, deadline__gte=timezone.localdate()
        ).order_by("deadline")[:5],
        "recent_applications": applications.order_by("-applied_on")[:5],
        "upcoming_events": CareerEvent.objects.filter(
            school=school, date__gte=timezone.localdate()
        ).order_by("date")[:5],
        "chart_data_json": json.dumps(chart_data),
    }

    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/overview.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def student_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    students = Student.objects.filter(school=school).prefetch_related("career_profile")
    context = {"students": students, "school": school}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/student_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def student_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    student = get_object_or_404(Student, pk=pk, school=school)
    profile, created = CareerProfile.objects.get_or_create(student=student)

    from apps.career_counseling.forms import CareerProfileForm

    if request.method == "POST":
        form = CareerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            from django.contrib import messages

            messages.success(request, "Career profile updated successfully.")
            return redirect("career_counseling:student_detail", pk=student.pk)
    else:
        form = CareerProfileForm(instance=profile)

    applications = student.university_applications.all()
    sessions = student.counseling_sessions.all()

    context = {
        "student": student,
        "profile": profile,
        "applications": applications,
        "sessions": sessions,
        "school": school,
        "form": form,
    }
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/student_detail.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def application_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    applications = Application.objects.filter(student__school=school).select_related(
        "student", "university"
    )
    context = {"applications": applications, "school": school}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/application_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def session_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    sessions = CounselingSession.objects.filter(school=school).select_related(
        "student", "counselor"
    )
    context = {"sessions": sessions, "school": school}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/session_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def session_add(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    from apps.career_counseling.forms import CounselingSessionForm

    if request.method == "POST":
        form = CounselingSessionForm(request.POST, school=school)
        if form.is_valid():
            from apps.staff.models import StaffMember

            staff = None
            if request.user.email:
                staff = StaffMember.objects.filter(email=request.user.email, school=school).first()
            if not staff:
                # Auto-create a staff record for the counselor to link to the session
                staff = StaffMember.objects.create(
                    school=school,
                    full_name=request.user.get_full_name() or request.user.username,
                    email=request.user.email,
                    staff_role="STAFF",
                    designation="Career Counselor",
                )

            students = form.cleaned_data["students"]
            for student in students:
                session = form.save(commit=False)
                session.pk = None  # create a new instance for each student
                session.school = school
                session.student = student
                session.counselor = staff
                session.save()

            from django.contrib import messages

            messages.success(
                request,
                f"Counseling session scheduled successfully for {students.count()} student(s).",
            )
            return redirect("career_counseling:session_list")
    else:
        form = CounselingSessionForm(school=school)

    context = {"form": form, "school": school, "is_edit": False}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/session_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def session_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    session = get_object_or_404(CounselingSession, pk=pk, school=school)

    # We use a custom form for editing since we don't want to re-select students
    from django import forms

    class SessionEditForm(forms.ModelForm):
        class Meta:
            model = CounselingSession
            fields = [
                "session_type",
                "mode",
                "meeting_link",
                "scheduled_at",
                "duration_minutes",
                "summary",
                "feedback",
                "follow_up_required",
                "is_completed",
            ]
            widgets = {
                "scheduled_at": forms.DateTimeInput(
                    attrs={"type": "datetime-local", "class": "form-control"}
                ),
                "session_type": forms.Select(attrs={"class": "form-select"}),
                "mode": forms.Select(attrs={"class": "form-select"}),
                "meeting_link": forms.URLInput(attrs={"class": "form-control"}),
                "duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
                "summary": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
                "feedback": forms.Textarea(
                    attrs={
                        "class": "form-control",
                        "rows": 3,
                        "placeholder": "Post session feedback...",
                    }
                ),
                "follow_up_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
                "is_completed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            }

    if request.method == "POST":
        form = SessionEditForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            from django.contrib import messages

            messages.success(request, "Session updated successfully.")
            return redirect("career_counseling:session_list")
    else:
        form = SessionEditForm(instance=session)

    context = {"form": form, "school": school, "session": session, "is_edit": True}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/session_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def university_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect

    universities = University.objects.filter(school=school)
    context = {"universities": universities, "school": school}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/university_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def university_add(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    from apps.career_counseling.forms import UniversityForm

    if request.method == "POST":
        form = UniversityForm(request.POST)
        if form.is_valid():
            university = form.save(commit=False)
            university.school = school
            university.save()
            from django.contrib import messages

            messages.success(request, "University added successfully.")
            return redirect("career_counseling:university_list")
    else:
        form = UniversityForm()
    context = {"form": form, "school": school, "is_edit": False}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/university_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def university_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    university = get_object_or_404(University, pk=pk, school=school)
    from apps.career_counseling.forms import UniversityForm

    if request.method == "POST":
        form = UniversityForm(request.POST, instance=university)
        if form.is_valid():
            form.save()
            from django.contrib import messages

            messages.success(request, "University updated successfully.")
            return redirect("career_counseling:university_list")
    else:
        form = UniversityForm(instance=university)
    context = {"form": form, "school": school, "is_edit": True, "university": university}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/university_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def application_add(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    from apps.career_counseling.forms import ApplicationForm

    student_id = request.GET.get("student")
    initial_data = {}
    if student_id:
        initial_data["student"] = student_id
    if request.method == "POST":
        form = ApplicationForm(request.POST, school=school)
        if form.is_valid():
            application = form.save(commit=False)
            # Student needs to be selected in the form or from GET
            if not application.student_id and student_id:
                application.student_id = student_id
            application.save()
            from django.contrib import messages

            messages.success(request, "Application added successfully.")
            return redirect("career_counseling:application_list")
    else:
        form = ApplicationForm(school=school, initial=initial_data)
        # Add student field to form if not already there (it might not be in the form fields)
        from django import forms

        form.fields["student"] = forms.ModelChoiceField(
            queryset=Student.objects.filter(school=school),
            widget=forms.Select(attrs={"class": "form-select"}),
            initial=student_id,
        )
    context = {"form": form, "school": school, "is_edit": False}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/application_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def event_list(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    events = CareerEvent.objects.filter(school=school).order_by("-date")
    context = {"events": events, "school": school}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/event_list.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def event_add(request):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    from apps.career_counseling.forms import CareerEventForm

    if request.method == "POST":
        form = CareerEventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.school = school
            event.save()
            from django.contrib import messages

            messages.success(request, "Event created successfully.")
            return redirect("career_counseling:event_list")
    else:
        form = CareerEventForm()
    context = {"form": form, "school": school, "is_edit": False}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/event_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def university_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    university = get_object_or_404(University, pk=pk, school=school)
    university.delete()
    from django.contrib import messages

    messages.success(request, "University deleted successfully.")
    return redirect("career_counseling:university_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def application_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    application = get_object_or_404(Application, pk=pk, student__school=school)
    from apps.career_counseling.forms import ApplicationForm

    if request.method == "POST":
        form = ApplicationForm(request.POST, instance=application, school=school)
        if form.is_valid():
            form.save()
            from django.contrib import messages

            messages.success(request, "Application updated successfully.")
            return redirect("career_counseling:application_list")
    else:
        form = ApplicationForm(instance=application, school=school)
    context = {"form": form, "school": school, "is_edit": True, "application": application}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/application_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def application_delete(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    application = get_object_or_404(Application, pk=pk, student__school=school)
    application.delete()
    from django.contrib import messages

    messages.success(request, "Application deleted successfully.")
    return redirect("career_counseling:application_list")


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def event_edit(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    event = get_object_or_404(CareerEvent, pk=pk, school=school)
    from apps.career_counseling.forms import CareerEventForm

    if request.method == "POST":
        form = CareerEventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            from django.contrib import messages

            messages.success(request, "Event updated successfully.")
            return redirect("career_counseling:event_list")
    else:
        form = CareerEventForm(instance=event)
    context = {"form": form, "school": school, "is_edit": True, "event": event}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/event_form.html", context)


@login_required
@role_required("SUPER_ADMIN", "SCHOOL_OWNER", "ADMIN", "PRINCIPAL", "CAREER_COUNSELOR")
def event_detail(request, pk):
    school, error_redirect = get_selected_school_or_redirect(request, "Career Counseling")
    if error_redirect:
        return error_redirect
    event = get_object_or_404(CareerEvent, pk=pk, school=school)
    registrations = event.registrations.all().select_related("student")

    from apps.career_counseling.forms import EventRegistrationForm

    if request.method == "POST":
        form = EventRegistrationForm(request.POST, school=school)
        if form.is_valid():
            reg = form.save(commit=False)
            reg.event = event
            reg.save()
            from django.contrib import messages

            messages.success(request, "Student registered for event.")
            return redirect("career_counseling:event_detail", pk=event.pk)
    else:
        form = EventRegistrationForm(school=school)

    context = {"event": event, "registrations": registrations, "form": form, "school": school}
    context.update(build_layout_context(request.user, current_section="career_counseling"))
    return render(request, "career_counseling/event_detail.html", context)
