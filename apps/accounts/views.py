from datetime import timedelta
import hashlib
import json
import secrets

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.models import UserInvitation
from apps.accounts.models import UserLoginOTP
from apps.academics.models import AcademicClass
from apps.attendance.models import StudentAttendance
from apps.communication.models import Notice
from apps.core.models import AuthSecurityEvent
from apps.core.ui import build_layout_context, get_role_config
from apps.exams.models import Exam, ExamMark
from apps.fees.models import FeePayment, StudentFeeLedger
from apps.schools.models import School
from apps.schools.models import SchoolSubscription
from apps.accounts.two_factor import requires_email_otp
from apps.students.models import Student
from apps.students.models import Guardian, StudentGuardian
from apps.frontoffice.views import build_frontoffice_dashboard_context


def _client_ip(request) -> str:
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def _ua(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:5000]


def _log_auth_event(request, *, event: str, username: str = "", user=None, success: bool = False, details: str = "") -> None:
    try:
        AuthSecurityEvent.objects.create(
            event=event,
            username=(username or "")[:150],
            ip_address=_client_ip(request)[:64],
            user_agent=_ua(request),
            user_id=getattr(user, "id", None),
            success=bool(success),
            details=(details or "")[:2000],
        )
    except Exception:
        return


def _throttle_hit(key: str, *, limit: int, window_seconds: int) -> bool:
    # Cache-based throttle. Returns True if limit exceeded.
    try:
        current = int(cache.get(key, 0))
    except Exception:
        current = 0
    current += 1
    cache.set(key, current, timeout=window_seconds)
    return current > limit


def _dashboard_data_for_user(user):
    schools = School.objects.all() if user.role == "SUPER_ADMIN" else School.objects.filter(id=user.school_id) if user.school_id else School.objects.none()
    students = Student.objects.all() if user.role == "SUPER_ADMIN" else Student.objects.filter(school_id=user.school_id) if user.school_id else Student.objects.none()
    users = User.objects.all() if user.role == "SUPER_ADMIN" else User.objects.filter(school_id=user.school_id) if user.school_id else User.objects.none()
    classes = AcademicClass.objects.all() if user.role == "SUPER_ADMIN" else AcademicClass.objects.filter(school_id=user.school_id) if user.school_id else AcademicClass.objects.none()
    attendance_entries = StudentAttendance.objects.all() if user.role == "SUPER_ADMIN" else StudentAttendance.objects.filter(session__school_id=user.school_id) if user.school_id else StudentAttendance.objects.none()
    fee_ledgers = StudentFeeLedger.objects.all() if user.role == "SUPER_ADMIN" else StudentFeeLedger.objects.filter(school_id=user.school_id) if user.school_id else StudentFeeLedger.objects.none()
    fee_payments = FeePayment.objects.all() if user.role == "SUPER_ADMIN" else FeePayment.objects.filter(school_id=user.school_id) if user.school_id else FeePayment.objects.none()
    exams = Exam.objects.all() if user.role == "SUPER_ADMIN" else Exam.objects.filter(school_id=user.school_id) if user.school_id else Exam.objects.none()
    exam_marks = ExamMark.objects.all() if user.role == "SUPER_ADMIN" else ExamMark.objects.filter(exam__school_id=user.school_id) if user.school_id else ExamMark.objects.none()

    attendance_rate = 0
    if attendance_entries.exists():
        attendance_rate = int((attendance_entries.filter(status="PRESENT").count() / attendance_entries.count()) * 100)

    outstanding = sum(max((ledger.amount_due - ledger.amount_paid), 0) for ledger in fee_ledgers)

    metrics = [
        {
            "label": "Schools",
            "value": schools.count(),
            "trend": "Active network visibility" if user.role == "SUPER_ADMIN" else "School scope assigned",
            "icon": "dashboard-icon2.png",
            "icon_bg": "bg-blue-600",
            "card_class": "gradient-bg-end-2",
        },
        {
            "label": "Students",
            "value": students.count(),
            "trend": f"{students.filter(is_active=True).count()} active students",
            "icon": "dashboard-icon1.png",
            "icon_bg": "bg-warning-600",
            "card_class": "gradient-bg-end-1",
        },
        {
            "label": "Operations",
            "value": classes.count(),
            "trend": f"{attendance_rate}% attendance | Rs {outstanding} due",
            "icon": "dashboard-icon4.png",
            "icon_bg": "bg-success-600",
            "card_class": "gradient-bg-end-3",
        },
    ]

    insights = []
    if user.role == "SUPER_ADMIN":
        insights = [
            {
                "title": "Network Academic Coverage",
                "body": f"{classes.count()} academic classes, {exams.count()} exams, and {exam_marks.count()} marks entries are visible across the platform.",
            },
            {
                "title": "Platform Snapshot",
                "body": f"{schools.filter(is_active=True).count()} active schools, {fee_payments.count()} collections, and {attendance_entries.count()} attendance entries are currently visible.",
            },
        ]
    else:
        school = schools.first()
        if school:
            insights = [
                {
                    "title": "School Operations Snapshot",
                    "body": f"{classes.count()} classes, {exams.count()} exams, and {fee_payments.count()} collections are active in {school.name}.",
                },
                {
                    "title": "Attendance And Fees",
                    "body": f"Attendance is at {attendance_rate}% and outstanding due stands at Rs {outstanding}.",
                },
            ]

    charts = {
        "attendance_rate": attendance_rate,
        "outstanding": float(outstanding),
        "students_active": float(students.filter(is_active=True).count()),
        "students_total": float(students.count()),
        "schools_active": float(schools.filter(is_active=True).count()),
        "schools_total": float(schools.count()),
    }

    return metrics, insights, charts


