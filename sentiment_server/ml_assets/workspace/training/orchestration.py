import json
import logging
import random
from argparse import Namespace
from dataclasses import dataclass

from ml_assets.workspace.training.artifacts import (
    build_config_snapshot,
    build_result_summary,
    persist_experiment_artifacts,
    to_artifact_path,
)

logger = logging.getLogger(__name__)


@dataclass
class TransformerWorkflowContext:
    train_dataset: object
    eval_dataset: object
    tokenizer: object
    tokenized_train: object
    tokenized_eval: object
    trainer: object


@dataclass
class RankedWorkflowArtifacts:
    leaderboard_rows: list
    leaderboard_path: object
    leaderboard_csv_path: object
    best_run_path: object


def seed_everything(seed: int):
    import numpy as np
    import torch
    from transformers import set_seed

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    set_seed(seed)


def ensure_workflow_output_dir(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_child_output_dir(base_output_dir, child_name):
    from ml_assets.workspace.data.constants import resolve_output_dir

    return resolve_output_dir(base_output_dir, child_name)


def clone_namespace(base_args, **overrides):
    values = vars(base_args).copy()
    values.update(overrides)
    return Namespace(**values)


def build_transformer_search_run_args(base_args, candidate, run_index):
    run_dir = build_child_output_dir(base_args.output_dir, f"run_{run_index:03d}")
    return clone_namespace(
        base_args,
        output_dir=run_dir,
        logging_dir=run_dir / "logs",
        seed=base_args.seed + run_index,
        num_train_epochs=candidate["num_train_epochs"],
        learning_rate=candidate["learning_rate"],
        weight_decay=candidate["weight_decay"],
        warmup_ratio=candidate["warmup_ratio"],
        per_device_train_batch_size=candidate["per_device_train_batch_size"],
    )


def build_transformer_search_fold_args(run_args, fold_index):
    fold_dir = build_child_output_dir(run_args.output_dir, f"fold_{fold_index:02d}")
    return clone_namespace(
        run_args,
        seed=run_args.seed + fold_index,
        output_dir=fold_dir,
        logging_dir=fold_dir / "logs",
    )


def build_training_args(args):
    from transformers import TrainingArguments

    report_to = [] if args.report_to.lower() == "none" else [args.report_to]

    return TrainingArguments(
        output_dir=str(args.output_dir),
        logging_dir=str(args.logging_dir),
        logging_steps=args.logging_steps,
        eval_strategy=args.eval_strategy,
        save_strategy=args.save_strategy,
        save_total_limit=args.save_total_limit,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        load_best_model_at_end=True,
        report_to=report_to,
        learning_rate=args.learning_rate,
        lr_scheduler_type=args.lr_scheduler_type,
        warmup_ratio=args.warmup_ratio,
        weight_decay=args.weight_decay,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        dataloader_num_workers=args.dataloader_num_workers,
        fp16=args.fp16,
        bf16=args.bf16,
        seed=args.seed,
        log_level="info",
    )


def save_run_metadata(args, train_dataset, eval_dataset, metrics, evaluation_report_path=None):
    from ml_assets.workspace.data.constants import ID2LABEL, LABEL2ID

    eval_macro_f1 = metrics.get("eval_macro_f1", metrics.get("macro_f1", 0.0))
    core_metrics = {
        "accuracy": metrics.get("eval_accuracy", metrics.get("accuracy")),
        "macro_f1": eval_macro_f1,
        "negative_recall": metrics.get("eval_negative_recall", metrics.get("negative_recall")),
    }

    config_snapshot = build_config_snapshot(
        workflow_type="transformer_train",
        output_dir=args.output_dir,
        dataset={
            "train_dataset_path": str(args.train_dataset_path),
            "eval_dataset_path": str(args.eval_dataset_path),
            "train_rows": len(train_dataset),
            "eval_rows": len(eval_dataset),
        },
        runtime={
            "seed": args.seed,
            "max_length": args.max_length,
            "num_train_epochs": args.num_train_epochs,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "warmup_ratio": args.warmup_ratio,
            "per_device_train_batch_size": args.per_device_train_batch_size,
            "per_device_eval_batch_size": args.per_device_eval_batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "lr_scheduler_type": args.lr_scheduler_type,
            "report_to": args.report_to,
            "logging_dir": to_artifact_path(args.logging_dir),
        },
        model={
            "model_name_or_path": args.model_name_or_path,
            "label2id": LABEL2ID,
            "id2label": ID2LABEL,
        },
        extras={
            "experiment_name": getattr(args, "experiment_name", None),
        },
    )

    artifact_paths = {
        "model_dir": to_artifact_path(args.output_dir),
        "tokenizer_dir": to_artifact_path(args.output_dir),
    }
    if evaluation_report_path is not None:
        artifact_paths["evaluation_report_path"] = to_artifact_path(evaluation_report_path)

    result_summary = build_result_summary(
        workflow_type="transformer_train",
        output_dir=args.output_dir,
        core_metrics=core_metrics,
        target_macro_f1=args.target_macro_f1,
        artifact_paths=artifact_paths,
        extras={
            "trainer_metrics": metrics,
            "meets_target_macro_f1": eval_macro_f1 >= args.target_macro_f1,
        },
    )

    return persist_experiment_artifacts(
        args.output_dir,
        config_snapshot=config_snapshot,
        result_summary=result_summary,
    )


def finalize_ranked_workflow_outputs(output_dir, leaderboard_rows, *, ranking_key):
    from ml_assets.workspace.evaluation.reporting import save_csv, save_json

    ensure_workflow_output_dir(output_dir)
    ranked_rows = sorted(
        leaderboard_rows,
        key=lambda item: item[ranking_key],
        reverse=True,
    )
    for rank, row in enumerate(ranked_rows, start=1):
        row["rank"] = rank

    leaderboard_path = output_dir / "leaderboard.json"
    leaderboard_csv_path = output_dir / "leaderboard.csv"
    best_run_path = output_dir / "best_run.json"
    save_json(leaderboard_path, ranked_rows)
    save_csv(leaderboard_csv_path, ranked_rows)
    return RankedWorkflowArtifacts(
        leaderboard_rows=ranked_rows,
        leaderboard_path=leaderboard_path,
        leaderboard_csv_path=leaderboard_csv_path,
        best_run_path=best_run_path,
    )


def persist_ranked_workflow_root_artifacts(
    output_dir,
    *,
    workflow_type,
    target_macro_f1,
    dataset,
    runtime,
    model,
    core_metrics,
    artifact_paths,
    config_extras=None,
    summary_extras=None,
):
    config_snapshot = build_config_snapshot(
        workflow_type=workflow_type,
        output_dir=output_dir,
        dataset=dataset,
        runtime=runtime,
        model=model,
        extras=config_extras,
    )
    result_summary = build_result_summary(
        workflow_type=workflow_type,
        output_dir=output_dir,
        core_metrics=core_metrics,
        target_macro_f1=target_macro_f1,
        artifact_paths=artifact_paths,
        extras=summary_extras,
    )
    root_artifact_paths = persist_experiment_artifacts(
        output_dir,
        config_snapshot=config_snapshot,
        result_summary=result_summary,
    )
    return root_artifact_paths, result_summary


def write_best_run_summary(
    output_path,
    *,
    workflow_type,
    entry_key,
    entry_value,
    summary_path,
    config_snapshot_path,
    core_metrics,
    artifact_paths,
    extras=None,
):
    from ml_assets.workspace.evaluation.reporting import save_json

    payload = {
        "schema_version": 1,
        "artifact_role": "best_run",
        "workflow_type": workflow_type,
        entry_key: entry_value,
        "summary_path": summary_path,
        "config_snapshot_path": config_snapshot_path,
        "core_metrics": core_metrics,
        "artifact_paths": artifact_paths,
    }
    if extras:
        payload.update(extras)
    save_json(output_path, payload)
    return payload


def build_transformer_workflow_context(args, train_dataset=None, eval_dataset=None):
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
    )

    from ml_assets.workspace.data.constants import ID2LABEL, LABEL2ID
    from ml_assets.workspace.data.processing import (
        build_tokenized_datasets,
        build_train_eval_datasets,
    )
    from ml_assets.workspace.evaluation.metrics import compute_metrics

    seed_everything(args.seed)

    if train_dataset is None or eval_dataset is None:
        train_dataset, eval_dataset = build_train_eval_datasets(args)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name_or_path)
    tokenized_train, tokenized_eval = build_tokenized_datasets(
        train_dataset,
        eval_dataset,
        tokenizer,
        args.max_length,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name_or_path,
        num_labels=3,
        id2label={idx: label for idx, label in ID2LABEL.items()},
        label2id={label: idx for label, idx in LABEL2ID.items()},
    )
    trainer = Trainer(
        model=model,
        args=build_training_args(args),
        train_dataset=tokenized_train,
        eval_dataset=tokenized_eval,
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )

    return TransformerWorkflowContext(
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        tokenized_train=tokenized_train,
        tokenized_eval=tokenized_eval,
        trainer=trainer,
    )


