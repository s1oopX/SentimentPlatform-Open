from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.captcha import generate_captcha
from apps.users.application.auth.login import login_user
from apps.users.application.auth.logout import logout_user
from apps.users.application.errors import UserServiceError
from apps.users.application.passwords.reset_password import reset_user_password
from apps.users.application.passwords.send_code import send_verification_code
from apps.users.application.registration.register_user import register_user
from apps.users.api.responses import build_error_response
from apps.users.api.serializers.auth import (
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    SendCodeSerializer,
)
from apps.users.api.serializers.profile import UserSerializer
from apps.users.permissions import AuthenticatedUserPermission, PublicUserPermission
from core.request_ip import get_request_ip


class CaptchaView(APIView):
    """
    获取图形验证码
    GET /api/auth/captcha/
    """

    permission_classes = [PublicUserPermission]


    def get(self, _request):
        captcha_key, svg = generate_captcha()
        return Response({"captcha_key": captcha_key, "captcha_svg": svg})


class SendCodeView(APIView):
    """
    发送邮箱验证码
    POST /api/auth/send-code/
    """

    permission_classes = [PublicUserPermission]


    def post(self, request):
        serializer = SendCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            send_verification_code(
                email=serializer.validated_data["email"],
                purpose=serializer.validated_data.get("purpose", "register"),
                client_ip=get_request_ip(request),
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        return Response({"message": "验证码发送成功"})


class RegisterView(APIView):
    """
    用户注册
    POST /api/auth/register/
    """

    permission_classes = [PublicUserPermission]


    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = register_user(
                validated_data=serializer.validated_data,
                avatar_file=request.FILES.get("avatar"),
                client_ip=get_request_ip(request),
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        return Response(
            {"message": "注册成功", "user_id": user.id}, status=status.HTTP_201_CREATED
        )


class LoginView(APIView):
    """
    用户登录
    POST /api/auth/login/
    """

    permission_classes = [PublicUserPermission]


    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            login_result = login_user(
                email=serializer.validated_data["email"],
                phone=serializer.validated_data["phone"],
                password=serializer.validated_data["password"],
                client_ip=get_request_ip(request),
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        from apps.users.domain.jwt_cookies import set_refresh_token_cookie

        response = Response(
            {"message": login_result["message"], "access_token": login_result["access_token"], "user": UserSerializer(login_result["user"]).data}
        )
        set_refresh_token_cookie(response, login_result["refresh_token"])
        return response


class ResetPasswordView(APIView):
    """
    重置密码
    POST /api/auth/reset-password/
    """

    permission_classes = [PublicUserPermission]


    def post(self, request):
        serializer = ResetPasswordSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            reset_user_password(
                email=serializer.validated_data["email"],
                code=serializer.validated_data["code"],
                new_password=serializer.validated_data["new_password"],
                client_ip=get_request_ip(request),
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        return Response({"message": "密码重置成功"})


class LogoutView(APIView):
    """
    用户登出
    POST /api/auth/logout/
    """

    permission_classes = [AuthenticatedUserPermission]

    def post(self, request):
        from apps.users.domain.jwt_cookies import (
            clear_refresh_token_cookie,
            read_refresh_token_from_cookie,
        )

        refresh_token = read_refresh_token_from_cookie(request)

        try:
            logout_user(
                user=request.user,
                refresh_token=refresh_token,
                client_ip=get_request_ip(request),
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        response = Response({"message": "登出成功"})
        clear_refresh_token_cookie(response)
        return response
