import logging

from celery import shared_task
from django.db import OperationalError, InterfaceError

logger = logging.getLogger(__name__)


def _cleanup_stale_running_training_runs_task_impl():
    from apps.admin_panel.application.training_admin import tasks as task_use_cases

    return task_use_cases.cleanup_stale_running_training_runs()


def _finalize_training_run_success(training_run_id, expected_revision, result):
    from apps.admin_panel.application.training_admin import tasks as task_use_cases
    from apps.admin_panel.infra.runtime_registry.registry import register_training_run_models

    return task_use_cases.finalize_training_run_success(
        training_run_id=training_run_id,
        expected_revision=expected_revision,
        result=result,
        register_training_run_models_fn=register_training_run_models,
    )


def _retry_training_post_run_task_impl(training_run_id, expected_revision):
    from apps.admin_panel.application.training_admin import tasks as task_use_cases
    from apps.admin_panel.infra.runtime_registry.registry import register_training_run_models
    from apps.admin_panel.infra.training.executor import finalize_training_run_post_run

    return task_use_cases.retry_training_post_run_delivery(
        training_run_id=training_run_id,
        expected_revision=expected_revision,
        finalize_training_run_post_run_fn=finalize_training_run_post_run,
        register_training_run_models_fn=register_training_run_models,
    )


def _run_training_task_impl(training_run_id, expected_revision):
    from apps.admin_panel.application.training_admin import tasks as task_use_cases
    from apps.admin_panel.infra.runtime_registry.registry import register_training_run_models
    from apps.admin_panel.infra.training.executor import (
        TrainingExecutionError,
        execute_training_run,
        finalize_training_run_post_run,
    )

    return task_use_cases.run_training_task_delivery(
        training_run_id=training_run_id,
        expected_revision=expected_revision,
        execute_training_run_fn=execute_training_run,
        finalize_training_run_post_run_fn=finalize_training_run_post_run,
        register_training_run_models_fn=register_training_run_models,
        training_execution_error_cls=TrainingExecutionError,
        logger_=logger,
    )


@shared_task(
    name="apps.admin_panel.training_tasks.cleanup_stale_running_training_runs_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=30,
)
def cleanup_stale_running_training_runs_task():
    return _cleanup_stale_running_training_runs_task_impl()


@shared_task(
    name="apps.admin_panel.training_tasks.retry_training_post_run_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=60,
)
def retry_training_post_run_task(training_run_id, expected_revision):
    return _retry_training_post_run_task_impl(training_run_id, expected_revision)


@shared_task(
    name="apps.admin_panel.training_tasks.run_training_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=2,
    retry_backoff=120,
    acks_late=False,
    reject_on_worker_lost=False,
)
def run_training_task(training_run_id, expected_revision):
    return _run_training_task_impl(training_run_id, expected_revision)


@shared_task(
    name="apps.admin_panel.training_tasks.check_auto_retrain_threshold_task",
    autoretry_for=(OperationalError, InterfaceError),
    max_retries=3,
    retry_backoff=60,
)
def check_auto_retrain_threshold_task():
    from apps.admin_panel.infra.automation.auto_retrain import (
        check_auto_retrain_threshold,
    )

    return check_auto_retrain_threshold()
