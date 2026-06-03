import itertools
import random
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.data.constants import (
    DEFAULT_TRANSFORMER_SEARCH_DIR,
    get_transformer_output_dir,
)
from ml_assets.workspace.data.processing import (
    load_dataset_split,
    prepare_labeled_dataset,
)
from ml_assets.workspace.training.cli_args import (
    build_transformer_arg_parser,
    validate_args,
)
from ml_assets.workspace.training.artifacts import (
    build_config_snapshot,
    build_leaderboard_entry,
    build_result_summary,
    persist_experiment_artifacts,
    to_artifact_path,
)
from ml_assets.workspace.training.orchestration import (
    build_transformer_search_fold_args,
    build_transformer_search_run_args,
    clone_namespace,
    ensure_workflow_output_dir,
    finalize_ranked_workflow_outputs,
    persist_ranked_workflow_root_artifacts,
    write_best_run_summary,
)
from ml_assets.workspace.training.transformer_pipeline import train_transformer_model


def parse_args(
    argv=None,
    *,
    description="Transformer 搜索入口（也可使用 run_experiment.py transformer-search）",
):
    parser = build_transformer_arg_parser(
        description=description,
        default_output_dir=DEFAULT_TRANSFORMER_SEARCH_DIR,
    )
    parser.add_argument(
        "--search-type",
        choices=["grid", "random"],
        default="random",
        help="超参数搜索方式",
    )
    parser.add_argument("--max-trials", type=int, default=8, help="随机搜索最大实验次数")
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=3,
        help="Transformer 搜索阶段的交叉验证折数",
    )
    args = validate_args(
        parser.parse_args(argv),
        default_output_dir=DEFAULT_TRANSFORMER_SEARCH_DIR,
    )
    if args.cv_folds < 2:
        raise ValueError("cv_folds 至少为 2")
    if args.max_trials < 1:
        raise ValueError("max_trials 至少为 1")
    return args


def build_search_candidates():
    learning_rates = [1e-5, 2e-5, 3e-5, 5e-5]
    batch_sizes = [8, 16]
    weight_decays = [0.0, 0.01, 0.05]
    warmup_ratios = [0.0, 0.06, 0.1]
    epochs = [2.0, 3.0, 4.0]

    combinations = []
    for learning_rate, batch_size, weight_decay, warmup_ratio, num_train_epochs in itertools.product(
        learning_rates,
        batch_sizes,
        weight_decays,
        warmup_ratios,
        epochs,
    ):
        combinations.append(
            {
                "learning_rate": learning_rate,
                "per_device_train_batch_size": batch_size,
                "weight_decay": weight_decay,
                "warmup_ratio": warmup_ratio,
                "num_train_epochs": num_train_epochs,
            }
        )
    return combinations


def select_candidates(candidates, search_type, max_trials, seed):
    if search_type == "grid":
        return candidates
    if max_trials >= len(candidates):
        return candidates
    generator = random.Random(seed)
    return generator.sample(candidates, k=max_trials)


def summarize_fold_metrics(fold_reports):
    macro_f1_scores = np.array([report["macro_f1"] for report in fold_reports], dtype=float)
    accuracy_scores = np.array([report["accuracy"] for report in fold_reports], dtype=float)
    negative_recall_scores = np.array(
        [report["negative_recall"] for report in fold_reports],
        dtype=float,
    )
    return {
        "cv_macro_f1_mean": float(macro_f1_scores.mean()),
        "cv_macro_f1_std": float(macro_f1_scores.std()),
        "cv_accuracy_mean": float(accuracy_scores.mean()),
        "cv_accuracy_std": float(accuracy_scores.std()),
        "cv_negative_recall_mean": float(negative_recall_scores.mean()),
        "cv_negative_recall_std": float(negative_recall_scores.std()),
    }


