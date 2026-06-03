import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)

from ml_assets.workspace.data.constants import CLASS_LABEL_IDS, CLASS_LABEL_NAMES, NEGATIVE_LABEL_ID
from ml_assets.workspace.evaluation.serialization import sanitize_for_json


def predictions_from_logits(logits):
    if isinstance(logits, tuple):
        logits = logits[0]
    return np.argmax(logits, axis=-1)


def macro_f1_score(y_true, y_pred):
    return f1_score(y_true, y_pred, average="macro", zero_division=0)


def negative_recall_score(y_true, y_pred):
    return recall_score(
        y_true,
        y_pred,
        labels=[NEGATIVE_LABEL_ID],
        average="macro",
        zero_division=0,
    )


def calculate_classification_metrics(y_true, y_pred):
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": macro_f1_score(y_true, y_pred),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "macro_recall": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "negative_recall": negative_recall_score(y_true, y_pred),
        "confusion_matrix": confusion_matrix(
            y_true,
            y_pred,
            labels=CLASS_LABEL_IDS,
        ),
        "label_order": CLASS_LABEL_NAMES,
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=CLASS_LABEL_IDS,
            target_names=CLASS_LABEL_NAMES,
            zero_division=0,
            output_dict=True,
        ),
    }
    return sanitize_for_json(metrics)


def build_scalar_metrics(y_true, y_pred):
    metrics = calculate_classification_metrics(y_true, y_pred)
    return {
        "accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "weighted_f1": metrics["weighted_f1"],
        "negative_recall": metrics["negative_recall"],
    }


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = predictions_from_logits(logits)
    return build_scalar_metrics(labels, predictions)