def _parent_students_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return Student.objects.none()

    q = Student.objects.none()
    if user.email:
        q = q | Student.objects.filter(
            guardian_links__guardian__email__iexact=user.email,
        )
    if user.username:
        q = q | Student.objects.filter(
            guardian_links__guardian__phone__icontains=user.username,
        )
    full_name = (user.get_full_name() or "").strip()
    if full_name:
        q = q | Student.objects.filter(
            guardian_links__guardian__full_name__iexact=full_name,
        )
    return q.distinct().select_related("school")


def _parent_dashboard_data(user):
    students = _parent_students_for_user(user)
    child_cards = []
    for student in students[:12]:
        attendance_entries = StudentAttendance.objects.filter(student=student)
        fee_ledgers = StudentFeeLedger.objects.filter(student=student)
        exam_marks = ExamMark.objects.filter(student=student)
        notices = Notice.objects.filter(school=student.school, is_published=True, audience__in={"ALL", "STUDENTS", "PARENTS"})

        present_count = attendance_entries.filter(status="PRESENT").count()
        attendance_rate = int((present_count / attendance_entries.count()) * 100) if attendance_entries.exists() else 0
        outstanding = sum(max((ledger.amount_due - ledger.amount_paid), 0) for ledger in fee_ledgers)
        average_marks = round(sum(mark.marks_obtained for mark in exam_marks) / exam_marks.count(), 2) if exam_marks.exists() else 0

        child_cards.append(
            {
                "student": student,
                "attendance_rate": attendance_rate,
                "outstanding": outstanding,
                "average_marks": average_marks,
                "notice_count": notices.count(),
                "latest_notice": notices.first(),
                "class_label": f"{student.class_name} - {student.section}",
            }
        )

    return {
        "child_count": students.count(),
        "child_cards": child_cards,
        "active_children": students.filter(is_active=True).count(),
        "inactive_children": students.filter(is_active=False).count(),
    }


def _student_record_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None

    school_id = getattr(user, "school_id", None)
    candidates = Student.objects.select_related("school")
    if school_id:
        candidates = candidates.filter(school_id=school_id)

    username = (getattr(user, "username", "") or "").strip()
    full_name = (user.get_full_name() or "").strip()

    student = candidates.filter(student_username__iexact=username).first()
    if student:
        return student

    student = candidates.filter(admission_no__iexact=username).first()
    if student:
        return student

    if full_name:
        student = candidates.filter(
            first_name__iexact=full_name.split(" ", 1)[0],
            last_name__iexact=full_name.split(" ", 1)[-1] if " " in full_name else full_name.split(" ", 1)[0],
        ).first()
        if student:
            return student

    return None


