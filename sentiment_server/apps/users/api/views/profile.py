from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.application.errors import UserServiceError
from apps.users.application.passwords.change_password import change_user_password
from apps.users.application.profile.delete_account import delete_user_account
from apps.users.application.profile.update_profile import update_user_profile
from apps.users.api.responses import build_error_response
from apps.users.api.serializers.auth import (
    ChangePasswordSerializer,
    DeleteAccountSerializer,
)
from apps.users.api.serializers.profile import (
    UserProfileUpdateSerializer,
    UserSerializer,
)
from apps.users.permissions import AuthenticatedUserPermission
from core.request_ip import get_request_ip


class ChangePasswordView(APIView):
    """
    已登录用户修改密码
    POST /api/auth/change-password/
    """

    permission_classes = [AuthenticatedUserPermission]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"user": request.user}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            change_user_password(
                user=request.user,
                old_password=serializer.validated_data["old_password"],
                new_password=serializer.validated_data["new_password"],
                client_ip=get_request_ip(request),
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        return Response({"message": "密码修改成功"})


class UserProfileView(APIView):
    """
    获取/修改用户信息
    GET/PUT /api/auth/profile/
    """

    permission_classes = [AuthenticatedUserPermission]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = update_user_profile(
                user=request.user, validated_data=serializer.validated_data
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        return Response(UserSerializer(user).data)


class DeleteAccountView(APIView):
    """
    注销当前账号
    DELETE /api/auth/delete-account/
    """

    permission_classes = [AuthenticatedUserPermission]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            delete_user_account(
                user=request.user,
                password=serializer.validated_data["password"],
                confirmation=serializer.validated_data["confirmation"],
                client_ip=get_request_ip(request),
            )
        except UserServiceError as exc:
            return build_error_response(exc)

        from apps.users.domain.jwt_cookies import clear_refresh_token_cookie

        response = Response({"message": "账号已注销"})
        clear_refresh_token_cookie(response)
        return response
