from pathlib import Path

import pytest
from django.utils import timezone

from apps.admin_panel.application.training_admin.commands import create_training_run
from apps.admin_panel.application.training_admin.tasks import (
    cleanup_stale_running_training_runs,
)
from apps.admin_panel.api.serializers.training_admin import TrainingRecordCreateSerializer
from apps.admin_panel.infra.training.executor import _build_command
from apps.admin_panel.models import TrainingRun
from apps.users.models import User


@pytest.mark.django_db
def test_create_training_run_does_not_write_read_only_execution_mode(settings, tmp_path):
    dataset_root = tmp_path / "datasets"
    split_root = dataset_root / "splits"
    (split_root / "train").mkdir(parents=True)
    (split_root / "eval").mkdir()
    settings.TRAINING_DATASETS_ROOT = dataset_root

    admin = User.objects.create_user(
        email="training-create-admin@example.com",
        password="SecurePass123",
        role="admin",
    )

    queued = []
    training_run = create_training_run(
        validated_data={
            "name": "本地测试训练任务",
            "task_type": "classical_compare",
            "dataset_source": "workspace_dataset",
            "dataset_ref": "splits",
            "candidate_models": ["linear_svm"],
            "search_type": "random",
            "split_strategy": "pre_split",
            "target_macro_f1": 0.85,
            "max_length": 128,
            "use_gpu": False,
            "max_trials": 1,
            "cv_folds": 2,
        },
        operator=admin,
        enqueue_training_run_fn=lambda training_run_id, execution_revision: queued.append(
            (training_run_id, execution_revision)
        ),
    )

    assert TrainingRun.objects.filter(pk=training_run.pk).exists()
    assert training_run.execution_mode == "manual"
    assert queued == [(training_run.pk, training_run.execution_revision)]


@pytest.mark.django_db
def test_training_run_execution_revision_persists_in_config_snapshot():
    admin = User.objects.create_user(
        email="training-revision-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="版本号兼容测试",
        task_type="classical_compare",
        status="queued",
        dataset_source="workspace_dataset",
        dataset_ref="splits",
        candidate_models=["linear_svm"],
        search_type="random",
        created_by=admin,
    )

    training_run.execution_revision = 3
    training_run.save(update_fields=["config_snapshot"])
    training_run.refresh_from_db()

    assert training_run.execution_revision == 3
    assert training_run.config_snapshot["execution_revision"] == 3


@pytest.mark.django_db
def test_cleanup_stale_running_training_runs_updates_revision_without_model_field():
    now = timezone.now()
    admin = User.objects.create_user(
        email="training-cleanup-admin@example.com",
        password="SecurePass123",
        role="admin",
    )
    training_run = TrainingRun.objects.create(
        name="过期运行任务",
        task_type="classical_compare",
        status="running",
        dataset_source="workspace_dataset",
        dataset_ref="splits",
        candidate_models=["linear_svm"],
        search_type="random",
        started_at=now - timezone.timedelta(hours=2),
        created_by=admin,
    )

    cleaned = cleanup_stale_running_training_runs(now_fn=lambda: now)

    training_run.refresh_from_db()
    assert cleaned == 1
    assert training_run.status == "failed"
    assert training_run.execution_revision == 2


def _training_run_for_command(tmp_path, *, use_gpu):
    dataset_root = tmp_path / "datasets"
    train_path = dataset_root / "splits" / "train"
    eval_path = dataset_root / "splits" / "eval"
    train_path.mkdir(parents=True)
    eval_path.mkdir()

    model_workspace = tmp_path / "ml_assets"
    output_dir = model_workspace / "models" / "_training_runs" / "run-99" / "attempt-1"
    log_path = output_dir / "run.log"

    return TrainingRun(
        id=99,
        name="神经网络 GPU 传参测试",
        task_type="neural_baseline_train",
        status="queued",
        dataset_source="workspace_dataset",
        dataset_ref="splits",
        candidate_models=["textcnn"],
        config_snapshot={
            "request": {
                "task_type": "neural_baseline_train",
                "dataset_source": "workspace_dataset",
                "dataset_ref": "splits",
                "candidate_models": ["textcnn"],
                "split_strategy": "pre_split",
                "target_macro_f1": 0.85,
                "max_length": 128,
                "use_gpu": use_gpu,
            },
            "resolved_paths": {
                "train_dataset_path": str(train_path),
                "eval_dataset_path": str(eval_path),
                "output_dir": str(output_dir),
                "log_path": str(log_path),
            },
        },
    )


