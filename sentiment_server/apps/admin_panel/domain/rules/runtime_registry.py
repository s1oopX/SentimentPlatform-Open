from apps.admin_panel.domain.errors import AdminPanelDomainError

RUNTIME_MODEL_VIRTUAL_ID = 0


def needs_runtime_record_persistence(runtime_payload):
    return int(runtime_payload.get("id") or 0) == RUNTIME_MODEL_VIRTUAL_ID


def is_current_runtime_request(*, requested_id, runtime_payload):
    runtime_id = runtime_payload.get("id")
    return (
        runtime_id not in (None, RUNTIME_MODEL_VIRTUAL_ID)
        and requested_id == runtime_id
    )


def require_current_runtime_request(
    *, requested_id, runtime_payload, error_cls=AdminPanelDomainError
):
    if not is_current_runtime_request(
        requested_id=requested_id, runtime_payload=runtime_payload
    ):
        raise error_cls("runtime_model_not_found", "模型不存在", status_code=404)
    return runtime_payload
