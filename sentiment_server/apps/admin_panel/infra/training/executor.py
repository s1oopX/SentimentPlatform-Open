import json
import logging
import os
import subprocess
import sys
from json import JSONDecodeError
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings

from apps.admin_panel.training_constants import (
    ALL_CANDIDATE_MODELS,
    SEARCH_TYPE_CHOICES,
    TASK_TYPE_CLASSICAL_COMPARE,
    TASK_TYPE_NEURAL_BASELINE_TRAIN,
    TASK_TYPE_TRANSFORMER_SEARCH,
    TASK_TYPE_TRANSFORMER_TRAIN,
    TRANSFORMER_MODEL_FAMILIES,
)

_VALID_CANDIDATE_MODELS = set(ALL_CANDIDATE_MODELS)
_VALID_SEARCH_TYPES = {value for value, _label in SEARCH_TYPE_CHOICES}
_VALID_MODEL_FAMILIES = set(TRANSFORMER_MODEL_FAMILIES)

logger = logging.getLogger(__name__)


TRANSFORMER_BASE_MODELS = {
    "bert": "bert-base-chinese",
    "roberta": "hfl/chinese-roberta-wwm-ext",
}


class TrainingExecutionError(RuntimeError):
    def __init__(self, message, *, execution_result):
        super().__init__(message)
        self.execution_result = execution_result


DEFAULT_TRAINING_EXECUTION_TIMEOUT_SECONDS = 60 * 60


def _perform_auto_split(raw_dataset_path, output_dir):
    """Load raw HuggingFace dataset, run 7:1:2 stratified split, save to output_dir/splits/."""
    from datasets import load_from_disk

    from ml_assets.workspace.data.processing import stratified_three_way_split

    raw_dataset = load_from_disk(str(raw_dataset_path))
    train_ds, val_ds, test_ds = stratified_three_way_split(
        raw_dataset, train_size=0.7, val_size=0.1, test_size=0.2, seed=42,
    )

    splits_dir = Path(output_dir) / "splits"
    train_dir = splits_dir / "train"
    val_dir = splits_dir / "val"
    test_dir = splits_dir / "test"
    splits_dir.mkdir(parents=True, exist_ok=True)

    train_ds.save_to_disk(str(train_dir))
    val_ds.save_to_disk(str(val_dir))
    test_ds.save_to_disk(str(test_dir))

    logger.info(
        "auto_split completed: train=%d val=%d test=%d",
        len(train_ds), len(val_ds), len(test_ds),
    )
    return str(train_dir), str(val_dir), str(test_dir)


def _ensure_path_within_root(path_value, *, root, label, must_exist=False):
    root = Path(root).resolve()
    candidate = Path(path_value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"{label} 超出允许目录: {candidate}") from exc
    if must_exist and not candidate.exists():
        raise RuntimeError(f"{label} 不存在: {candidate}")
    return str(candidate)


def _validate_resolved_paths(resolved_paths, *, split_strategy="pre_split"):
    datasets_root = Path(
        getattr(settings, "TRAINING_DATASETS_ROOT", settings.MODEL_WORKSPACE_DIR)
    ).resolve()
    training_runs_root = (
        Path(settings.MODEL_WORKSPACE_DIR).resolve() / "models" / "_training_runs"
    )

    if split_strategy == "auto_split":
        required_keys = ("output_dir", "log_path", "raw_dataset_path")
    else:
        required_keys = (
            "train_dataset_path",
            "eval_dataset_path",
            "output_dir",
            "log_path",
        )
    missing = [key for key in required_keys if not resolved_paths.get(key)]
    if missing:
        raise RuntimeError(f"训练路径快照缺少字段: {', '.join(missing)}")

    validated = dict(resolved_paths)
    if resolved_paths.get("train_dataset_path"):
        validated["train_dataset_path"] = _ensure_path_within_root(
            resolved_paths["train_dataset_path"],
            root=datasets_root,
            label="训练集路径",
            must_exist=True,
        )
    if resolved_paths.get("eval_dataset_path"):
        validated["eval_dataset_path"] = _ensure_path_within_root(
            resolved_paths["eval_dataset_path"],
            root=datasets_root,
            label="验证集路径",
            must_exist=True,
        )
    if resolved_paths.get("test_dataset_path"):
        validated["test_dataset_path"] = _ensure_path_within_root(
            resolved_paths["test_dataset_path"],
            root=datasets_root,
            label="测试集路径",
            must_exist=True,
        )
    validated["output_dir"] = _ensure_path_within_root(
        resolved_paths["output_dir"],
        root=training_runs_root,
        label="训练输出目录",
    )
    validated["log_path"] = _ensure_path_within_root(
        resolved_paths["log_path"],
        root=training_runs_root,
        label="训练日志路径",
    )
    if Path(validated["log_path"]).name != "run.log":
        raise RuntimeError("训练日志路径文件名必须为 run.log")
    return validated


