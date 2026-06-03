import json
from json import JSONDecodeError
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.admin_panel.infra.runtime_registry.registry import runtime_artifacts_complete
from apps.analysis.models import Model

RUNTIME_MODEL_VIRTUAL_ID = 0


def load_json_if_exists(path):
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (JSONDecodeError, OSError, TypeError, ValueError):
        return {}


def get_persisted_runtime_model(*, model_path):
    return (
        Model.objects.filter(path=model_path)
        .order_by("-is_active", "-created_at", "-pk")
        .first()
    )


def build_runtime_model_payload():
    """获取运行时模型元数据。
    
    如果模型尚未加载（首次访问），返回基于文件系统的轻量元数据，
    避免在列表页面触发完整的模型加载。
    """
    from apps.analysis.infra.model_runtime import _model_loader, get_model_loader
    
    # 如果模型已加载（单例存在），直接获取元数据
    if _model_loader is not None:
        loader = get_model_loader()
        metadata = loader.get_runtime_metadata()
    else:
        # 模型未加载时，基于文件系统构建轻量元数据，不触发加载
        model_path = str(Path(settings.MODEL_PATH).resolve())
        config_path = Path(model_path) / "config.json"
        metadata = {
            "name": Path(model_path).name,
            "version": "1.0",
            "model_type": "transformer",
            "metrics": {"loaded": False, "device": "pending"},
            "path": model_path,
            "is_active": True,
        }
        if config_path.exists():
            config_data = load_json_if_exists(config_path)
            if config_data.get("_name_or_path"):
                metadata["name"] = config_data["_name_or_path"].split("/")[-1]
    
    baseline_path = str(Path(settings.MODEL_PATH).resolve()).replace("/", "\\")
    runtime_record = get_persisted_runtime_model(model_path=metadata["path"])
    if runtime_record is None:
        active_model = Model.get_active_model()
        if active_model and active_model.path == metadata["path"]:
            runtime_record = active_model
    resolved_path = runtime_record.path if runtime_record else metadata["path"]
    return {
        "id": runtime_record.id if runtime_record else RUNTIME_MODEL_VIRTUAL_ID,
        "name": runtime_record.name if runtime_record else metadata["name"],
        "version": runtime_record.version if runtime_record else metadata["version"],
        "model_type": runtime_record.model_type
        if runtime_record
        else metadata["model_type"],
        "metrics": metadata["metrics"],
        "path": resolved_path,
        "file_label": Path(resolved_path).name if resolved_path else "",
        "location_label": "当前运行模型",
        "is_active": bool(metadata["is_active"])
        if runtime_record
        else metadata["is_active"],
        "baseline_path": baseline_path,
        "baseline_ready": runtime_artifacts_complete(baseline_path),
        "created_at": runtime_record.created_at if runtime_record else None,
    }


def sanitize_runtime_model_payload(runtime_payload):
    payload = dict(runtime_payload)
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        payload["metrics"] = dict(metrics)
    payload.pop("path", None)
    payload.pop("baseline_path", None)
    payload.setdefault("file_label", "")
    payload.setdefault("location_label", "当前运行模型")
    return payload


def build_runtime_logs(runtime_payload):
    metrics = runtime_payload["metrics"]
    model_path = Path(runtime_payload["path"])
    runtime_type = metrics.get("runtime_type") or runtime_payload.get("model_type") or ""

    logs = []

    if runtime_type == "classical_joblib":
        file_exists = model_path.is_file()
        logs.append({
            "timestamp": timezone.now().isoformat(),
            "level": "INFO" if file_exists else "ERROR",
            "message": f"模型文件检查 exists={file_exists}, path={model_path.name}",
        })
        config_path = model_path.parent / "config_snapshot.json"
        report_path = model_path.parent / "report.json"
        logs.append({
            "timestamp": timezone.now().isoformat(),
            "level": "INFO",
            "message": (
                f"产物检查 config_snapshot={config_path.exists()}, "
                f"report={report_path.exists()}"
            ),
        })
    elif runtime_type == "neural_torch":
        file_exists = model_path.is_file()
        vocab_exists = (model_path.parent / "vocab.json").exists()
        config_exists = (model_path.parent / "config_snapshot.json").exists()
        logs.append({
            "timestamp": timezone.now().isoformat(),
            "level": "INFO" if file_exists else "ERROR",
            "message": f"模型文件检查 exists={file_exists}, path={model_path.name}",
        })
        logs.append({
            "timestamp": timezone.now().isoformat(),
            "level": "INFO" if vocab_exists and config_exists else "WARNING",
            "message": f"产物检查 vocab={vocab_exists}, config_snapshot={config_exists}",
        })
    else:
        # Transformer: path is a directory
        model_dir = model_path
        config_exists = (model_dir / "config.json").exists()
        weights_exists = (model_dir / "model.safetensors").exists()
        tokenizer_exists = (model_dir / "tokenizer_config.json").exists()
        logs.append({
            "timestamp": timezone.now().isoformat(),
            "level": "INFO" if model_dir.exists() else "ERROR",
            "message": "模型目录检查完成",
        })
        logs.append({
            "timestamp": timezone.now().isoformat(),
            "level": "INFO"
            if config_exists and weights_exists and tokenizer_exists
            else "ERROR",
            "message": (
                f"文件检查 config={config_exists}, weights={weights_exists}, "
                f"tokenizer={tokenizer_exists}"
            ),
        })
        evaluation_report = load_json_if_exists(model_dir / "evaluation_report.json")
        if evaluation_report:
            logs.append({
                "timestamp": timezone.now().isoformat(),
                "level": "INFO",
                "message": (
                    "评估摘要 "
                    f"macro_f1={evaluation_report.get('macro_f1')}, "
                    f"accuracy={evaluation_report.get('accuracy')}"
                ),
            })

    logs.append({
        "timestamp": timezone.now().isoformat(),
        "level": "INFO" if metrics.get("loaded") else "INFO",
        "message": (
            f"运行状态 loaded={metrics.get('loaded')}, device={metrics.get('device')}"
            + ("" if metrics.get("loaded") else "（未激活，属正常状态）")
        ),
    })

    return logs
