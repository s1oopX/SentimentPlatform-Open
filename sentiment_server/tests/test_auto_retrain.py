from decimal import Decimal

import pytest
from django.utils import timezone

from apps.admin_panel.infra.automation.auto_retrain import check_auto_retrain_threshold
from apps.admin_panel.models import OperationLog, TrainingRun
from apps.analysis.models import AnalysisResult, Comment
from apps.users.models import User


def _create_result(*, user, content, confidence, reviewed=False):
    comment = Comment.objects.create(content=content)
    return AnalysisResult.objects.create(
        user=user,
        comment=comment,
        sentiment=1,
        confidence=Decimal(str(confidence)),
        reviewed_at=timezone.now() if reviewed else None,
        reviewed_by=user if reviewed else None,
    )


@pytest.mark.django_db
def test_auto_retrain_saves_exact_eligible_batch_and_marks_results(settings, tmp_path):
    settings.AUTO_RETRAIN_ENABLED = True
    settings.AUTO_RETRAIN_MODE = "auto"
    settings.AUTO_RETRAIN_THRESHOLD = 3
    settings.AUTO_RETRAIN_MAX_BATCHES_PER_CHECK = 1
    settings.TRAINING_DATASETS_ROOT = tmp_path / "datasets"

    admin = User.objects.create_user(
        email="auto-retrain-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    high_1 = _create_result(user=admin, content="高置信样本1", confidence="0.91")
    low_unreviewed = _create_result(user=admin, content="低置信未审核", confidence="0.31")
    high_2 = _create_result(user=admin, content="高置信样本2", confidence="0.82")
    low_reviewed = _create_result(
        user=admin, content="低置信已审核", confidence="0.42", reviewed=True
    )

    saved_batches = []

    def fake_save_dataset(*, results, dataset_ref, now):
        result_ids = [result.id for result in results]
        saved_batches.append({"dataset_ref": dataset_ref, "result_ids": result_ids})
        return {
            "dataset_ref": dataset_ref,
            "result_count": len(results),
            "result_min_id": min(result_ids),
            "result_max_id": max(result_ids),
            "result_ids": result_ids,
            "label_counts": {"2": len(results)},
            "generated_at": now.isoformat(),
            "source": "analysis_results",
        }

    def fake_create_training_run(*, validated_data, operator):
        return TrainingRun.objects.create(
            name=validated_data["name"],
            task_type=validated_data["task_type"],
            status="queued",
            dataset_source=validated_data["dataset_source"],
            dataset_ref=validated_data["dataset_ref"],
            candidate_models=validated_data["candidate_models"],
            search_type=validated_data["search_type"],
            split_strategy=validated_data["split_strategy"],
            created_by=operator,
            config_snapshot={"request": validated_data, "resolved_paths": {}},
        )

    result = check_auto_retrain_threshold(
        save_dataset_fn=fake_save_dataset,
        create_training_run_fn=fake_create_training_run,
        resolve_operator_fn=lambda: admin,
    )

    assert result["status"] == "submitted"
    assert result["submitted_batches"][0]["count"] == 3
    assert saved_batches[0]["result_ids"] == [high_1.id, high_2.id, low_reviewed.id]

    for item in [high_1, high_2, low_reviewed]:
        item.refresh_from_db()
        assert item.training_dataset_ref == saved_batches[0]["dataset_ref"]
        assert item.training_dataset_at is not None

    low_unreviewed.refresh_from_db()
    assert low_unreviewed.training_dataset_ref == ""

    training_run = TrainingRun.objects.get()
    assert training_run.dataset_ref == saved_batches[0]["dataset_ref"]
    assert training_run.split_strategy == "auto_split"
    assert training_run.config_snapshot["auto_retrain"]["result_count"] == 3
    assert OperationLog.objects.filter(detail__startswith="[AUTO_RETRAIN_DATASET]").exists()


@pytest.mark.django_db
def test_auto_retrain_missing_operator_does_not_mark_or_save(settings):
    settings.AUTO_RETRAIN_ENABLED = True
    settings.AUTO_RETRAIN_MODE = "auto"
    settings.AUTO_RETRAIN_THRESHOLD = 1
    settings.AUTO_RETRAIN_MAX_BATCHES_PER_CHECK = 1

    user = User.objects.create_user(
        email="auto-retrain-user@example.com",
        password="SecurePass123",
        role="user",
    )
    result_row = _create_result(user=user, content="无人创建训练任务", confidence="0.91")

    result = check_auto_retrain_threshold(
        save_dataset_fn=lambda **_kwargs: pytest.fail("should not save dataset"),
        resolve_operator_fn=lambda: None,
    )

    assert result["status"] == "missing_operator"
    result_row.refresh_from_db()
    assert result_row.training_dataset_ref == ""
    assert OperationLog.objects.filter(detail__startswith="[AUTO_RETRAIN_ERROR]").exists()