def _transformer_training_run_for_command(tmp_path):
    dataset_root = tmp_path / "datasets"
    train_path = dataset_root / "splits" / "train"
    eval_path = dataset_root / "splits" / "eval"
    train_path.mkdir(parents=True)
    eval_path.mkdir()

    model_workspace = tmp_path / "ml_assets"
    output_dir = model_workspace / "models" / "_training_runs" / "run-101" / "attempt-1"
    log_path = output_dir / "run.log"

    return TrainingRun(
        id=101,
        name="Transformer 单次训练传参测试",
        task_type="transformer_train",
        status="queued",
        dataset_source="workspace_dataset",
        dataset_ref="splits",
        model_family="bert",
        config_snapshot={
            "request": {
                "task_type": "transformer_train",
                "dataset_source": "workspace_dataset",
                "dataset_ref": "splits",
                "model_family": "bert",
                "split_strategy": "pre_split",
                "target_macro_f1": 0.85,
                "max_length": 128,
            },
            "resolved_paths": {
                "train_dataset_path": str(train_path),
                "eval_dataset_path": str(eval_path),
                "output_dir": str(output_dir),
                "log_path": str(log_path),
            },
        },
    )


def test_transformer_training_command_uses_maintained_launcher(settings, tmp_path):
    model_workspace = tmp_path / "ml_assets"
    settings.MODEL_WORKSPACE_DIR = model_workspace
    settings.TRAINING_DATASETS_ROOT = tmp_path / "datasets"

    command = _build_command(
        _transformer_training_run_for_command(tmp_path),
        script_path_fn=lambda name: Path("scripts") / name,
    )

    assert command[1] == str(Path("scripts") / "run_experiment.py")
    assert command[2] == "transformer-train"
    assert "--model-name-or-path" in command
    assert command[command.index("--model-name-or-path") + 1] == "bert-base-chinese"


def test_training_create_serializer_rejects_gpu_for_non_pytorch_task():
    serializer = TrainingRecordCreateSerializer(
        data={
            "name": "错误 GPU 任务",
            "task_type": "classical_compare",
            "dataset_source": "workspace_dataset",
            "dataset_ref": "splits",
            "candidate_models": ["linear_svm"],
            "search_type": "random",
            "split_strategy": "pre_split",
            "use_gpu": True,
        }
    )

    assert not serializer.is_valid()
    assert "use_gpu" in serializer.errors


def test_neural_training_command_passes_cuda_device_when_gpu_requested(settings, tmp_path):
    model_workspace = tmp_path / "ml_assets"
    settings.MODEL_WORKSPACE_DIR = model_workspace
    settings.TRAINING_DATASETS_ROOT = tmp_path / "datasets"

    command = _build_command(
        _training_run_for_command(tmp_path, use_gpu=True),
        script_path_fn=lambda name: Path("scripts") / name,
    )

    assert "--device" in command
    assert command[command.index("--device") + 1] == "cuda"


def test_neural_training_command_passes_cpu_device_when_gpu_not_requested(settings, tmp_path):
    model_workspace = tmp_path / "ml_assets"
    settings.MODEL_WORKSPACE_DIR = model_workspace
    settings.TRAINING_DATASETS_ROOT = tmp_path / "datasets"

    command = _build_command(
        _training_run_for_command(tmp_path, use_gpu=False),
        script_path_fn=lambda name: Path("scripts") / name,
    )

    assert "--device" in command
    assert command[command.index("--device") + 1] == "cpu"


def test_auto_split_command_accepts_generated_splits_under_training_output(settings, tmp_path):
    dataset_root = tmp_path / "datasets"
    raw_path = dataset_root / "auto_retrain" / "batch_1_3"
    raw_path.mkdir(parents=True)

    model_workspace = tmp_path / "ml_assets"
    output_dir = model_workspace / "models" / "_training_runs" / "run-102" / "attempt-1"
    train_path = output_dir / "splits" / "train"
    eval_path = output_dir / "splits" / "val"
    test_path = output_dir / "splits" / "test"
    train_path.mkdir(parents=True)
    eval_path.mkdir()
    test_path.mkdir()
    log_path = output_dir / "run.log"

    settings.MODEL_WORKSPACE_DIR = model_workspace
    settings.TRAINING_DATASETS_ROOT = dataset_root

    training_run = TrainingRun(
        id=102,
        name="自动切分路径校验",
        task_type="classical_compare",
        status="queued",
        dataset_source="workspace_dataset",
        dataset_ref="auto_retrain/batch_1_3",
        candidate_models=["linear_svm"],
        search_type="random",
        split_strategy="auto_split",
        config_snapshot={
            "request": {
                "task_type": "classical_compare",
                "dataset_source": "workspace_dataset",
                "dataset_ref": "auto_retrain/batch_1_3",
                "candidate_models": ["linear_svm"],
                "search_type": "random",
                "split_strategy": "auto_split",
                "target_macro_f1": 0.85,
            },
            "resolved_paths": {
                "raw_dataset_path": str(raw_path),
                "train_dataset_path": str(train_path),
                "eval_dataset_path": str(eval_path),
                "test_dataset_path": str(test_path),
                "output_dir": str(output_dir),
                "log_path": str(log_path),
            },
        },
    )

    command = _build_command(training_run, script_path_fn=lambda name: Path("scripts") / name)

    assert command[1] == str(Path("scripts") / "compare_models.py")
    assert command[command.index("--train-dataset-path") + 1] == str(train_path)
    assert command[command.index("--eval-dataset-path") + 1] == str(eval_path)