def _student_dashboard_data(student):
    attendance_entries = StudentAttendance.objects.filter(student=student)
    fee_ledgers = StudentFeeLedger.objects.filter(student=student)
    exam_marks = ExamMark.objects.filter(student=student)
    notices = Notice.objects.filter(
        school=student.school,
        is_published=True,
        audience__in={"ALL", "STUDENTS"},
    )
    present_count = attendance_entries.filter(status="PRESENT").count()
    attendance_rate = int((present_count / attendance_entries.count()) * 100) if attendance_entries.exists() else 0
    total_due = sum(max((ledger.amount_due - ledger.amount_paid), 0) for ledger in fee_ledgers)
    total_marks = sum(mark.marks_obtained for mark in exam_marks)
    average_marks = round(total_marks / exam_marks.count(), 2) if exam_marks.exists() else 0

    workflow_steps = []
    workflow_steps.append(
        {
            "label": "Profile",
            "status": "Done" if student.first_name and student.admission_no and student.class_name else "Pending",
            "complete": bool(student.first_name and student.admission_no and student.class_name),
            "description": "Your admission profile and class placement are ready.",
            "url": f"/students/{student.slug}/",
        }
    )
    workflow_steps.append(
        {
            "label": "Attendance",
            "status": "Done" if attendance_entries.exists() else "Pending",
            "complete": attendance_entries.exists(),
            "description": "See your attendance pattern and updates from school.",
            "url": f"/students/{student.slug}/history/",
        }
    )
    workflow_steps.append(
        {
            "label": "Fees",
            "status": "Done" if fee_ledgers.exists() else "Pending",
            "complete": fee_ledgers.exists(),
            "description": "Track fee dues and payment cycles.",
            "url": "/fees/",
        }
    )
    workflow_steps.append(
        {
            "label": "Exams",
            "status": "Done" if exam_marks.exists() else "Pending",
            "complete": exam_marks.exists(),
            "description": "Review exam performance and marks entries.",
            "url": "/exams/",
        }
    )
    workflow_steps.append(
        {
            "label": "Notices",
            "status": "Done" if notices.exists() else "Pending",
            "complete": notices.exists(),
            "description": "View published school notices and announcements.",
            "url": "/communication/",
        }
    )

    return {
        "student": student,
        "attendance_rate": attendance_rate,
        "outstanding_due": total_due,
        "average_marks": average_marks,
        "notice_count": notices.count(),
        "latest_notice": notices.first(),
        "workflow_steps": workflow_steps,
        "attendance_entries": attendance_entries.count(),
        "fee_ledger_count": fee_ledgers.count(),
        "exam_marks_count": exam_marks.count(),
    }


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        identifier = (request.POST.get("username") or "").strip()
        password = request.POST.get("password")
        ip = _client_ip(request)

        if _throttle_hit(f"throttle:login:ip:{ip}", limit=40, window_seconds=15 * 60):
            _log_auth_event(request, event="THROTTLED", username=identifier, success=False, details="login ip throttle")
            messages.error(request, "Too many login attempts. Try again later.")
            response = render(request, "accounts/login.html")
            response.status_code = 429
            return response

        if identifier and _throttle_hit(f"throttle:login:identifier:{identifier.lower()}", limit=15, window_seconds=15 * 60):
            _log_auth_event(request, event="THROTTLED", username=identifier, success=False, details="login identifier throttle")
            messages.error(request, "Too many login attempts for this account. Try again later.")
            response = render(request, "accounts/login.html")
            response.status_code = 429
            return response

        ip_key = f"login_failed_ip:{ip}"
        ip_failures = int(cache.get(ip_key, 0))
        if ip_failures >= 25:
            _log_auth_event(request, event="THROTTLED", username=identifier, success=False, details="legacy ip_failures lockout")
            messages.error(request, "Too many failed login attempts from this network. Try again later.")
            response = render(request, "accounts/login.html")
            response.status_code = 429
            return response

        user_obj = User.objects.filter(username=identifier).first()
        if not user_obj and identifier and "@" in identifier:
            user_obj = User.objects.filter(email__iexact=identifier).first()

        username_for_auth = user_obj.username if user_obj else identifier
        if user_obj and user_obj.locked_until and user_obj.locked_until > timezone.now():
            _log_auth_event(request, event="LOGIN_LOCKED", username=username_for_auth, user=user_obj, success=False, details="locked_until active")
            messages.error(request, "Account is temporarily locked due to failed login attempts. Try again later.")
            return render(request, "accounts/login.html")

        user = authenticate(request, username=username_for_auth, password=password)

        if user is not None:
            _log_auth_event(request, event="LOGIN_SUCCESS", username=username_for_auth, user=user, success=True)
            if not user.is_active:
                messages.error(request, "Your account is inactive. Please contact the administrator.")
                return render(request, "accounts/login.html")
            if user.failed_login_attempts or user.locked_until:
                user.failed_login_attempts = 0
                user.locked_until = None
                user.save(update_fields=["failed_login_attempts", "locked_until"])

            cache.delete(ip_key)

            if user.role != "SUPER_ADMIN":
                if not user.school_id:
                    messages.error(request, "Your account is not linked to any school. Contact administrator.")
                    return render(request, "accounts/login.html")
                subscription = SchoolSubscription.objects.select_related("school").filter(school_id=user.school_id).first()
                if not subscription or not subscription.is_valid_access(today=timezone.now().date()):
                    messages.error(request, "Subscription is inactive or expired. Contact SchoolFlow support.")
                    return render(request, "accounts/login.html")

            if requires_email_otp(user):
                code = f"{secrets.randbelow(1000000):06d}"
                otp = UserLoginOTP.objects.create(
                    user=user,
                    code_hash="",
                    expires_at=timezone.now() + timedelta(minutes=10),
                )
                digest = hashlib.sha256(f"{user.id}:{code}:{otp.salt}:{user.password}".encode("utf-8")).hexdigest()
                otp.code_hash = digest
                otp.save(update_fields=["code_hash"])

                request.session["pending_2fa_user_id"] = user.id
                request.session["pending_2fa_otp_id"] = otp.id
                if settings.DEBUG:
                    request.session["pending_2fa_debug_code"] = code
                request.session.set_expiry(15 * 60)
                _log_auth_event(request, event="OTP_SENT", username=user.username, user=user, success=True, details="superadmin otp created")

                if settings.DEBUG:
                    messages.info(request, "Dev mode: verification code is shown on the next screen.")
                    return redirect("login-verify")

                if user.email:
                    subject = "SchoolFlow login verification code"
                    text_body = render_to_string("accounts/otp_email.txt", {"user": user, "code": code})
                    html_body = render_to_string("accounts/otp_email.html", {"user": user, "code": code})
                    try:
                        msg = EmailMultiAlternatives(subject=subject, body=text_body, to=[user.email])
                        msg.attach_alternative(html_body, "text/html")
                        msg.send(fail_silently=False)
                    except Exception:
                        messages.error(request, "Could not send verification code email. Contact administrator.")
                        return render(request, "accounts/login.html")

                return redirect("login-verify")

            login(request, user)
            remember_me = bool(request.POST.get("remember_me"))
            request.session.set_expiry((30 * 24 * 60 * 60) if remember_me else (12 * 60 * 60))
            return redirect("dashboard")

        if user_obj:
            _log_auth_event(request, event="LOGIN_FAIL", username=username_for_auth, user=user_obj, success=False, details="bad password")
            user_obj.failed_login_attempts = min(user_obj.failed_login_attempts + 1, 50)
            if user_obj.failed_login_attempts >= 5:
                user_obj.locked_until = timezone.now() + timedelta(minutes=15)
            user_obj.save(update_fields=["failed_login_attempts", "locked_until"])
        else:
            _log_auth_event(request, event="LOGIN_FAIL", username=identifier, user=None, success=False, details="unknown user")

        cache.set(ip_key, ip_failures + 1, timeout=15 * 60)
        messages.error(request, "Invalid username or password")

    return render(request, "accounts/login.html")