def _validate_command_args(training_run):
    """Defense-in-depth: reject values that could inject unexpected flags."""
    candidate_models = list(training_run.candidate_models or [])
    for model_name in candidate_models:
        if model_name not in _VALID_CANDIDATE_MODELS:
            raise RuntimeError(
                f"非法 candidate_models 值: {model_name!r} (允许: {sorted(_VALID_CANDIDATE_MODELS)})"
            )

    search_type = training_run.search_type or ""
    if search_type and search_type not in _VALID_SEARCH_TYPES:
        raise RuntimeError(
            f"非法 search_type 值: {search_type!r} (允许: {sorted(_VALID_SEARCH_TYPES)})"
        )

    model_family = training_run.model_family or ""
    if model_family and model_family not in _VALID_MODEL_FAMILIES:
        raise RuntimeError(
            f"非法 model_family 值: {model_family!r} (允许: {sorted(_VALID_MODEL_FAMILIES)})"
        )


def _script_path(name):
    return Path(settings.MODEL_WORKSPACE_DIR) / "scripts" / "training" / name


def _load_json_if_exists(path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _safe_load_json_if_exists(path, *, warning_label, warnings):
    if not path.exists():
        return {}, False
    try:
        return _load_json_if_exists(path), True
    except (JSONDecodeError, OSError, TypeError, ValueError):
        warnings.append(f"{warning_label}解析失败: {path.name}")
        return {}, False


def _build_row_metrics(row):
    core_metrics = row.get("core_metrics") or {}
    return {
        "accuracy": row.get("eval_accuracy", core_metrics.get("accuracy")),
        "macro_f1": row.get("eval_macro_f1", core_metrics.get("macro_f1")),
        "negative_recall": row.get(
            "eval_negative_recall", core_metrics.get("negative_recall")
        ),
    }


def _extract_registry_candidates(training_run, result_summary, output_dir):
    artifact_paths = result_summary.get("artifact_paths") or {}
    task_type = training_run.task_type

    if task_type in {TASK_TYPE_CLASSICAL_COMPARE, TASK_TYPE_NEURAL_BASELINE_TRAIN}:
        leaderboard_path = artifact_paths.get("leaderboard_path") or str(
            output_dir / "leaderboard.json"
        )
        leaderboard_rows = _load_json_if_exists(Path(leaderboard_path))
        if not isinstance(leaderboard_rows, list):
            return []
        return [
            {
                "name": row.get("model_name")
                or row.get("entry_name")
                or f"candidate-{index + 1}",
                "path": (row.get("artifact_paths") or {}).get("model_path") or "",
                "metrics": _build_row_metrics(row),
            }
            for index, row in enumerate(leaderboard_rows)
            if (row.get("artifact_paths") or {}).get("model_path")
        ]

    if task_type == TASK_TYPE_TRANSFORMER_SEARCH:
        selected_model_dir = artifact_paths.get("selected_model_dir")
        if not selected_model_dir:
            return []
        return [
            {
                "name": result_summary.get("selected_run_name")
                or training_run.model_family
                or training_run.name,
                "path": selected_model_dir,
                "metrics": dict(result_summary.get("core_metrics") or {}),
            }
        ]

    model_dir = artifact_paths.get("model_dir")
    if not model_dir:
        return []
    return [
        {
            "name": training_run.model_family or training_run.name,
            "path": model_dir,
            "metrics": dict(result_summary.get("core_metrics") or {}),
        }
    ]


def _render_training_log(command, completed):
    return "\n".join(
        [
            "$ " + " ".join(command),
            completed.stdout or "",
            completed.stderr or "",
        ]
    ).strip()


def _normalize_process_output(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _default_post_run_result(output_dir, log_path):
    return {
        "metrics_snapshot": {},
        "artifact_paths": {
            "output_dir": str(output_dir),
        },
        "log_path": str(log_path),
        "registry_candidates": [],
        "artifacts_complete": True,
        "post_run_warnings": [],
        "post_run_message": "",
    }


def _build_command(training_run, *, script_path_fn=None):
    _validate_command_args(training_run)
    # Snapshot validated values immediately to prevent race condition
    # if the training_run DB row is mutated between validation and use.
    validated_model_family = training_run.model_family or "roberta"
    validated_candidate_models = list(training_run.candidate_models or [])
    validated_search_type = training_run.search_type or ""

    script_path_fn = script_path_fn or _script_path
    snapshot = training_run.config_snapshot or {}
    request = snapshot.get("request", {})
    split_strategy = request.get("split_strategy", "pre_split")
    resolved_paths = _validate_resolved_paths(
        snapshot.get("resolved_paths", {}), split_strategy=split_strategy,
    )
    task_type = training_run.task_type
    output_dir = resolved_paths["output_dir"]
    command = [
        sys.executable,
        "",
        "--train-dataset-path",
        resolved_paths["train_dataset_path"],
        "--eval-dataset-path",
        resolved_paths["eval_dataset_path"],
        "--output-dir",
        output_dir,
        "--experiment-name",
        f"run-{training_run.id}",
        "--target-macro-f1",
        str(request.get("target_macro_f1", 0.85)),
    ]

    if task_type == TASK_TYPE_TRANSFORMER_TRAIN:
        command[1] = str(script_path_fn("run_experiment.py"))
        command.insert(2, "transformer-train")
        command.extend(
            [
                "--model-name-or-path",
                TRANSFORMER_BASE_MODELS.get(
                    validated_model_family,
                    "hfl/chinese-roberta-wwm-ext",
                ),
                "--max-length",
                str(request.get("max_length", 256)),
            ]
        )
    elif task_type == TASK_TYPE_TRANSFORMER_SEARCH:
        command[1] = str(script_path_fn("search_transformer.py"))
        command.extend(
            [
                "--model-name-or-path",
                TRANSFORMER_BASE_MODELS.get(
                    validated_model_family,
                    "hfl/chinese-roberta-wwm-ext",
                ),
                "--max-length",
                str(request.get("max_length", 256)),
                "--search-type",
                validated_search_type or request.get("search_type", "random"),
                "--max-trials",
                str(request.get("max_trials", 8)),
                "--cv-folds",
                str(request.get("cv_folds", 3)),
            ]
        )
    elif task_type == TASK_TYPE_CLASSICAL_COMPARE:
        command[1] = str(script_path_fn("compare_models.py"))
        command.extend(
            [
                "--search-type",
                validated_search_type or request.get("search_type", "random"),
                "--max-trials",
                str(request.get("max_trials", 8)),
                "--cv-folds",
                str(request.get("cv_folds", 3)),
                "--models",
                *validated_candidate_models,
            ]
        )
    elif task_type == TASK_TYPE_NEURAL_BASELINE_TRAIN:
        command[1] = str(script_path_fn("train_neural_baselines.py"))
        command.extend(
            [
                "--device",
                "cuda" if request.get("use_gpu", False) else "cpu",
                "--models",
                *validated_candidate_models,
            ]
        )
    else:
        raise RuntimeError(f"未知训练任务类型: {task_type}")

    return command


def _collect_artifacts(output_dir, training_run):
    output_dir = Path(output_dir)
    config_snapshot_path = output_dir / "config_snapshot.json"
    result_summary_path = output_dir / "result_summary.json"
    evaluation_report_path = output_dir / "evaluation_report.json"
    warnings = []
    result_summary, result_summary_ok = _safe_load_json_if_exists(
        result_summary_path,
        warning_label="训练结果摘要",
        warnings=warnings,
    )
    evaluation_report, _evaluation_report_ok = _safe_load_json_if_exists(
        evaluation_report_path,
        warning_label="评估报告",
        warnings=warnings,
    )
    metrics = dict(result_summary.get("core_metrics") or {})
    if "confusion_matrix" in result_summary:
        metrics["confusion_matrix"] = result_summary.get("confusion_matrix")
    if "loss_curve" in result_summary:
        metrics["loss_curve"] = result_summary.get("loss_curve")
    if not metrics and evaluation_report:
        metrics = dict(evaluation_report.get("core_metrics") or {})

    leaderboard_warnings = []
    registry_candidates = []
    try:
        registry_candidates = _extract_registry_candidates(
            training_run, result_summary, output_dir
        )
    except (JSONDecodeError, OSError, TypeError, ValueError):
        leaderboard_warnings.append("排行榜工件解析失败: leaderboard.json")

    warnings.extend(leaderboard_warnings)
    artifact_paths = {
        "output_dir": str(output_dir),
        "config_snapshot_path": str(config_snapshot_path)
        if config_snapshot_path.exists()
        else "",
        "result_summary_path": str(result_summary_path)
        if result_summary_path.exists()
        else "",
        "evaluation_report_path": str(evaluation_report_path)
        if evaluation_report_path.exists()
        else "",
    }
    artifacts_complete = bool(result_summary_ok)

    return {
        "metrics_snapshot": metrics,
        "artifact_paths": artifact_paths,
        "registry_candidates": registry_candidates,
        "artifacts_complete": artifacts_complete,
        "post_run_warnings": warnings,
        "post_run_message": "训练完成，但部分训练产物无法解析" if warnings else "",
    }


def finalize_training_run_post_run(
    training_run,
    execution_result,
    *,
    collect_artifacts_fn=None,
    render_training_log_fn=None,
):
    collect_artifacts_fn = collect_artifacts_fn or _collect_artifacts
    render_training_log_fn = render_training_log_fn or _render_training_log
    snapshot = training_run.config_snapshot or {}
    request = snapshot.get("request", {})
    split_strategy = request.get("split_strategy", "pre_split")
    resolved_paths = _validate_resolved_paths(
        snapshot.get("resolved_paths", {}), split_strategy=split_strategy,
    )
    output_dir = Path(
        execution_result.get("output_dir") or resolved_paths["output_dir"]
    )
    log_path = Path(execution_result.get("log_path") or resolved_paths["log_path"])
    result = _default_post_run_result(output_dir, log_path)
    warnings = list(result["post_run_warnings"])

    log_contents = execution_result.get("log_contents")
    if log_contents is None:
        completed = type(
            "CompletedProcessLike",
            (),
            {
                "stdout": execution_result.get("stdout") or "",
                "stderr": execution_result.get("stderr") or "",
            },
        )()
        log_contents = render_training_log_fn(
            execution_result.get("command") or [], completed
        )

    preserve_existing_log = bool(execution_result.get("preserve_existing_log"))
    if not (preserve_existing_log and log_path.exists()):
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(log_contents, encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            warnings.append(f"训练日志写入失败: {exc}")

    try:
        collected = collect_artifacts_fn(output_dir, training_run)
    except Exception as exc:
        warnings.append(f"训练产物收集失败: {exc}")
        collected = {}

    result.update(
        {
            "metrics_snapshot": collected.get("metrics_snapshot") or {},
            "artifact_paths": collected.get("artifact_paths")
            or result["artifact_paths"],
            "registry_candidates": collected.get("registry_candidates") or [],
            "artifacts_complete": collected.get("artifacts_complete", True),
            "post_run_warnings": warnings
            + list(collected.get("post_run_warnings") or []),
            "post_run_message": collected.get("post_run_message") or "",
        }
    )
    if result["post_run_warnings"] and not result["post_run_message"]:
        result["post_run_message"] = (
            f"训练完成，但后处理不完整：{result['post_run_warnings'][0]}"
        )
    return result


def execute_training_run(
    training_run,
    *,
    subprocess_run=None,
    build_command_fn=None,
    normalize_process_output_fn=None,
    render_training_log_fn=None,
):
    subprocess_run = subprocess_run or subprocess.run
    build_command_fn = build_command_fn or _build_command
    normalize_process_output_fn = (
        normalize_process_output_fn or _normalize_process_output
    )
    render_training_log_fn = render_training_log_fn or _render_training_log
    snapshot = training_run.config_snapshot or {}
    request = snapshot.get("request", {})
    split_strategy = request.get("split_strategy", "pre_split")
    resolved_paths = _validate_resolved_paths(
        snapshot.get("resolved_paths", {}), split_strategy=split_strategy,
    )
    output_dir = Path(resolved_paths["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(resolved_paths["log_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if split_strategy == "auto_split":
        raw_path = resolved_paths.get("raw_dataset_path", "")
        if not raw_path or not Path(raw_path).exists():
            raise RuntimeError(f"auto_split 原始数据集不存在: {raw_path}")
        train_path, eval_path, test_path = _perform_auto_split(raw_path, output_dir)
        resolved_paths["train_dataset_path"] = train_path
        resolved_paths["eval_dataset_path"] = eval_path
        resolved_paths["test_dataset_path"] = test_path
        snapshot["resolved_paths"] = resolved_paths
        training_run.config_snapshot = snapshot
        training_run.save(update_fields=["config_snapshot"])

    command = build_command_fn(training_run)
    env = os.environ.copy()
    pythonpath_parts = [str(settings.BASE_DIR)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    timeout_seconds = int(
        getattr(
            settings,
            "TRAINING_EXECUTION_TIMEOUT_SECONDS",
            DEFAULT_TRAINING_EXECUTION_TIMEOUT_SECONDS,
        )
    )
    try:
        completed = subprocess_run(
            command,
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = normalize_process_output_fn(exc.output)
        stderr = normalize_process_output_fn(exc.stderr)
        completed_like = SimpleNamespace(stdout=stdout, stderr=stderr)
        execution_result = {
            "output_dir": str(output_dir),
            "log_path": str(log_path),
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "log_contents": render_training_log_fn(command, completed_like),
        }
        raise TrainingExecutionError(
            f"训练脚本执行超时（>{timeout_seconds} 秒）",
            execution_result=execution_result,
        ) from exc

    execution_result = {
        "output_dir": str(output_dir),
        "log_path": str(log_path),
        "command": command,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
        "log_contents": render_training_log_fn(command, completed),
    }

    if completed.returncode != 0:
        raise TrainingExecutionError(
            f"训练脚本执行失败，退出码 {completed.returncode}",
            execution_result=execution_result,
        )

    return execution_result
