from django.urls import path
from django.contrib.auth import views as auth_views

from .views import activate_invitation, dashboard, login_verify, login_view, logout_view
from .views_sso import sso_google_callback, sso_google_start
from .views_profile import profile_edit, profile_view
from .views_register import register_placeholder

urlpatterns = [
    path("", login_view, name="login"),
    path("login/", login_view, name="login-page"),
    path("login/verify/", login_verify, name="login-verify"),
    path("sso/google/start/", sso_google_start, name="sso-google-start"),
    path("sso/google/callback/", sso_google_callback, name="sso-google-callback"),
    path("dashboard/", dashboard, name="dashboard"),
    path("logout/", logout_view, name="logout"),
    path("activate/<uuid:token>/", activate_invitation, name="activate-invitation"),

    path("profile/", profile_view, name="profile"),
    path("profile/edit/", profile_edit, name="profile-edit"),

    # Legacy demo link: keep a real page instead of 404.
    path("register.html", register_placeholder, name="register-placeholder"),

    path("password-reset/", auth_views.PasswordResetView.as_view(template_name="accounts/password_reset_form.html"), name="password_reset"),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="accounts/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
