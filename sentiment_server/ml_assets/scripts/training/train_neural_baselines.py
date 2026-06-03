import argparse
import sys
from pathlib import Path

import torch


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.data.constants import (
    DEFAULT_EVAL_SPLIT_DIR,
    DEFAULT_NEURAL_OUTPUT_DIR,
    DEFAULT_TRAIN_SPLIT_DIR,
)
from ml_assets.workspace.data.processing import load_train_eval_texts_and_labels
from ml_assets.workspace.evaluation.reporting import save_json
from ml_assets.workspace.training.artifacts import (
    build_config_snapshot,
    build_leaderboard_entry,
    build_result_summary,
    persist_experiment_artifacts,
    to_artifact_path,
)
from ml_assets.workspace.training.neural_baselines import (
    build_char_vocab,
    build_dataloader,
    build_neural_model,
    train_with_early_stopping,
)
from ml_assets.workspace.training.orchestration import (
    build_child_output_dir,
    ensure_workflow_output_dir,
    finalize_ranked_workflow_outputs,
    persist_ranked_workflow_root_artifacts,
    write_best_run_summary,
)
from ml_assets.workspace.training.utils import seed_everything


def parse_args(
    argv=None,
    *,
    description="神经网络基线训练入口（也可使用 run_experiment.py neural-baselines）",
):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--train-dataset-path",
        type=Path,
        default=DEFAULT_TRAIN_SPLIT_DIR,
        help=f"训练集目录，例如 {DEFAULT_TRAIN_SPLIT_DIR}",
    )
    parser.add_argument(
        "--eval-dataset-path",
        type=Path,
        default=DEFAULT_EVAL_SPLIT_DIR,
        help=f"验证集目录，例如 {DEFAULT_EVAL_SPLIT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="神经网络基线模型输出目录；默认遵循统一的训练工作区命名规则",
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="实验名称；未显式传入 output-dir 时会作为统一输出目录的子目录名",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=["textcnn", "bilstm"],
        default=["textcnn", "bilstm"],
        help="需要训练的神经网络基线模型",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--target-macro-f1", type=float, default=0.85, help="目标测试集 Macro-F1 阈值")
    parser.add_argument("--max-length", type=int, default=256, help="最大字符长度")
    parser.add_argument("--min-freq", type=int, default=2, help="字符最小词频")
    parser.add_argument("--embed-dim", type=int, default=128, help="嵌入维度")
    parser.add_argument("--hidden-size", type=int, default=128, help="BiLSTM 隐层维度")
    parser.add_argument("--num-filters", type=int, default=128, help="TextCNN 卷积通道数")
    parser.add_argument("--kernel-sizes", type=int, nargs="+", default=[2, 3, 4], help="TextCNN 卷积核大小")
    parser.add_argument("--dropout", type=float, default=0.3, help="Dropout 比例")
    parser.add_argument(
        "--num-epochs",
        "--epochs",
        dest="num_epochs",
        type=int,
        default=10,
        help="训练轮数",
    )
    parser.add_argument(
        "--batch-size",
        "--train-batch-size",
        dest="batch_size",
        type=int,
        default=64,
        help="Batch size",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-3, help="学习率")
    parser.add_argument("--weight-decay", type=float, default=1e-2, help="权重衰减")
    parser.add_argument("--patience", type=int, default=3, help="Early stopping patience")
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="训练设备，例如 cpu/cuda",
    )
    args = parser.parse_args(argv)
    if args.output_dir is None:
        args.output_dir = build_child_output_dir(
            DEFAULT_NEURAL_OUTPUT_DIR,
            args.experiment_name,
        )
    if not 0 < args.target_macro_f1 <= 1:
        raise ValueError("target_macro_f1 必须位于 0 到 1 之间")
    if args.max_length < max(args.kernel_sizes):
        raise ValueError("max_length 不能小于最大的卷积核尺寸")
    return args