def persist_search_candidate_artifacts(
    base_args,
    run_args,
    candidate,
    cv_summary,
    train_rows,
    eval_rows,
    fold_outputs,
):
    config_snapshot = build_config_snapshot(
        workflow_type="transformer_search_candidate",
        output_dir=run_args.output_dir,
        dataset={
            "train_dataset_path": str(base_args.train_dataset_path),
            "eval_dataset_path": str(base_args.eval_dataset_path),
            "train_rows": train_rows,
            "eval_rows": eval_rows,
        },
        runtime={
            "seed": run_args.seed,
            "search_type": base_args.search_type,
            "max_trials": base_args.max_trials,
            "cv_folds": base_args.cv_folds,
            "max_length": base_args.max_length,
            "per_device_eval_batch_size": base_args.per_device_eval_batch_size,
        },
        model={
            "model_name_or_path": base_args.model_name_or_path,
            "selected_hyperparameters": candidate,
        },
        extras={
            "experiment_name": getattr(base_args, "experiment_name", None),
            "run_name": run_args.output_dir.name,
        },
    )
    artifact_paths = {
        "fold_output_dirs": [item["output_dir"] for item in fold_outputs],
        "fold_result_summary_paths": [item["result_summary_path"] for item in fold_outputs],
        "fold_config_snapshot_paths": [item["config_snapshot_path"] for item in fold_outputs],
        "fold_evaluation_report_paths": [item["evaluation_report_path"] for item in fold_outputs],
    }
    result_summary = build_result_summary(
        workflow_type="transformer_search_candidate",
        output_dir=run_args.output_dir,
        core_metrics={
            "accuracy": cv_summary["cv_accuracy_mean"],
            "macro_f1": cv_summary["cv_macro_f1_mean"],
            "negative_recall": cv_summary["cv_negative_recall_mean"],
        },
        target_macro_f1=base_args.target_macro_f1,
        artifact_paths=artifact_paths,
        extras={
            "run_name": run_args.output_dir.name,
            "selection_metric": "cv_macro_f1_mean",
            "selected_hyperparameters": candidate,
            "cv_summary": cv_summary,
        },
    )
    return persist_experiment_artifacts(
        run_args.output_dir,
        config_snapshot=config_snapshot,
        result_summary=result_summary,
    )


def build_search_leaderboard_row(run_name, candidate, cv_summary, artifact_paths):
    return build_leaderboard_entry(
        workflow_type="transformer_search",
        entry_name=run_name,
        ranking_metric="cv_macro_f1_mean",
        core_metrics={
            "accuracy": cv_summary["cv_accuracy_mean"],
            "macro_f1": cv_summary["cv_macro_f1_mean"],
            "negative_recall": cv_summary["cv_negative_recall_mean"],
        },
        artifact_paths=artifact_paths,
        extras={
            "run_name": run_name,
            "learning_rate": candidate["learning_rate"],
            "per_device_train_batch_size": candidate["per_device_train_batch_size"],
            "weight_decay": candidate["weight_decay"],
            "warmup_ratio": candidate["warmup_ratio"],
            "num_train_epochs": candidate["num_train_epochs"],
            "cv_macro_f1_mean": cv_summary["cv_macro_f1_mean"],
            "cv_macro_f1_std": cv_summary["cv_macro_f1_std"],
            "cv_accuracy_mean": cv_summary["cv_accuracy_mean"],
            "cv_accuracy_std": cv_summary["cv_accuracy_std"],
            "cv_negative_recall_mean": cv_summary["cv_negative_recall_mean"],
            "cv_negative_recall_std": cv_summary["cv_negative_recall_std"],
        },
    )


