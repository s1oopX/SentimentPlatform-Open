import pytest

from apps.admin_panel.application.training_admin.commands import (
    TrainingServiceError,
    delete_training_run,
)
from apps.admin_panel.application.training_admin.queries import (
    build_training_dashboard_payload,
    get_training_record_detail,
)
from apps.admin_panel.models import TrainingRun
from apps.users.models import User


@pytest.mark.django_db
def test_delete_training_run_removes_failed_record():
    admin = User.objects.create_user(
        email="training-delete-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="失败训练任务",
        task_type="classical_compare",
        status="failed",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        created_by=admin,
    )

    snapshot = delete_training_run(
        training_run=training_run,
        operator=admin,
        reason="清理失败记录",
    )

    assert snapshot["id"] == training_run.id
    assert not TrainingRun.objects.filter(pk=training_run.pk).exists()


@pytest.mark.django_db
def test_delete_training_run_rejects_successful_non_demo_record():
    admin = User.objects.create_user(
        email="training-delete-reject-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="正常成功训练任务",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        created_by=admin,
    )

    with pytest.raises(TrainingServiceError) as exc_info:
        delete_training_run(
            training_run=training_run,
            operator=admin,
            reason="误删测试",
        )

    assert "仅允许删除失败、已取消或演示命名的训练记录" in str(exc_info.value)
    assert TrainingRun.objects.filter(pk=training_run.pk).exists()


@pytest.mark.django_db
def test_training_dashboard_filters_failed_and_demo_named_records():
    admin = User.objects.create_user(
        email="training-dashboard-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    TrainingRun.objects.create(
        name="成功训练任务",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        created_by=admin,
    )
    TrainingRun.objects.create(
        name="失败训练任务",
        task_type="classical_compare",
        status="failed",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        created_by=admin,
    )
    TrainingRun.objects.create(
        name="[local-demo-training] 演示训练任务 01",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        created_by=admin,
    )

    payload = build_training_dashboard_payload()

    assert payload["totals"]["total_records"] == 1
    assert [item["title"] for item in payload["recent_records"]] == ["成功训练任务"]
    assert [item["title"] for item in payload["best_records"]] == ["成功训练任务"]


@pytest.mark.django_db
def test_training_record_detail_reports_can_delete_for_failed_records():
    admin = User.objects.create_user(
        email="training-detail-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="[local-demo-training] 演示训练任务 02",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        created_by=admin,
    )

    detail = get_training_record_detail(f"run-{training_run.id}")

    assert detail["can_delete"] is True


@pytest.mark.django_db
def test_training_record_detail_exposes_confusion_matrix_label_order():
    admin = User.objects.create_user(
        email="training-detail-label-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="矩阵标签顺序测试",
        task_type="transformer_train",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        metrics_snapshot={
            "confusion_matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            "label_order": ["negative", "neutral", "positive"],
        },
        created_by=admin,
    )

    detail = get_training_record_detail(f"run-{training_run.id}")

    assert detail["confusion_matrix"] == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    assert detail["label_order"] == ["negative", "neutral", "positive"]
