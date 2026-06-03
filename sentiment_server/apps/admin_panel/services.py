import logging
import os
from pathlib import Path

from django.utils import timezone

from apps.admin_panel.application.dataset_admin.commands import (
    DATASET_IMPORT_SUPPORTED_FORMATS,
    delete_datasets_command,
    export_dataset_command,
    import_dataset_command,
    validate_uploaded_file_size_command,
)
from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.application.users_admin.commands import (
    toggle_admin_user_status_command,
)
from apps.admin_panel.infra.audit_logs import create_operation_log
from apps.analysis.models import Comment
from core.request_ip import get_request_ip

logger = logging.getLogger(__name__)

AdminPanelServiceError = AdminPanelApplicationError


def get_client_ip(request):
    return get_request_ip(request)


def toggle_admin_user_status(*, user, operator, client_ip=None):
    return toggle_admin_user_status_command(
        user=user,
        operator=operator,
        client_ip=client_ip,
        create_operation_log_fn=create_operation_log,
        error_cls=AdminPanelServiceError,
    )


def validate_uploaded_file_size(uploaded_file):
    return validate_uploaded_file_size_command(
        uploaded_file=uploaded_file,
        error_cls=AdminPanelServiceError,
    )


def import_dataset(*, uploaded_file, project_name="", operator, client_ip=None):
    return import_dataset_command(
        uploaded_file=uploaded_file,
        project_name=project_name,
        operator=operator,
        client_ip=client_ip,
        create_operation_log_fn=create_operation_log,
        validate_uploaded_file_size_fn=lambda *, uploaded_file: validate_uploaded_file_size(uploaded_file),
        error_cls=AdminPanelServiceError,
    )


def export_dataset(*, comments, export_format, operator, client_ip=None):
    return export_dataset_command(
        comments=comments,
        export_format=export_format,
        operator=operator,
        client_ip=client_ip,
        create_operation_log_fn=create_operation_log,
        timezone_module=timezone,
        path_cls=Path,
        makedirs_fn=os.makedirs,
    )


def delete_datasets(*, ids):
    return delete_datasets_command(
        ids=ids,
        comment_model=Comment,
        error_cls=AdminPanelServiceError,
    )


__all__ = [
    'AdminPanelServiceError',
    'DATASET_IMPORT_SUPPORTED_FORMATS',
    'get_client_ip',
    'create_operation_log',
    'toggle_admin_user_status',
    'validate_uploaded_file_size',
    'import_dataset',
    'export_dataset',
    'delete_datasets',
]