def main(
    argv=None,
    *,
    description="Transformer 搜索入口（也可使用 run_experiment.py transformer-search）",
    completion_label="Transformer 超参数搜索定义已完成",
):
    args = parse_args(argv, description=description)
    ensure_workflow_output_dir(args.output_dir)
    full_train_dataset = prepare_labeled_dataset(load_dataset_split(args.train_dataset_path))
    test_dataset = prepare_labeled_dataset(load_dataset_split(args.eval_dataset_path))
    train_labels = list(full_train_dataset["label"])
    cv = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=args.seed)
    all_candidates = build_search_candidates()
    selected_candidates = select_candidates(
        all_candidates,
        search_type=args.search_type,
        max_trials=args.max_trials,
        seed=args.seed,
    )

    leaderboard_rows = []
    for run_index, candidate in enumerate(selected_candidates, start=1):
        run_args = build_transformer_search_run_args(args, candidate, run_index)
        fold_reports = []
        fold_outputs = []

        for fold_index, (train_indices, validation_indices) in enumerate(
            cv.split(np.zeros(len(train_labels)), train_labels),
            start=1,
        ):
            fold_train_dataset = full_train_dataset.select(train_indices.tolist())
            fold_validation_dataset = full_train_dataset.select(validation_indices.tolist())
            fold_args = build_transformer_search_fold_args(run_args, fold_index)

            fold_result = train_transformer_model(
                fold_args,
                train_dataset=fold_train_dataset,
                eval_dataset=fold_validation_dataset,
            )
            fold_reports.append(fold_result["evaluation_report"])
            fold_outputs.append(
                {
                    "output_dir": fold_result["output_dir"],
                    "result_summary_path": fold_result["result_summary_path"],
                    "config_snapshot_path": fold_result["config_snapshot_path"],
                    "evaluation_report_path": fold_result["evaluation_report_path"],
                }
            )

        cv_summary = summarize_fold_metrics(fold_reports)
        run_name = f"run_{run_index:03d}"
        candidate_artifact_paths = persist_search_candidate_artifacts(
            args,
            run_args,
            candidate,
            cv_summary,
            train_rows=len(full_train_dataset),
            eval_rows=len(test_dataset),
            fold_outputs=fold_outputs,
        )

        leaderboard_rows.append(
            build_search_leaderboard_row(
                run_name,
                candidate,
                cv_summary,
                artifact_paths={
                    "config_snapshot_path": candidate_artifact_paths["config_snapshot_path"],
                    "result_summary_path": candidate_artifact_paths["result_summary_path"],
                    "fold_output_dirs": [item["output_dir"] for item in fold_outputs],
                    "fold_result_summary_paths": [item["result_summary_path"] for item in fold_outputs],
                    "fold_config_snapshot_paths": [item["config_snapshot_path"] for item in fold_outputs],
                },
            )
        )

    ranked_workflow = finalize_ranked_workflow_outputs(
        args.output_dir,
        leaderboard_rows,
        ranking_key="cv_macro_f1_mean",
    )

    if ranked_workflow.leaderboard_rows:
        best_row = ranked_workflow.leaderboard_rows[0]
        best_candidate = {
            "learning_rate": best_row["learning_rate"],
            "per_device_train_batch_size": best_row["per_device_train_batch_size"],
            "weight_decay": best_row["weight_decay"],
            "warmup_ratio": best_row["warmup_ratio"],
            "num_train_epochs": best_row["num_train_epochs"],
        }
        final_output_dir = get_transformer_output_dir(
            args.model_name_or_path,
            experiment_name=getattr(args, "experiment_name", None),
        )
        final_args = clone_namespace(
            build_transformer_search_run_args(args, best_candidate, run_index=0),
            output_dir=final_output_dir,
            logging_dir=final_output_dir / "logs",
        )
        final_result = train_transformer_model(
            final_args,
            train_dataset=full_train_dataset,
            eval_dataset=test_dataset,
        )
        root_artifact_paths, root_result_summary = persist_ranked_workflow_root_artifacts(
            args.output_dir,
            workflow_type="transformer_search",
            target_macro_f1=args.target_macro_f1,
            dataset={
                "train_dataset_path": str(args.train_dataset_path),
                "eval_dataset_path": str(args.eval_dataset_path),
                "train_rows": len(full_train_dataset),
                "eval_rows": len(test_dataset),
            },
            runtime={
                "seed": args.seed,
                "search_type": args.search_type,
                "max_trials": args.max_trials,
                "cv_folds": args.cv_folds,
                "max_length": args.max_length,
                "per_device_eval_batch_size": args.per_device_eval_batch_size,
            },
            model={
                "model_name_or_path": args.model_name_or_path,
                "selected_hyperparameters": best_candidate,
            },
            core_metrics={
                "accuracy": final_result["evaluation_report"]["accuracy"],
                "macro_f1": final_result["evaluation_report"]["macro_f1"],
                "negative_recall": final_result["evaluation_report"]["negative_recall"],
            },
            artifact_paths={
                "leaderboard_path": to_artifact_path(ranked_workflow.leaderboard_path),
                "leaderboard_csv_path": to_artifact_path(ranked_workflow.leaderboard_csv_path),
                "best_run_path": to_artifact_path(ranked_workflow.best_run_path),
                "selected_candidate_summary_path": best_row["summary_path"],
                "selected_candidate_config_snapshot_path": best_row["config_snapshot_path"],
                "selected_model_dir": final_result["output_dir"],
                "selected_model_result_summary_path": final_result["result_summary_path"],
                "selected_model_config_snapshot_path": final_result["config_snapshot_path"],
                "selected_model_evaluation_report_path": final_result["evaluation_report_path"],
            },
            config_extras={
                "experiment_name": getattr(args, "experiment_name", None),
                "selected_run_name": best_row["run_name"],
            },
            summary_extras={
                "selection_metric": "cv_macro_f1_mean",
                "cv_folds": args.cv_folds,
                "selected_run_name": best_row["run_name"],
                "selected_hyperparameters": best_candidate,
                "cross_validation_result": best_row,
                "test_result": final_result["evaluation_report"],
            },
        )
        write_best_run_summary(
            ranked_workflow.best_run_path,
            workflow_type="transformer_search",
            entry_key="run_name",
            entry_value=best_row["run_name"],
            summary_path=root_artifact_paths["result_summary_path"],
            config_snapshot_path=root_artifact_paths["config_snapshot_path"],
            core_metrics=root_result_summary["core_metrics"],
            artifact_paths=root_result_summary["artifact_paths"],
            extras={
                "selection_metric": "cv_macro_f1_mean",
                "selected_hyperparameters": best_candidate,
                "cross_validation_result": best_row,
                "test_result": final_result["evaluation_report"],
                "output_dir": to_artifact_path(args.output_dir),
            },
        )

    print(completion_label)
    for row in ranked_workflow.leaderboard_rows:
        print(
            f"{row['run_name']}: "
            f"cv_macro_f1_mean={row['cv_macro_f1_mean']:.4f}, "
            f"cv_negative_recall_mean={row['cv_negative_recall_mean']:.4f}"
        )


if __name__ == "__main__":
    main()