def login_verify(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    user_id = request.session.get("pending_2fa_user_id")
    otp_id = request.session.get("pending_2fa_otp_id")
    if not user_id or not otp_id:
        messages.error(request, "Verification session expired. Please log in again.")
        return redirect("login")

    user = User.objects.filter(id=user_id).first()
    otp = UserLoginOTP.objects.filter(id=otp_id, user_id=user_id).first()
    if not user or not otp:
        messages.error(request, "Verification session invalid. Please log in again.")
        return redirect("login")

    if otp.is_used():
        messages.error(request, "Verification code already used. Please log in again.")
        return redirect("login")

    if otp.is_expired():
        messages.error(request, "Verification code expired. Please log in again.")
        return redirect("login")

    if request.method == "POST":
        ip = _client_ip(request)
        if _throttle_hit(f"throttle:otp_verify:ip:{ip}", limit=60, window_seconds=15 * 60):
            _log_auth_event(request, event="THROTTLED", username=getattr(user, "username", ""), user=user, success=False, details="otp verify ip throttle")
            messages.error(request, "Too many verification attempts. Try again later.")
            response = render(request, "accounts/otp_verify.html")
            response.status_code = 429
            return response

        code = (request.POST.get("code") or "").strip()
        if not code or len(code) != 6 or not code.isdigit():
            messages.error(request, "Enter the 6-digit code.")
            return render(request, "accounts/otp_verify.html")

        digest = hashlib.sha256(f"{user.id}:{code}:{otp.salt}:{user.password}".encode("utf-8")).hexdigest()
        otp.attempts += 1
        if otp.attempts >= 8:
            otp.expires_at = timezone.now()
        otp.save(update_fields=["attempts", "expires_at"])

        if digest != otp.code_hash:
            _log_auth_event(request, event="OTP_VERIFY_FAIL", username=user.username, user=user, success=False, details="invalid otp")
            messages.error(request, "Invalid code.")
            return render(request, "accounts/otp_verify.html")

        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])
        request.session.pop("pending_2fa_user_id", None)
        request.session.pop("pending_2fa_otp_id", None)
        request.session.pop("pending_2fa_debug_code", None)

        _log_auth_event(request, event="OTP_VERIFY_SUCCESS", username=user.username, user=user, success=True)
        login(request, user)
        request.session.set_expiry(12 * 60 * 60)
        return redirect("dashboard")

    context = {}
    if settings.DEBUG and request.session.get("pending_2fa_debug_code"):
        context["debug_code"] = request.session.get("pending_2fa_debug_code")
    return render(request, "accounts/otp_verify.html", context)