def persist_neural_model_artifacts(
    args,
    model_name,
    model_output_dir,
    train_rows,
    eval_rows,
    best_metrics,
    final_metrics,
    history,
    model_path,
    vocab_path,
    report_path,
):
    config_snapshot = build_config_snapshot(
        workflow_type="neural_baseline_model",
        output_dir=model_output_dir,
        dataset={
            "train_dataset_path": str(args.train_dataset_path),
            "eval_dataset_path": str(args.eval_dataset_path),
            "train_rows": train_rows,
            "eval_rows": eval_rows,
        },
        runtime={
            "seed": args.seed,
            "max_length": args.max_length,
            "min_freq": args.min_freq,
            "embed_dim": args.embed_dim,
            "hidden_size": args.hidden_size,
            "num_filters": args.num_filters,
            "kernel_sizes": args.kernel_sizes,
            "dropout": args.dropout,
            "num_epochs": args.num_epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "patience": args.patience,
            "device": args.device,
        },
        model={
            "model_name": model_name,
        },
        extras={
            "experiment_name": getattr(args, "experiment_name", None),
        },
    )
    result_summary = build_result_summary(
        workflow_type="neural_baseline_model",
        output_dir=model_output_dir,
        core_metrics={
            "accuracy": final_metrics["accuracy"],
            "macro_f1": final_metrics["macro_f1"],
            "negative_recall": final_metrics["negative_recall"],
        },
        target_macro_f1=args.target_macro_f1,
        artifact_paths={
            "model_path": to_artifact_path(model_path),
            "vocab_path": to_artifact_path(vocab_path),
            "report_path": to_artifact_path(report_path),
        },
        extras={
            "model_name": model_name,
            "best_metrics": best_metrics,
            "history": history,
        },
    )
    return persist_experiment_artifacts(
        model_output_dir,
        config_snapshot=config_snapshot,
        result_summary=result_summary,
    )


def build_neural_leaderboard_row(model_name, final_metrics, meets_target, artifact_paths):
    return build_leaderboard_entry(
        workflow_type="neural_baseline_train",
        entry_name=model_name,
        ranking_metric="eval_macro_f1",
        core_metrics={
            "accuracy": final_metrics["accuracy"],
            "macro_f1": final_metrics["macro_f1"],
            "negative_recall": final_metrics["negative_recall"],
        },
        artifact_paths=artifact_paths,
        extras={
            "model_name": model_name,
            "eval_macro_f1": final_metrics["macro_f1"],
            "eval_accuracy": final_metrics["accuracy"],
            "eval_negative_recall": final_metrics["negative_recall"],
            "meets_target_macro_f1": meets_target,
        },
    )


