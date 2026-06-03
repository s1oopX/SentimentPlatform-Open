from django.db import IntegrityError

from apps.admin_panel.infra.runtime_registry.selectors import (
    build_runtime_logs as _build_runtime_logs,
    build_runtime_model_payload as _build_runtime_model_payload,
    sanitize_runtime_model_payload as _sanitize_runtime_model_payload,
)
from apps.admin_panel.application.errors import AdminPanelApplicationError
from apps.admin_panel.domain.rules.runtime_registry import (
    needs_runtime_record_persistence,
    require_current_runtime_request,
)
from apps.admin_panel.application.runtime_registry.commands import (
    persist_runtime_model_payload,
)
from apps.analysis.models import Model


def build_runtime_model_payload():
    return _build_runtime_model_payload()


def sanitize_runtime_model_payload(runtime_payload):
    return _sanitize_runtime_model_payload(runtime_payload)


def build_runtime_logs(runtime_payload):
    return _build_runtime_logs(runtime_payload)


def _build_persisted_runtime_model_payload(
    *,
    operator,
    build_runtime_model_payload_fn=None,
    needs_runtime_record_persistence_fn=None,
    persist_runtime_model_payload_fn=None,
):
    build_runtime_model_payload_fn = (
        build_runtime_model_payload_fn or build_runtime_model_payload
    )
    needs_runtime_record_persistence_fn = (
        needs_runtime_record_persistence_fn or needs_runtime_record_persistence
    )
    persist_runtime_model_payload_fn = (
        persist_runtime_model_payload_fn or persist_runtime_model_payload
    )
    runtime_model = build_runtime_model_payload_fn()
    if not needs_runtime_record_persistence_fn(runtime_model):
        return runtime_model

    try:
        persist_runtime_model_payload_fn(
            runtime_payload=runtime_model,
            operator=operator,
            validate_artifacts=False,
        )
    except (IntegrityError, ValueError):
        return runtime_model
    return build_runtime_model_payload_fn()


def build_runtime_model_list_response(
    *,
    operator,
    build_runtime_model_payload_fn=None,
    needs_runtime_record_persistence_fn=None,
    persist_runtime_model_payload_fn=None,
    sanitize_runtime_model_payload_fn=None,
):
    sanitize_runtime_model_payload_fn = (
        sanitize_runtime_model_payload_fn or sanitize_runtime_model_payload
    )
    # Sync the runtime model into the DB so is_active stays fresh,
    # then return ALL models from the database for the full listing.
    _build_persisted_runtime_model_payload(
        operator=operator,
        build_runtime_model_payload_fn=build_runtime_model_payload_fn,
        needs_runtime_record_persistence_fn=needs_runtime_record_persistence_fn,
        persist_runtime_model_payload_fn=persist_runtime_model_payload_fn,
    )
    return Model.objects.select_related("source_run").all().order_by("-created_at")


def build_runtime_logs_response(
    *,
    operator,
    requested_id,
    build_runtime_model_payload_fn=None,
    build_runtime_logs_fn=None,
    needs_runtime_record_persistence_fn=None,
    persist_runtime_model_payload_fn=None,
    require_current_runtime_request_fn=None,
):
    build_runtime_logs_fn = build_runtime_logs_fn or build_runtime_logs
    require_current_runtime_request_fn = (
        require_current_runtime_request_fn or require_current_runtime_request
    )
    runtime_model = _build_persisted_runtime_model_payload(
        operator=operator,
        build_runtime_model_payload_fn=build_runtime_model_payload_fn,
        needs_runtime_record_persistence_fn=needs_runtime_record_persistence_fn,
        persist_runtime_model_payload_fn=persist_runtime_model_payload_fn,
    )
    require_current_runtime_request_fn(
        requested_id=requested_id,
        runtime_payload=runtime_model,
        error_cls=AdminPanelApplicationError,
    )

    payload = {
        "model_id": runtime_model["id"],
        "logs": build_runtime_logs_fn(runtime_model),
    }
    warning = (runtime_model.get("metrics") or {}).get("warning")
    if warning:
        payload["warning"] = warning
    return payload
