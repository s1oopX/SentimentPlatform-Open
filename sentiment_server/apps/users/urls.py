from django.urls import path

from apps.users.api.views.auth import (
    CaptchaView,
    LoginView,
    LogoutView,
    RegisterView,
    ResetPasswordView,
    SendCodeView,
)
from apps.users.api.views.profile import (
    ChangePasswordView,
    DeleteAccountView,
    UserProfileView,
)
from apps.users.jwt_views import CookieAwareTokenRefreshView

urlpatterns = [
    path("captcha/", CaptchaView.as_view(), name="captcha"),
    path("send-code/", SendCodeView.as_view(), name="send-code"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path(
        "refresh/", CookieAwareTokenRefreshView.as_view(), name="token-refresh"
    ),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("delete-account/", DeleteAccountView.as_view(), name="delete-account"),
    path("profile/", UserProfileView.as_view(), name="profile"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
