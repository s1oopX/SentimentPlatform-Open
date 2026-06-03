"""
情感分析模型加载和预测模块
加载训练好的 BERT 模型进行情感预测
"""

import json
import logging
import math
import sys
from json import JSONDecodeError
from pathlib import Path
from threading import RLock

from django.conf import settings

from apps.admin_panel.infra.automation.system_config import get_keyword_top_k
from apps.analysis.domain.keyword_rules import normalize_keywords


_SINGLETON_LOCK = RLock()
logger = logging.getLogger(__name__)
MODEL_UNAVAILABLE_CODE = "model_unavailable"
RUNTIME_TYPE_CLASSICAL_JOBLIB = "classical_joblib"
RUNTIME_TYPE_NEURAL_TORCH = "neural_torch"
RUNTIME_TYPE_TRANSFORMER = "transformer"


class ModelUnavailableError(RuntimeError):
    """当前运行模型不可用时抛出的异常。"""


def build_model_unavailable_payload(message):
    return {
        "code": MODEL_UNAVAILABLE_CODE,
        "error": str(message),
    }


def _get_torch_modules():
    """Lazy-load torch so the backend can start without ML runtime deps."""
    import torch

    return torch


def _load_workspace_inference():
    workspace_root = Path(getattr(settings, "MODEL_WORKSPACE_DIR", "ml_assets"))
    parent = str(workspace_root.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    from ml_assets.workspace.serving.inference import (
        load_transformer_model,
        predict_texts,
    )

    return load_transformer_model, predict_texts


def _load_json_if_exists(path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _safe_load_json_if_exists(path, *, warning_label):
    if not path.exists():
        return {}, ""
    try:
        return _load_json_if_exists(path), ""
    except (JSONDecodeError, OSError, TypeError, ValueError):
        logger.exception("%s读取失败: %s", warning_label, path)
        return {}, f"{warning_label}损坏: {path.name}"


def _normalize_runtime_path(path_value):
    if not path_value:
        return None
    return str(Path(path_value).resolve())


def _validate_path_within_workspace(path_value):
    """Log a warning if *path_value* resolves outside MODEL_WORKSPACE_DIR."""
    workspace_root = Path(getattr(settings, "MODEL_WORKSPACE_DIR", "ml_assets")).resolve()
    resolved = Path(path_value).resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        logger.error(
            "Model path %s is outside MODEL_WORKSPACE_DIR %s.",
            resolved, workspace_root,
        )
        return False
    return True


def _detect_runtime_artifact_type(path_value):
    path = Path(path_value)
    if path.is_file() and path.suffix.lower() == ".joblib":
        return RUNTIME_TYPE_CLASSICAL_JOBLIB
    if (
        path.is_file()
        and path.suffix.lower() == ".pt"
        and (path.parent / "vocab.json").exists()
        and (path.parent / "config_snapshot.json").exists()
    ):
        return RUNTIME_TYPE_NEURAL_TORCH
    if path.is_dir():
        required_files = (
            path / "config.json",
            path / "model.safetensors",
            path / "tokenizer_config.json",
        )
        if all(required_path.exists() for required_path in required_files):
            return RUNTIME_TYPE_TRANSFORMER
    return ""


def _resolve_runtime_model_path():
    from apps.analysis.models import Model

    active_model = Model.get_active_model()
    if active_model and active_model.path:
        return str(Path(active_model.path).resolve())

    model_path = getattr(settings, "MODEL_PATH", None)
    if model_path:
        return str(Path(model_path).resolve())

    return None


class SentimentModelLoader:
    """情感分析模型加载器（单例模式）"""

    _instance = None
    _model = None
    _tokenizer = None
    _device = None
    _is_loaded = False
    _loaded_model_path = None
    _runtime_type = None
    _runtime_context = None

    def __new__(cls):
        if cls._instance is None:
            with _SINGLETON_LOCK:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._lock = RLock()
        return cls._instance

    def load_model(self):
        """加载模型和分词器"""
        with self._lock:
            model_path = _resolve_runtime_model_path()
            normalized_model_path = _normalize_runtime_path(model_path)
            if self._is_loaded and self._loaded_model_path == normalized_model_path:
                logger.info("模型已加载，跳过")
                return True

            if self._is_loaded and self._loaded_model_path != normalized_model_path:
                self._model = None
                self._tokenizer = None
                self._device = None
                self._is_loaded = False
                self._loaded_model_path = None
                self._runtime_type = None
                self._runtime_context = None

            try:
                runtime_path = Path(model_path) if model_path else None
                if not runtime_path or not runtime_path.exists():
                    logger.warning("模型路径不完整或不存在：%s", runtime_path)
                    return False
                if not _validate_path_within_workspace(runtime_path):
                    return False

                runtime_type = _detect_runtime_artifact_type(runtime_path)
                if not runtime_type:
                    logger.warning("模型文件不完整：%s", runtime_path)
                    return False

                if runtime_type == RUNTIME_TYPE_CLASSICAL_JOBLIB:
                    import joblib

                    # joblib.load 等价于 pickle.load；上方的 _validate_path_within_workspace
                    # 已确保 runtime_path 限定在 MODEL_WORKSPACE_DIR 内，不允许加载
                    # 用户上传或外部来源的 .joblib。
                    model = joblib.load(runtime_path)
                    if not hasattr(model, "predict"):
                        logger.warning("传统模型缺少 predict 方法：%s", runtime_path)
                        return False
                    self._tokenizer = None
                    self._model = model
                    self._device = "cpu"
                    self._runtime_type = runtime_type
                    self._runtime_context = {}
                    self._is_loaded = True
                    self._loaded_model_path = normalized_model_path
                    logger.info("传统模型加载成功：%s", runtime_path)
                    return True

                if runtime_type == RUNTIME_TYPE_NEURAL_TORCH:
                    torch = _get_torch_modules()
                    requested_device = "cpu"
                    if getattr(settings, "USE_GPU", False):
                        requested_device = "cuda" if torch.cuda.is_available() else "cpu"
                    model, context = _load_neural_torch_model(
                        runtime_path,
                        device=requested_device,
                    )
                    self._tokenizer = None
                    self._model = model
                    self._device = requested_device
                    self._runtime_type = runtime_type
                    self._runtime_context = context
                    self._is_loaded = True
                    self._loaded_model_path = normalized_model_path
                    logger.info("神经网络模型加载成功：%s", runtime_path)
                    return True

                load_transformer_model, _ = _load_workspace_inference()
                requested_device = "cpu"
                if getattr(settings, "USE_GPU", False):
                    torch = _get_torch_modules()
                    requested_device = "cuda" if torch.cuda.is_available() else "cpu"

                checkpoint_dir = str(runtime_path)
                logger.info("正在从 %s 加载情感分析模型...", checkpoint_dir)
                self._tokenizer, self._model, self._device = load_transformer_model(
                    model_path=checkpoint_dir,
                    device=requested_device,
                )

                self._is_loaded = True
                self._loaded_model_path = normalized_model_path
                self._runtime_type = runtime_type
                self._runtime_context = {}
                logger.info("模型加载成功，推理设备：%s", self._device)
                return True
            except Exception as exc:
                logger.error("模型加载失败：%s", exc)
                self._is_loaded = False
                self._loaded_model_path = None
                self._runtime_type = None
                self._runtime_context = None
                return False

    def ensure_loaded(self):
        """确保当前配置的真实模型已经可用。"""
        resolved_model_path = _normalize_runtime_path(_resolve_runtime_model_path())
        if resolved_model_path and not _validate_path_within_workspace(resolved_model_path):
            raise ModelUnavailableError(
                f"Model path {resolved_model_path} is outside the workspace."
            )
        with self._lock:
            if self._is_loaded and self._loaded_model_path == resolved_model_path:
                return
        if not self.load_model():
            target = resolved_model_path or getattr(settings, "MODEL_PATH", None) or "<未配置>"
            raise ModelUnavailableError(
                f"当前模型不可用，请检查模型目录和依赖：{target}"
            )

    def _get_runtime_metadata_snapshot(self):
        with self._lock:
            configured_model_path = _normalize_runtime_path(
                _resolve_runtime_model_path()
            )
            loaded_model_path = self._loaded_model_path
            loaded = self._is_loaded
            device = self._device
            runtime_type = self._runtime_type
            runtime_context = self._runtime_context
        return {
            "configured_model_path": configured_model_path,
            "runtime_model_path": loaded_model_path or configured_model_path,
            "loaded": loaded,
            "device": device,
            "runtime_type": runtime_type,
            "runtime_context": runtime_context,
        }

    def get_runtime_metadata(self):
        """返回当前真实运行模型的元信息。"""
        snapshot = self._get_runtime_metadata_snapshot()
        runtime_model_path = snapshot["runtime_model_path"]
        if not runtime_model_path:
            return {
                "name": "",
                "version": "",
                "model_type": "",
                "path": "",
                "metrics": {
                    "runtime_ready": False,
                    "loaded": snapshot["loaded"],
                    "device": snapshot["device"],
                    "runtime_type": snapshot["runtime_type"] or "",
                },
                "is_active": False,
            }
        model_path = Path(runtime_model_path)
        if _detect_runtime_artifact_type(model_path) == RUNTIME_TYPE_CLASSICAL_JOBLIB:
            return {
                "name": model_path.stem or "classical-model",
                "version": "runtime",
                "model_type": RUNTIME_TYPE_CLASSICAL_JOBLIB,
                "path": str(model_path),
                "metrics": {
                    "runtime_ready": model_path.exists(),
                    "loaded": snapshot["loaded"],
                    "device": snapshot["device"],
                    "runtime_type": RUNTIME_TYPE_CLASSICAL_JOBLIB,
                },
                "is_active": model_path.exists() and snapshot["loaded"],
            }
        if _detect_runtime_artifact_type(model_path) == RUNTIME_TYPE_NEURAL_TORCH:
            context = snapshot.get("runtime_context") or {}
            return {
                "name": context.get("model_name") or model_path.parent.name or "neural-model",
                "version": "runtime",
                "model_type": RUNTIME_TYPE_NEURAL_TORCH,
                "path": str(model_path),
                "metrics": {
                    "runtime_ready": model_path.exists(),
                    "loaded": snapshot["loaded"],
                    "device": snapshot["device"],
                    "runtime_type": RUNTIME_TYPE_NEURAL_TORCH,
                    "model_name": context.get("model_name"),
                    "max_length": context.get("max_length"),
                },
                "is_active": model_path.exists() and snapshot["loaded"],
            }
        config_path = model_path / "config.json"
        weights_path = model_path / "model.safetensors"
        tokenizer_path = model_path / "tokenizer_config.json"
        config_data, config_warning = _safe_load_json_if_exists(
            config_path,
            warning_label="运行时模型配置",
        )
        evaluation_data, evaluation_warning = _safe_load_json_if_exists(
            model_path / "evaluation_report.json",
            warning_label="运行时模型评估报告",
        )
        warnings = [
            warning for warning in [config_warning, evaluation_warning] if warning
        ]
        metrics = {
            "runtime_ready": (
                config_path.exists()
                and weights_path.exists()
                and tokenizer_path.exists()
                and not config_warning
            ),
            "loaded": snapshot["loaded"],
            "device": snapshot["device"],
            "runtime_type": RUNTIME_TYPE_TRANSFORMER,
            "base_model": config_data.get("_name_or_path"),
            "transformers_version": config_data.get("transformers_version"),
            "num_labels": config_data.get("num_labels"),
        }
        if evaluation_data:
            metrics["evaluation_report"] = evaluation_data
        if warnings:
            metrics["warning"] = "；".join(warnings)

        return {
            "name": model_path.name or "bert",
            "version": config_data.get("transformers_version") or "runtime",
            "model_type": "transformer",
            "path": str(model_path),
            "metrics": metrics,
            "is_active": metrics["runtime_ready"] and snapshot["loaded"],
        }

    def _predict_classical(self, content, model):
        label_id = _coerce_classical_label_id(model.predict([content])[0])
        confidence = _classical_prediction_confidence(model, content, label_id)
        label_map = {
            0: -1,
            1: 0,
            2: 1,
        }
        try:
            from ml_assets.workspace.serving.inference import extract_keywords

            keywords = extract_keywords(content, top_k=get_keyword_top_k())
        except Exception:
            logger.warning("传统模型关键词提取失败，返回空关键词", exc_info=True)
            keywords = []
        return label_map.get(label_id, 0), confidence, normalize_keywords(keywords)

    def predict(self, content):
        self.ensure_loaded()

        # Only hold the lock long enough to snapshot model references;
        # actual inference runs outside the lock so concurrent requests
        # do not block each other.
        with self._lock:
            tokenizer = self._tokenizer
            model = self._model
            device = self._device
            runtime_type = self._runtime_type
            runtime_context = self._runtime_context

        try:
            if runtime_type == RUNTIME_TYPE_CLASSICAL_JOBLIB:
                return self._predict_classical(content, model)
            if runtime_type == RUNTIME_TYPE_NEURAL_TORCH:
                return _predict_neural_torch(
                    content=content,
                    model=model,
                    device=device,
                    context=runtime_context,
                )

            _, predict_texts = _load_workspace_inference()
            prediction = predict_texts(
                tokenizer=tokenizer,
                model=model,
                device=device,
                texts=[content],
                max_length=getattr(settings, "MODEL_MAX_LENGTH", 256),
                keyword_top_k=get_keyword_top_k(),
                keyword_mode=getattr(settings, "MODEL_KEYWORD_MODE", "hybrid"),
            )[0]

            label_map = {
                0: -1,
                1: 0,
                2: 1,
            }
            sentiment = label_map.get(prediction["label_id"], 0)
            confidence = round(float(prediction["confidence"]), 4)
            keywords = normalize_keywords(prediction.get("keywords"))
            return sentiment, confidence, keywords
        except Exception as exc:
            logger.error("模型预测失败：%s", exc)
            raise ModelUnavailableError(
                "当前模型推理失败，请检查模型文件和运行环境"
            ) from exc

    def predict_batch(self, contents):
        """Batch prediction: returns list of (sentiment, confidence, keywords) tuples."""
        if not contents:
            return []

        self.ensure_loaded()

        with self._lock:
            tokenizer = self._tokenizer
            model = self._model
            device = self._device
            runtime_type = self._runtime_type

        try:
            if runtime_type in (RUNTIME_TYPE_CLASSICAL_JOBLIB, RUNTIME_TYPE_NEURAL_TORCH):
                return [self.predict(content) for content in contents]

            _, predict_texts = _load_workspace_inference()
            predictions = predict_texts(
                tokenizer=tokenizer,
                model=model,
                device=device,
                texts=contents,
                max_length=getattr(settings, "MODEL_MAX_LENGTH", 256),
                keyword_top_k=get_keyword_top_k(),
                keyword_mode=getattr(settings, "MODEL_KEYWORD_MODE", "hybrid"),
            )

            label_map = {
                0: -1,
                1: 0,
                2: 1,
            }
            results = []
            for prediction in predictions:
                sentiment = label_map.get(prediction["label_id"], 0)
                confidence = round(float(prediction["confidence"]), 4)
                keywords = normalize_keywords(prediction.get("keywords"))
                results.append((sentiment, confidence, keywords))
            return results
        except Exception as exc:
            logger.error("批量模型预测失败：%s", exc)
            raise ModelUnavailableError(
                "当前模型推理失败，请检查模型文件和运行环境"
            ) from exc

    @property
    def is_loaded(self):
        return self._is_loaded


_model_loader = None


def get_model_loader():
    global _model_loader
    if _model_loader is None:
        with _SINGLETON_LOCK:
            if _model_loader is None:
                loader = SentimentModelLoader()
                loader.load_model()
                _model_loader = loader
    return _model_loader


def predict_sentiment(content):
    return get_model_loader().predict(content)


def predict_sentiment_batch(contents):
    return get_model_loader().predict_batch(contents)


def _as_python_list(value):
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value


def _coerce_classical_label_id(value):
    value = _as_python_list(value)
    if isinstance(value, list):
        value = value[0] if value else 1
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 1
    if numeric == -1:
        return 0
    if numeric in {0, 1, 2}:
        return numeric
    return 1


def _softmax_confidence(scores, label_id):
    scores = [float(score) for score in scores]
    max_score = max(scores)
    exp_scores = [math.exp(score - max_score) for score in scores]
    total = sum(exp_scores)
    if not total:
        return 1.0
    if 0 <= label_id < len(exp_scores):
        return round(exp_scores[label_id] / total, 4)
    return round(max(exp_scores) / total, 4)


def _classical_prediction_confidence(model, content, label_id):
    if hasattr(model, "predict_proba"):
        probabilities = _as_python_list(model.predict_proba([content]))
        vector = probabilities[0] if probabilities else []
        if 0 <= label_id < len(vector):
            return round(float(vector[label_id]), 4)
        if vector:
            return round(float(max(vector)), 4)

    if hasattr(model, "decision_function"):
        scores = _as_python_list(model.decision_function([content]))
        vector = scores[0] if scores and isinstance(scores[0], list) else scores
        if isinstance(vector, list) and vector:
            return _softmax_confidence(vector, label_id)

    return 1.0


def _load_neural_torch_model(model_path, *, device):
    from ml_assets.workspace.training.neural_baselines import (
        CharVocab,
        build_neural_model,
    )

    torch = _get_torch_modules()
    config = _load_json_if_exists(model_path.parent / "config_snapshot.json")
    vocab_payload = _load_json_if_exists(model_path.parent / "vocab.json")
    runtime_config = dict(config.get("runtime") or {})
    model_config = dict(config.get("model") or {})
    token_to_id = dict(vocab_payload.get("token_to_id") or {})
    if not token_to_id:
        raise ValueError("神经网络模型缺少 vocab token_to_id")

    model_name = model_config.get("model_name") or model_path.parent.name
    model = build_neural_model(
        model_name=model_name,
        vocab_size=len(token_to_id),
        num_classes=3,
        embed_dim=int(runtime_config.get("embed_dim", 128)),
        hidden_size=int(runtime_config.get("hidden_size", 128)),
        dropout=float(runtime_config.get("dropout", 0.3)),
        num_filters=int(runtime_config.get("num_filters", 128)),
        kernel_sizes=list(runtime_config.get("kernel_sizes") or [2, 3, 4]),
    )
    state_dict = torch.load(model_path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model, {
        "vocab": CharVocab(token_to_id),
        "max_length": int(runtime_config.get("max_length", 256)),
        "model_name": model_name,
    }


def _predict_neural_torch(*, content, model, device, context):
    torch = _get_torch_modules()
    vocab = context["vocab"]
    max_length = context["max_length"]
    token_ids, length = vocab.encode(content, max_length)
    input_ids = torch.tensor([token_ids], dtype=torch.long, device=device)
    lengths = torch.tensor([length], dtype=torch.long, device=device)
    with torch.no_grad():
        logits = model(input_ids, lengths)
        probabilities = torch.softmax(logits, dim=-1)[0]
        label_id = int(torch.argmax(probabilities).item())
        confidence = round(float(probabilities[label_id].item()), 4)
    label_map = {
        0: -1,
        1: 0,
        2: 1,
    }
    try:
        from ml_assets.workspace.serving.inference import extract_keywords

        keywords = extract_keywords(content, top_k=get_keyword_top_k())
    except Exception:
        logger.warning("神经网络模型关键词提取失败，返回空关键词", exc_info=True)
        keywords = []
    return label_map.get(label_id, 0), confidence, normalize_keywords(keywords)
