import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_DIR = BASE_DIR / "data" / "chinese-news-sentiment-c3-ds"
DEFAULT_SPLITS_DIR = BASE_DIR / "data" / "splits"
DEFAULT_TRAIN_SPLIT_DIR = DEFAULT_SPLITS_DIR / "train"
DEFAULT_EVAL_SPLIT_DIR = DEFAULT_SPLITS_DIR / "test"
MODELS_DIR = BASE_DIR / "models"
DEFAULT_CLASSICAL_OUTPUT_DIR = MODELS_DIR / "_classical_comparison"
DEFAULT_NEURAL_OUTPUT_DIR = MODELS_DIR / "_neural_baselines"
DEFAULT_TRANSFORMER_SEARCH_DIR = MODELS_DIR / "_transformer_search"
DEFAULT_BASE_MODEL = "hfl/chinese-roberta-wwm-ext"

LABEL2ID = {
    "negative": 0,
    "neutral": 1,
    "positive": 2,
}
ID2LABEL = {value: key for key, value in LABEL2ID.items()}
CLASS_LABEL_IDS = list(ID2LABEL.keys())
CLASS_LABEL_NAMES = [ID2LABEL[label_id] for label_id in CLASS_LABEL_IDS]
NEGATIVE_LABEL_ID = LABEL2ID["negative"]


def sanitize_model_dir_name(name):
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(name).strip().lower())
    sanitized = sanitized.strip("._-")
    return sanitized or "model"


def resolve_transformer_dir_name(model_name_or_path):
    raw_name = str(model_name_or_path).rstrip("/\\")
    base_name = Path(raw_name).name if raw_name else ""
    candidate = sanitize_model_dir_name(base_name or raw_name or "transformer")
    if candidate in {"bert", "roberta", "transformer"}:
        return f"{candidate}_finetuned"
    return candidate


def get_model_dir(model_name):
    return MODELS_DIR / sanitize_model_dir_name(model_name)


def resolve_output_dir(base_dir, experiment_name=None):
    base_dir = Path(base_dir)
    if not experiment_name:
        return base_dir
    return base_dir / sanitize_model_dir_name(experiment_name)


def get_transformer_output_dir(model_name_or_path, experiment_name=None):
    base_dir = MODELS_DIR / resolve_transformer_dir_name(model_name_or_path)
    return resolve_output_dir(base_dir, experiment_name=experiment_name)


DEFAULT_REFERENCE_BERT_DIR = MODELS_DIR / "bert"
DEFAULT_OUTPUT_DIR = get_transformer_output_dir(DEFAULT_BASE_MODEL)
DEFAULT_LOG_DIR = DEFAULT_OUTPUT_DIR / "logs"
DEFAULT_API_MODEL_DIR = DEFAULT_REFERENCE_BERT_DIR
