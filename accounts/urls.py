"""URL routes for authentication endpoints."""

from django.contrib.auth import views as auth_views
from django.urls import path

from .views import auth_ping, login_view, logout_view

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("auth/ping/", auth_ping, name="auth-ping"),
    path("auth/password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "auth/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "auth/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "auth/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
