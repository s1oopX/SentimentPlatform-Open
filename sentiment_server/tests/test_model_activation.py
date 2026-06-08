import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.admin_panel.application.training_admin.commands import (
    activate_registered_model_for_run,
)
from apps.admin_panel.application.training_admin.queries import get_training_record_detail
from apps.admin_panel.api.serializers.runtime_registry import ModelAdminSerializer
from apps.admin_panel.api.views.runtime_registry import (
    ModelActivateView,
    ModelLogsView,
    ModelManagementView,
)
from apps.admin_panel.infra.runtime_registry.registry import runtime_artifacts_complete
from apps.admin_panel.models import TrainingRun
from apps.analysis.models import Model
from apps.analysis.infra.model_runtime import SentimentModelLoader
from apps.users.models import User


class DummyClassicalEstimator:
    def predict(self, texts):
        return [2 if "好" in text else 0 for text in texts]

    def predict_proba(self, texts):
        return [[0.1, 0.2, 0.7] if "好" in text else [0.8, 0.1, 0.1] for text in texts]


def dump_dummy_joblib(path):
    joblib = pytest.importorskip("joblib")

    joblib.dump(DummyClassicalEstimator(), path)


def write_dummy_neural_artifacts(path, *, model_name="textcnn"):
    torch = pytest.importorskip("torch")
    pytest.importorskip("sklearn")

    from ml_assets.workspace.training.neural_baselines import build_neural_model

    path.mkdir(parents=True, exist_ok=True)
    vocab_payload = {
        "token_to_id": {
            "<pad>": 0,
            "<unk>": 1,
            "这": 2,
            "个": 3,
            "服": 4,
            "务": 5,
            "很": 6,
            "好": 7,
        },
        "pad_id": 0,
        "unk_id": 1,
    }
    runtime_config = {
        "max_length": 8,
        "embed_dim": 4,
        "hidden_size": 4,
        "num_filters": 2,
        "kernel_sizes": [2, 3],
        "dropout": 0.0,
    }
    model = build_neural_model(
        model_name=model_name,
        vocab_size=len(vocab_payload["token_to_id"]),
        num_classes=3,
        embed_dim=runtime_config["embed_dim"],
        hidden_size=runtime_config["hidden_size"],
        dropout=runtime_config["dropout"],
        num_filters=runtime_config["num_filters"],
        kernel_sizes=runtime_config["kernel_sizes"],
    )
    torch.save(model.state_dict(), path / "model.pt")
    (path / "vocab.json").write_text(
        json.dumps(vocab_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (path / "config_snapshot.json").write_text(
        json.dumps(
            {
                "model": {"model_name": model_name},
                "runtime": runtime_config,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@pytest.fixture
def model_artifact_dir():
    path = Path(__file__).resolve().parent / "_runtime_model_test_artifacts" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="sentiment_server.urls")
def test_non_runtime_compatible_model_activation_returns_json_error(model_artifact_dir):
    admin = User.objects.create_user(
        email="admin-models@example.com",
        password="TestPass123!",
        role="admin",
    )
    model = Model.objects.create(
        name="textcnn",
        version="run-1-textcnn",
        model_type="neural_baseline_train",
        path=str(model_artifact_dir / "missing.pt"),
        is_runtime_compatible=False,
    )
    request = APIRequestFactory().post(f"/api/admin/models/{model.pk}/activate/")
    force_authenticate(request, user=admin)

    response = ModelActivateView.as_view()(request, pk=model.pk)

    assert response.status_code == 400
    assert response.data == {"error": "该模型不兼容在线运行，不能直接启用"}


@pytest.mark.django_db
def test_model_admin_serializer_exposes_runtime_compatibility(model_artifact_dir):
    model_path = model_artifact_dir / "model.joblib"
    dump_dummy_joblib(model_path)
    model = Model.objects.create(
        name="linear_svm",
        version="run-1-linear-svm",
        model_type="classical_compare",
        path=str(model_path),
        is_runtime_compatible=False,
    )

    data = ModelAdminSerializer(model).data

    assert data["is_runtime_compatible"] is True
    assert data["runtime_type"] == "classical_joblib"
    assert data["runtime_incompatibility_reason"] == ""


@pytest.mark.django_db
def test_model_admin_serializer_exposes_training_origin_and_activation_metadata():
    admin = User.objects.create_user(
        email="admin-model-origin@example.com",
        password="TestPass123!",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="origin run",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="splits/v2",
        created_by=admin,
    )
    activated_at = timezone.now()
    model = Model.objects.create(
        name="linear_svm",
        version="run-9-linear-svm",
        model_type="classical_compare",
        metrics={"macro_f1": 0.8123, "accuracy": 0.9},
        path="models/linear_svm/run-9/model.joblib",
        is_active=True,
        source_run=training_run,
        artifact_summary={"model_file": "model.joblib"},
        registered_by=admin,
        activated_at=activated_at,
        is_best_candidate=True,
    )

    data = ModelAdminSerializer(model).data

    assert data["source_run_id"] == training_run.pk
    assert data["source_run_record_id"] == f"run-{training_run.pk}"
    assert data["source_run_name"] == "origin run"
    assert data["dataset_ref"] == "splits/v2"
    assert data["artifact_summary"] == {"model_file": "model.joblib"}
    assert data["is_best_candidate"] is True
    assert data["activated_at"] is not None


@pytest.mark.django_db
def test_model_management_lists_active_model_first(model_artifact_dir):
    admin = User.objects.create_user(
        email="admin-model-list-order@example.com",
        password="TestPass123!",
        role="admin",
    )
    inactive_path = model_artifact_dir / "inactive.joblib"
    active_path = model_artifact_dir / "active.joblib"
    dump_dummy_joblib(inactive_path)
    dump_dummy_joblib(active_path)
    inactive = Model.objects.create(
        name="inactive-linear",
        version="run-1-inactive",
        model_type="classical_compare",
        path=str(inactive_path),
        is_runtime_compatible=True,
    )
    active = Model.objects.create(
        name="active-linear",
        version="run-1-active",
        model_type="classical_compare",
        path=str(active_path),
        is_runtime_compatible=True,
        is_active=True,
    )

    request = APIRequestFactory().get("/api/admin/models/?page=1&page_size=10")
    force_authenticate(request, user=admin)
    response = ModelManagementView.as_view()(request)

    ids = [row["id"] for row in response.data["results"]]
    assert response.status_code == 200
    assert ids.index(active.pk) < ids.index(inactive.pk)


@pytest.mark.django_db
def test_model_logs_detect_runtime_type_from_artifact_path(model_artifact_dir):
    admin = User.objects.create_user(
        email="admin-model-logs-runtime@example.com",
        password="TestPass123!",
        role="admin",
    )
    model_path = model_artifact_dir / "model.joblib"
    dump_dummy_joblib(model_path)
    model = Model.objects.create(
        name="linear_svm",
        version="run-1-linear-svm",
        model_type="classical_compare",
        path=str(model_path),
        is_runtime_compatible=True,
    )

    request = APIRequestFactory().get(f"/api/admin/models/{model.pk}/logs/")
    force_authenticate(request, user=admin)
    response = ModelLogsView.as_view()(request, pk=model.pk)
    messages = [row["message"] for row in response.data["logs"]]

    assert response.status_code == 200
    assert any("模型文件检查" in message for message in messages)
    assert not any("模型目录检查完成" in message for message in messages)


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="sentiment_server.urls")
def test_unknown_model_activation_returns_404():
    admin = User.objects.create_user(
        email="admin-unknown-activate@example.com",
        password="TestPass123!",
        role="admin",
    )
    request = APIRequestFactory().post("/api/admin/models/999999/activate/")
    force_authenticate(request, user=admin)

    response = ModelActivateView.as_view()(request, pk=999999)

    assert response.status_code == 404
    assert response.data == {"error": "模型不存在"}


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="sentiment_server.urls")
def test_activation_returns_400_when_artifact_disappears_between_check_and_activate(
    model_artifact_dir,
):
    """Race-condition coverage: the registry check passes (artifact present),
    but the file is deleted before model.activate() acquires the row lock and
    re-validates. The view should surface the ValueError raised inside activate()
    as a 400 instead of leaking it.
    """
    admin = User.objects.create_user(
        email="admin-race-activate@example.com",
        password="TestPass123!",
        role="admin",
    )
    model_path = model_artifact_dir / "model.joblib"
    dump_dummy_joblib(model_path)
    model = Model.objects.create(
        name="linear_svm",
        version="run-1-linear-svm",
        model_type="classical_compare",
        path=str(model_path),
        is_runtime_compatible=True,
    )
    # Simulate the race: artifact removed after the request reaches the view
    # but before the row lock is taken inside model.activate().
    model_path.unlink()

    request = APIRequestFactory().post(f"/api/admin/models/{model.pk}/activate/")
    force_authenticate(request, user=admin)
    response = ModelActivateView.as_view()(request, pk=model.pk)

    # The pre-check is_effectively_runtime_compatible() trusts the stored flag,
    # so it lets the request through. activate() then re-validates and raises
    # ValueError, which the view turns into a 400 with the original message.
    model.refresh_from_db()
    assert response.status_code == 400
    assert "完整" in response.data["error"]
    assert model.is_active is False


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="sentiment_server.urls")
def test_legacy_classical_joblib_model_can_be_activated_despite_stale_flag(model_artifact_dir):
    admin = User.objects.create_user(
        email="admin-legacy-classical@example.com",
        password="TestPass123!",
        role="admin",
    )
    model_path = model_artifact_dir / "model.joblib"
    dump_dummy_joblib(model_path)
    model = Model.objects.create(
        name="linear_svm",
        version="run-1-linear-svm",
        model_type="classical_compare",
        path=str(model_path),
        is_runtime_compatible=False,
    )
    request = APIRequestFactory().post(f"/api/admin/models/{model.pk}/activate/")
    force_authenticate(request, user=admin)

    response = ModelActivateView.as_view()(request, pk=model.pk)

    model.refresh_from_db()
    assert response.status_code == 200
    assert model.is_active is True
    assert model.is_runtime_compatible is True


def test_runtime_artifacts_complete_accepts_classical_joblib(model_artifact_dir):
    model_path = model_artifact_dir / "model.joblib"
    dump_dummy_joblib(model_path)

    assert runtime_artifacts_complete(model_path) is True


def test_runtime_artifacts_complete_accepts_neural_torch_artifact(model_artifact_dir):
    write_dummy_neural_artifacts(model_artifact_dir)

    assert runtime_artifacts_complete(model_artifact_dir / "model.pt") is True


@pytest.mark.django_db
def test_classical_training_run_model_can_be_activated(model_artifact_dir):
    model_path = model_artifact_dir / "model.joblib"
    dump_dummy_joblib(model_path)
    admin = User.objects.create_user(
        email="admin-classical-activate@example.com",
        password="TestPass123!",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="classical run",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="splits",
        created_by=admin,
        post_run_status="succeeded",
    )
    model = Model.objects.create(
        name="linear_svm",
        version="run-1-linear-svm",
        model_type="classical_compare",
        path=str(model_path),
        is_runtime_compatible=True,
        is_best_candidate=True,
        source_run=training_run,
        registered_by=admin,
    )

    activated = activate_registered_model_for_run(
        training_run=training_run,
        operator=admin,
    )

    model.refresh_from_db()
    assert activated.pk == model.pk
    assert model.is_active is True


@pytest.mark.django_db
def test_neural_training_run_model_can_be_activated(model_artifact_dir):
    write_dummy_neural_artifacts(model_artifact_dir)
    model_path = model_artifact_dir / "model.pt"
    admin = User.objects.create_user(
        email="admin-neural-activate@example.com",
        password="TestPass123!",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="neural run",
        task_type="neural_baseline_train",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="splits",
        created_by=admin,
        post_run_status="succeeded",
    )
    model = Model.objects.create(
        name="textcnn",
        version="run-1-textcnn",
        model_type="neural_baseline_train",
        path=str(model_path),
        is_runtime_compatible=True,
        is_best_candidate=True,
        source_run=training_run,
        registered_by=admin,
    )

    activated = activate_registered_model_for_run(
        training_run=training_run,
        operator=admin,
    )

    model.refresh_from_db()
    assert activated.pk == model.pk
    assert model.is_active is True


@pytest.mark.django_db
def test_classical_joblib_runtime_predicts_sentiment(model_artifact_dir, settings):
    model_path = model_artifact_dir / "model.joblib"
    dump_dummy_joblib(model_path)
    settings.MODEL_WORKSPACE_DIR = str(model_artifact_dir)
    Model.objects.create(
        name="linear_svm",
        version="run-1-linear-svm",
        model_type="classical_compare",
        path=str(model_path),
        is_runtime_compatible=True,
        is_active=True,
    )
    loader = SentimentModelLoader()
    loader._model = None
    loader._tokenizer = None
    loader._device = None
    loader._is_loaded = False
    loader._loaded_model_path = None

    sentiment, confidence, keywords = loader.predict("这个服务很好")

    assert sentiment == 1
    assert confidence == 0.7
    assert keywords


@pytest.mark.django_db
def test_neural_torch_runtime_predicts_sentiment(model_artifact_dir, settings):
    write_dummy_neural_artifacts(model_artifact_dir)
    model_path = model_artifact_dir / "model.pt"
    settings.MODEL_WORKSPACE_DIR = str(model_artifact_dir)
    Model.objects.create(
        name="textcnn",
        version="run-1-textcnn",
        model_type="neural_baseline_train",
        path=str(model_path),
        is_runtime_compatible=True,
        is_active=True,
    )
    loader = SentimentModelLoader()
    loader._model = None
    loader._tokenizer = None
    loader._device = None
    loader._is_loaded = False
    loader._loaded_model_path = None
    loader._runtime_type = None
    loader._runtime_context = None

    sentiment, confidence, keywords = loader.predict("这个服务很好")

    assert sentiment in {-1, 0, 1}
    assert 0 <= confidence <= 1
    assert keywords


@pytest.mark.django_db
def test_training_detail_exposes_dataset_quality_and_runtime_analysis():
    admin = User.objects.create_user(
        email="admin-training-analysis@example.com",
        password="TestPass123!",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="quality run",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="splits",
        candidate_models=["linear_svm"],
        search_type="random",
        created_by=admin,
        post_run_status="warning",
        post_run_warnings=["注册模型产物缺少文件"],
        config_snapshot={
            "request": {
                "target_macro_f1": 0.85,
                "split_strategy": "pre_split",
            },
            "resolved_paths": {
                "train_dataset_path": "D:/workspace/splits/train",
                "eval_dataset_path": "D:/workspace/splits/eval",
                "test_dataset_path": "D:/workspace/splits/test",
            },
        },
        metrics_snapshot={
            "macro_f1": 0.72,
            "accuracy": 0.8,
            "negative_recall": 0.5,
            "leaderboard_preview": [
                {
                    "model_name": "linear_svm",
                    "eval_macro_f1": 0.72,
                    "cv_macro_f1_mean": 0.7,
                    "cv_macro_f1_std": 0.02,
                    "meets_target_macro_f1": False,
                }
            ],
        },
    )
    Model.objects.create(
        name="textcnn",
        version="run-1-textcnn",
        model_type="neural_baseline_train",
        path="D:/workspace/model.pt",
        is_runtime_compatible=False,
        is_best_candidate=True,
        source_run=training_run,
        registered_by=admin,
    )

    detail = get_training_record_detail(f"run-{training_run.pk}")

    assert detail["dataset_analysis"]["dataset_ref"] == "splits"
    assert detail["dataset_analysis"]["paths"]["train_dataset_path"].endswith("/train")
    assert detail["quality_warnings"]
    assert detail["runtime_compatibility"]["registered_models"][0]["runtime_type"] == "unsupported"
    assert detail["runtime_compatibility"]["registered_models"][0]["incompatibility_reason"]


@pytest.mark.django_db
def test_training_detail_matches_global_model_by_artifact_path(tmp_path):
    admin = User.objects.create_user(
        email="training-artifact-match-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    artifact_dir = tmp_path / "linear_svm"
    artifact_dir.mkdir()
    model_path = artifact_dir / "model.joblib"
    model_path.write_bytes(b"dummy joblib payload")
    training_run = TrainingRun.objects.create(
        name="linear_svm (full dataset retrain)",
        task_type="classical_compare",
        status="succeeded",
        dataset_source="workspace_dataset",
        dataset_ref="chinese-news-sentiment-c3-ds",
        artifact_paths={"model_path": str(model_path), "output_dir": str(artifact_dir)},
        created_by=admin,
    )
    Model.objects.create(
        name="linear_svm",
        version="2.0",
        model_type="classical_joblib",
        path=str(model_path),
        source_run=None,
        registered_by=admin,
        is_runtime_compatible=True,
        is_best_candidate=True,
    )

    detail = get_training_record_detail(f"run-{training_run.pk}")

    assert detail["can_activate_model"] is True
    assert detail["registered_models"][0]["name"] == "linear_svm"
    assert (
        detail["runtime_compatibility"]["registered_models"][0]["runtime_type"]
        == "classical_joblib"
    )