def finalize_transformer_training_run(args, workflow_context):
    from ml_assets.workspace.evaluation.metrics import (
        calculate_classification_metrics,
        predictions_from_logits,
    )
    from ml_assets.workspace.evaluation.reporting import save_json

    trainer = workflow_context.trainer
    trainer.train()
    trainer_metrics = trainer.evaluate()
    prediction_output = trainer.predict(workflow_context.tokenized_eval)
    prediction_ids = predictions_from_logits(prediction_output.predictions)
    evaluation_report = calculate_classification_metrics(
        prediction_output.label_ids,
        prediction_ids,
    )
    evaluation_report["target_macro_f1"] = args.target_macro_f1
    evaluation_report["meets_target_macro_f1"] = (
        evaluation_report["macro_f1"] >= args.target_macro_f1
    )

    trainer.save_model(str(args.output_dir))
    workflow_context.tokenizer.save_pretrained(str(args.output_dir))
    evaluation_report_path = args.output_dir / "evaluation_report.json"
    save_json(evaluation_report_path, evaluation_report)
    artifact_paths = save_run_metadata(
        args,
        workflow_context.train_dataset,
        workflow_context.eval_dataset,
        trainer_metrics,
        evaluation_report_path=evaluation_report_path,
    )

    return {
        "trainer_metrics": trainer_metrics,
        "evaluation_report": evaluation_report,
        "output_dir": str(args.output_dir),
        "evaluation_report_path": str(evaluation_report_path),
        "config_snapshot_path": artifact_paths["config_snapshot_path"],
        "result_summary_path": artifact_paths["result_summary_path"],
    }


def run_transformer_training_entrypoint(
    argv=None,
    *,
    description="运行统一的 Transformer 单次训练流程",
    completion_label="训练完成",
):
    from ml_assets.workspace.training.cli_args import parse_args
    from ml_assets.workspace.training.transformer_pipeline import train_transformer_model

    args = parse_args(argv, description=description)
    result = train_transformer_model(args)

    logger.info(completion_label)
    logger.info("模型已保存到: %s", args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