@login_required
def dashboard(request):
    if getattr(request.user, "role", None) == "RECEPTIONIST":
        # Keep the canonical dashboard URL, but render the receptionist workspace UI.
        context = build_frontoffice_dashboard_context(request, current_section="frontoffice")
        return render(request, "frontoffice/overview.html", context)

    if getattr(request.user, "role", None) == "PARENT":
        context = build_layout_context(request.user, current_section="dashboard")
        context["dashboard_mode"] = "parent"
        context["parent_dashboard"] = _parent_dashboard_data(request.user)
        return render(request, "accounts/parent_dashboard.html", context)

    if getattr(request.user, "role", None) == "STUDENT":
        student = _student_record_for_user(request.user)
        if student:
            context = build_layout_context(request.user, current_section="dashboard")
            context["dashboard_mode"] = "student"
            context["student_dashboard"] = _student_dashboard_data(student)
            context["student_dashboard"]["student_nav_active"] = "overview"
            return render(request, "accounts/student_dashboard.html", context)

    context = build_layout_context(request.user, current_section="dashboard")
    metrics, insights, charts = _dashboard_data_for_user(request.user)
    context["dashboard_mode"] = "pro"
    context["dashboard_metrics"] = metrics
    context["dashboard_insights"] = insights
    context["dashboard_charts"] = charts
    context["dashboard_charts_json"] = json.dumps(charts)
    return render(request, "dashboard.html", context)


@login_required
def logout_view(request):
    logout(request)
    return render(request, "accounts/logout.html")


def activate_invitation(request, token):
    invitation = UserInvitation.objects.select_related("user", "user__school").filter(token=token).first()

    if not invitation:
        messages.error(request, "Activation link is invalid.")
        return redirect("login")

    if invitation.is_accepted():
        messages.info(request, "This activation link has already been used. Please log in.")
        return redirect("login")

    if invitation.is_expired():
        messages.error(request, "Activation link has expired. Please contact the administrator.")
        return redirect("login")

    if request.user.is_authenticated:
        logout(request)

    if request.method == "POST":
        password = (request.POST.get("password") or "").strip()
        confirm = (request.POST.get("confirm_password") or "").strip()

        if not password:
            messages.error(request, "Password is required.")
        elif password != confirm:
            messages.error(request, "Passwords do not match.")
        else:
            try:
                validate_password(password, invitation.user)
            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(request, error)
                return render(request, "accounts/activate.html", {"invitation": invitation})

            user = invitation.user
            user.set_password(password)
            user.is_active = True
            user.failed_login_attempts = 0
            user.locked_until = None
            user.save(update_fields=["password", "is_active", "failed_login_attempts", "locked_until"])
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["accepted_at"])
            messages.success(request, "Account activated. You can now log in.")
            return redirect("login")

    return render(request, "accounts/activate.html", {"invitation": invitation})
