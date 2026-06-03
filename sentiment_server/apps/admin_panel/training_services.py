from apps.admin_panel.application.training_admin.commands import (
    activate_registered_model_for_run as _activate_registered_model_for_run,
    create_training_run as _create_training_run,
    delete_training_run as _delete_training_run,
    retry_training_post_run as _retry_training_post_run,
    retry_training_run as _retry_training_run,
)
from apps.admin_panel.infra.training.tasks import retry_training_post_run_task, run_training_task


def create_training_run(*, validated_data, operator, client_ip=None):
    return _create_training_run(
        validated_data=validated_data,
        operator=operator,
        client_ip=client_ip,
        enqueue_training_run_fn=lambda training_run_id, execution_revision: run_training_task.delay(
            training_run_id,
            execution_revision,
        ),
    )


def retry_training_run(*, training_run, operator=None, client_ip=None):
    return _retry_training_run(
        training_run=training_run,
        operator=operator,
        client_ip=client_ip,
        enqueue_training_run_fn=lambda training_run_id, execution_revision: run_training_task.delay(
            training_run_id,
            execution_revision,
        ),
    )


def retry_training_post_run(*, training_run, operator=None, client_ip=None):
    return _retry_training_post_run(
        training_run=training_run,
        operator=operator,
        client_ip=client_ip,
        enqueue_post_run_fn=lambda training_run_id, execution_revision: retry_training_post_run_task.delay(
            training_run_id,
            execution_revision,
        ),
    )


def activate_registered_model_for_run(*, training_run, operator=None, client_ip=None):
    return _activate_registered_model_for_run(
        training_run=training_run,
        operator=operator,
        client_ip=client_ip,
    )


def delete_training_run(*, training_run, operator=None, reason="", client_ip=None):
    return _delete_training_run(
        training_run=training_run,
        operator=operator,
        reason=reason,
        client_ip=client_ip,
    )
