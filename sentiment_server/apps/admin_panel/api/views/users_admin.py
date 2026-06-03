from rest_framework import status
from rest_framework.response import Response

from apps.admin_panel.api.responses import (
    StandardResultsSetPagination,
    build_service_error_response,
)
from apps.admin_panel.api.serializers import UserAdminSerializer
from apps.admin_panel.api.views.base import AdminOnlyAPIView, get_required_reason
from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.application.users_admin.commands import (
    toggle_admin_user_status_command,
    update_admin_user_role_command,
)
from apps.admin_panel.application.users_admin.queries import (
    build_user_detail_response,
    build_user_list_response,
)
from apps.admin_panel.infra.audit_logs import create_operation_log
from core.request_ip import get_request_ip


def _get_user_patch_payload(request):
    payload = (
        request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    )
    if hasattr(payload, "pop"):
        payload.pop("reason", None)

    allowed_fields = {"role"}
    unsupported_fields = sorted(set(payload.keys()) - allowed_fields)
    if unsupported_fields:
        raise AdminPanelApplicationError(
            "unsupported_fields",
            f"不支持修改字段：{', '.join(unsupported_fields)}",
            status_code=400,
        )
    if not payload:
        raise AdminPanelApplicationError(
            "empty_update", "请提供要修改的字段", status_code=400
        )
    return payload


class UserManagementView(AdminOnlyAPIView):
    def get(self, request):
        users = build_user_list_response(
            search=request.query_params.get("search", ""),
            role=request.query_params.get("role", ""),
            status_filter=request.query_params.get("status", ""),
            excluded_user_id=request.user.id,
        )

        paginator = StandardResultsSetPagination()
        paginated_users = paginator.paginate_queryset(users, request, view=self)
        return paginator.get_paginated_response(
            UserAdminSerializer(paginated_users, many=True).data
        )


class UserDetailManagementView(AdminOnlyAPIView):
    def patch(self, request, pk):
        user = build_user_detail_response(pk, excluded_user_id=request.user.id)
        if not user:
            return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        try:
            reason = get_required_reason(request)
        except AdminPanelApplicationError as exc:
            return build_service_error_response(exc)

        try:
            payload = _get_user_patch_payload(request)
        except AdminPanelApplicationError as exc:
            return build_service_error_response(exc)

        serializer = UserAdminSerializer(user, data=payload, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_user = update_admin_user_role_command(
                serializer=serializer,
                operator=request.user,
                reason=reason,
                client_ip=get_request_ip(request),
                create_operation_log_fn=create_operation_log,
                error_cls=AdminPanelApplicationError,
            )
        except AdminPanelApplicationError as exc:
            return build_service_error_response(exc)

        return Response(UserAdminSerializer(updated_user).data)


class UserStatusView(AdminOnlyAPIView):
    def put(self, request, pk):
        user = build_user_detail_response(pk, excluded_user_id=request.user.id)
        if not user:
            return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        try:
            reason = get_required_reason(request)
            user = toggle_admin_user_status_command(
                user=user,
                operator=request.user,
                reason=reason,
                client_ip=get_request_ip(request),
                create_operation_log_fn=create_operation_log,
                error_cls=AdminPanelApplicationError,
            )
        except AdminPanelApplicationError as exc:
            return build_service_error_response(exc)

        return Response(UserAdminSerializer(user).data)
