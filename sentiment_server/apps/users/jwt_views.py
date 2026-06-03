from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenRefreshView
from .domain.jwt_cookies import read_refresh_token_from_cookie

User = get_user_model()


class CookieAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """从 HttpOnly cookie 读取 refresh token，并检查用户状态。"""

    refresh = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        cookie_refresh = read_refresh_token_from_cookie(
            self.context.get("request", None)
        )
        attrs["refresh"] = cookie_refresh or ""
        if not attrs.get("refresh"):
            raise serializers.ValidationError({"refresh": "未提供刷新令牌"})

        refresh = self.token_class(attrs["refresh"])
        user_id = refresh.get("user_id")
        user = User.objects.filter(pk=user_id).first()
        if not user or user.status != 1:
            raise AuthenticationFailed(
                "No active account found", code="no_active_account"
            )

        return super().validate(attrs)


class CookieAwareTokenRefreshView(TokenRefreshView):
    serializer_class = CookieAwareTokenRefreshSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == 200 and response.data.get("refresh"):
            from .domain.jwt_cookies import set_refresh_token_cookie

            set_refresh_token_cookie(response, response.data["refresh"])
            # Remove refresh token from response body — sent via HttpOnly cookie instead
            response.data.pop("refresh", None)
        return response
