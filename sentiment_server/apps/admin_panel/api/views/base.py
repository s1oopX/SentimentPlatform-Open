from rest_framework.views import APIView

from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.users.permissions import IsAdminUserRole


class AdminOnlyAPIView(APIView):
    permission_classes = [IsAdminUserRole]


def get_required_reason(request):
    """Extract and validate the audit `reason` field from an admin request payload.

    Centralized here so that admin endpoints requiring an operation reason share
    a single validation contract (non-empty, max 200 chars).
    """
    raw_reason = request.data.get("reason", "") if hasattr(request.data, "get") else ""
    if isinstance(raw_reason, (list, tuple)):
        raw_reason = raw_reason[0] if raw_reason else ""
    reason = str(raw_reason or "").strip()
    if not reason:
        raise AdminPanelApplicationError(
            "invalid_reason", "请输入操作理由", status_code=400
        )
    if len(reason) > 200:
        raise AdminPanelApplicationError(
            "invalid_reason", "操作理由不能为空且不超过200字", status_code=400
        )
    return reason