def main(
    argv=None,
    *,
    description="神经网络基线训练入口（也可使用 run_experiment.py neural-baselines）",
    completion_label="神经网络基线训练定义已完成",
):
    args = parse_args(argv, description=description)
    seed_everything(args.seed)
    train_texts, train_labels, eval_texts, eval_labels = load_train_eval_texts_and_labels(
        args.train_dataset_path,
        args.eval_dataset_path,
    )

    vocab = build_char_vocab(train_texts, min_freq=args.min_freq)
    train_loader = build_dataloader(
        train_texts,
        train_labels,
        vocab,
        args.max_length,
        args.batch_size,
        shuffle=True,
    )
    eval_loader = build_dataloader(
        eval_texts,
        eval_labels,
        vocab,
        args.max_length,
        args.batch_size,
        shuffle=False,
    )

    ensure_workflow_output_dir(args.output_dir)
    leaderboard_rows = []

    for model_name in args.models:
        model = build_neural_model(
            model_name=model_name,
            vocab_size=len(vocab),
            num_classes=3,
            embed_dim=args.embed_dim,
            hidden_size=args.hidden_size,
            dropout=args.dropout,
            num_filters=args.num_filters,
            kernel_sizes=args.kernel_sizes,
        ).to(args.device)

        result = train_with_early_stopping(
            model=model,
            train_loader=train_loader,
            eval_loader=eval_loader,
            device=args.device,
            num_epochs=args.num_epochs,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
            patience=args.patience,
        )

        model_output_dir = build_child_output_dir(args.output_dir, model_name)
        ensure_workflow_output_dir(model_output_dir)
        model_path = model_output_dir / "model.pt"
        vocab_path = model_output_dir / "vocab.json"
        torch.save(model.state_dict(), model_path)
        save_json(
            vocab_path,
            {
                "token_to_id": vocab.token_to_id,
                "pad_id": vocab.pad_id,
                "unk_id": vocab.unk_id,
            },
        )

        final_metrics = result["final_metrics"]
        report = {
            "model_name": model_name,
            "target_macro_f1": args.target_macro_f1,
            "meets_target_macro_f1": final_metrics["macro_f1"] >= args.target_macro_f1,
            "config": {
                "max_length": args.max_length,
                "min_freq": args.min_freq,
                "embed_dim": args.embed_dim,
                "hidden_size": args.hidden_size,
                "num_filters": args.num_filters,
                "kernel_sizes": args.kernel_sizes,
                "dropout": args.dropout,
                "num_epochs": args.num_epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "weight_decay": args.weight_decay,
                "patience": args.patience,
                "device": args.device,
            },
            "history": result["history"],
            "best_metrics": result["best_metrics"],
                "final_metrics": final_metrics,
        }
        report_path = model_output_dir / "report.json"
        save_json(report_path, report)
        meets_target = final_metrics["macro_f1"] >= args.target_macro_f1
        artifact_paths = persist_neural_model_artifacts(
            args,
            model_name,
            model_output_dir,
            train_rows=len(train_texts),
            eval_rows=len(eval_texts),
            best_metrics=result["best_metrics"],
            final_metrics=final_metrics,
            history=result["history"],
            model_path=model_path,
            vocab_path=vocab_path,
            report_path=report_path,
        )

        leaderboard_rows.append(
            build_neural_leaderboard_row(
                model_name,
                final_metrics,
                meets_target,
                artifact_paths={
                    "config_snapshot_path": artifact_paths["config_snapshot_path"],
                    "result_summary_path": artifact_paths["result_summary_path"],
                    "model_path": to_artifact_path(model_path),
                    "vocab_path": to_artifact_path(vocab_path),
                    "report_path": to_artifact_path(report_path),
                },
            )
        )

    ranked_workflow = finalize_ranked_workflow_outputs(
        args.output_dir,
        leaderboard_rows,
        ranking_key="eval_macro_f1",
    )

    if ranked_workflow.leaderboard_rows:
        best_row = ranked_workflow.leaderboard_rows[0]
        root_artifact_paths, root_result_summary = persist_ranked_workflow_root_artifacts(
            args.output_dir,
            workflow_type="neural_baseline_train",
            target_macro_f1=args.target_macro_f1,
            dataset={
                "train_dataset_path": str(args.train_dataset_path),
                "eval_dataset_path": str(args.eval_dataset_path),
                "train_rows": len(train_texts),
                "eval_rows": len(eval_texts),
            },
            runtime={
                "seed": args.seed,
                "max_length": args.max_length,
                "min_freq": args.min_freq,
                "embed_dim": args.embed_dim,
                "hidden_size": args.hidden_size,
                "num_filters": args.num_filters,
                "kernel_sizes": args.kernel_sizes,
                "dropout": args.dropout,
                "num_epochs": args.num_epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "weight_decay": args.weight_decay,
                "patience": args.patience,
                "device": args.device,
            },
            model={
                "models": args.models,
            },
            core_metrics={
                "accuracy": best_row["eval_accuracy"],
                "macro_f1": best_row["eval_macro_f1"],
                "negative_recall": best_row["eval_negative_recall"],
            },
            artifact_paths={
                "leaderboard_path": to_artifact_path(ranked_workflow.leaderboard_path),
                "leaderboard_csv_path": to_artifact_path(ranked_workflow.leaderboard_csv_path),
                "best_run_path": to_artifact_path(ranked_workflow.best_run_path),
                "best_model_summary_path": best_row["summary_path"],
                "best_model_config_snapshot_path": best_row["config_snapshot_path"],
                "best_model_path": best_row["artifact_paths"]["model_path"],
                "best_model_vocab_path": best_row["artifact_paths"]["vocab_path"],
                "best_model_report_path": best_row["artifact_paths"]["report_path"],
            },
            config_extras={
                "experiment_name": getattr(args, "experiment_name", None),
                "best_model_name": best_row["model_name"],
            },
            summary_extras={
                "best_model_name": best_row["model_name"],
                "leaderboard_size": len(ranked_workflow.leaderboard_rows),
            },
        )
        write_best_run_summary(
            ranked_workflow.best_run_path,
            workflow_type="neural_baseline_train",
            entry_key="model_name",
            entry_value=best_row["model_name"],
            summary_path=root_artifact_paths["result_summary_path"],
            config_snapshot_path=root_artifact_paths["config_snapshot_path"],
            core_metrics=root_result_summary["core_metrics"],
            artifact_paths=root_result_summary["artifact_paths"],
        )

    print(completion_label)
    for row in ranked_workflow.leaderboard_rows:
        print(
            f"{row['model_name']}: "
            f"eval_macro_f1={row['eval_macro_f1']:.4f}, "
            f"eval_negative_recall={row['eval_negative_recall']:.4f}"
        )


if __name__ == "__main__":
    main()
