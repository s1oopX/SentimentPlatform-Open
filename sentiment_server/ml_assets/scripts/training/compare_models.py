import argparse
import sys
from pathlib import Path

import joblib
from sklearn.metrics import make_scorer
from sklearn.model_selection import (
    GridSearchCV,
    RandomizedSearchCV,
    StratifiedKFold,
    cross_validate,
)


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.data.constants import (
    DEFAULT_CLASSICAL_OUTPUT_DIR,
    DEFAULT_EVAL_SPLIT_DIR,
    DEFAULT_TRAIN_SPLIT_DIR,
)
from ml_assets.workspace.data.processing import load_train_eval_texts_and_labels
from ml_assets.workspace.evaluation.metrics import (
    calculate_classification_metrics,
    macro_f1_score,
    negative_recall_score,
)
from ml_assets.workspace.evaluation.reporting import save_json
from ml_assets.workspace.training.artifacts import (
    build_config_snapshot,
    build_leaderboard_entry,
    build_result_summary,
    persist_experiment_artifacts,
    to_artifact_path,
)
from ml_assets.workspace.training.classical_models import (
    build_estimator,
    get_search_space,
    get_supported_model_names,
)
from ml_assets.workspace.training.orchestration import (
    build_child_output_dir,
    ensure_workflow_output_dir,
    finalize_ranked_workflow_outputs,
    persist_ranked_workflow_root_artifacts,
    write_best_run_summary,
)


def parse_args(
    argv=None,
    *,
    description="传统模型比较入口（也可使用 run_experiment.py classical-compare）",
):
    supported_models = get_supported_model_names()
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
        help="模型比较结果输出目录；默认遵循统一的训练工作区命名规则",
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
        default=supported_models,
        choices=supported_models,
        help="需要比较的模型列表",
    )
    parser.add_argument(
        "--search-type",
        type=str,
        choices=["none", "grid", "random"],
        default="random",
        help="超参数搜索方式",
    )
    parser.add_argument(
        "--random-iter",
        "--max-trials",
        dest="max_trials",
        type=int,
        default=12,
        help="随机搜索迭代次数",
    )
    parser.add_argument("--cv-folds", type=int, default=5, help="交叉验证折数")
    parser.add_argument("--n-jobs", type=int, default=-1, help="并行 worker 数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--target-macro-f1", type=float, default=0.85, help="目标测试集 Macro-F1 阈值")
    parser.add_argument("--verbose", type=int, default=1, help="搜索日志级别")
    args = parser.parse_args(argv)

    if args.output_dir is None:
        args.output_dir = build_child_output_dir(
            DEFAULT_CLASSICAL_OUTPUT_DIR,
            args.experiment_name,
        )

    if not 0 < args.target_macro_f1 <= 1:
        raise ValueError("target_macro_f1 必须位于 0 到 1 之间")
    if args.cv_folds < 2:
        raise ValueError("cv_folds 至少为 2")
    if args.max_trials < 1:
        raise ValueError("max_trials 至少为 1")
    return args


def build_scoring():
    return {
        "accuracy": "accuracy",
        "macro_f1": make_scorer(macro_f1_score),
        "negative_recall": make_scorer(negative_recall_score),
    }


def summarize_cv_scores(cv_results):
    return {
        "cv_accuracy_mean": float(cv_results["test_accuracy"].mean()),
        "cv_accuracy_std": float(cv_results["test_accuracy"].std()),
        "cv_macro_f1_mean": float(cv_results["test_macro_f1"].mean()),
        "cv_macro_f1_std": float(cv_results["test_macro_f1"].std()),
        "cv_negative_recall_mean": float(cv_results["test_negative_recall"].mean()),
        "cv_negative_recall_std": float(cv_results["test_negative_recall"].std()),
    }


def run_model_search(model_name, args, train_texts, train_labels, cv, scoring):
    estimator = build_estimator(model_name, args.seed)

    if args.search_type == "none":
        cv_results = cross_validate(
            estimator,
            train_texts,
            train_labels,
            cv=cv,
            scoring=scoring,
            n_jobs=args.n_jobs,
        )
        estimator.fit(train_texts, train_labels)
        return estimator, {}, summarize_cv_scores(cv_results), None

    search_space = get_search_space(model_name, args.search_type)
    common_kwargs = {
        "estimator": estimator,
        "cv": cv,
        "scoring": scoring,
        "refit": "macro_f1",
        "n_jobs": args.n_jobs,
        "verbose": args.verbose,
    }
    if args.search_type == "grid":
        search = GridSearchCV(
            param_grid=search_space,
            **common_kwargs,
        )
    else:
        search = RandomizedSearchCV(
            param_distributions=search_space,
            n_iter=args.max_trials,
            random_state=args.seed,
            **common_kwargs,
        )

    search.fit(train_texts, train_labels)
    best_cv_scores = {
        "cv_accuracy_mean": float(search.cv_results_["mean_test_accuracy"][search.best_index_]),
        "cv_accuracy_std": float(search.cv_results_["std_test_accuracy"][search.best_index_]),
        "cv_macro_f1_mean": float(search.cv_results_["mean_test_macro_f1"][search.best_index_]),
        "cv_macro_f1_std": float(search.cv_results_["std_test_macro_f1"][search.best_index_]),
        "cv_negative_recall_mean": float(
            search.cv_results_["mean_test_negative_recall"][search.best_index_]
        ),
        "cv_negative_recall_std": float(
            search.cv_results_["std_test_negative_recall"][search.best_index_]
        ),
    }
    return search.best_estimator_, search.best_params_, best_cv_scores, search.cv_results_


def persist_classical_model_artifacts(
    args,
    model_name,
    model_output_dir,
    train_rows,
    eval_rows,
    cv_summary,
    eval_metrics,
    best_params,
    report_path,
    model_path,
):
    config_snapshot = build_config_snapshot(
        workflow_type="classical_compare_model",
        output_dir=model_output_dir,
        dataset={
            "train_dataset_path": str(args.train_dataset_path),
            "eval_dataset_path": str(args.eval_dataset_path),
            "train_rows": train_rows,
            "eval_rows": eval_rows,
        },
        runtime={
            "seed": args.seed,
            "search_type": args.search_type,
            "max_trials": args.max_trials,
            "cv_folds": args.cv_folds,
            "n_jobs": args.n_jobs,
            "verbose": args.verbose,
        },
        model={
            "model_name": model_name,
        },
        extras={
            "experiment_name": getattr(args, "experiment_name", None),
        },
    )
    result_summary = build_result_summary(
        workflow_type="classical_compare_model",
        output_dir=model_output_dir,
        core_metrics={
            "accuracy": eval_metrics["accuracy"],
            "macro_f1": eval_metrics["macro_f1"],
            "negative_recall": eval_metrics["negative_recall"],
        },
        target_macro_f1=args.target_macro_f1,
        artifact_paths={
            "model_path": to_artifact_path(model_path),
            "report_path": to_artifact_path(report_path),
        },
        extras={
            "model_name": model_name,
            "search_type": args.search_type,
            "best_params": best_params,
            "cv_summary": cv_summary,
        },
    )
    return persist_experiment_artifacts(
        model_output_dir,
        config_snapshot=config_snapshot,
        result_summary=result_summary,
    )


def build_classical_leaderboard_row(
    model_name,
    search_type,
    cv_summary,
    eval_metrics,
    meets_target,
    best_params,
    artifact_paths,
):
    return build_leaderboard_entry(
        workflow_type="classical_compare",
        entry_name=model_name,
        ranking_metric="eval_macro_f1",
        core_metrics={
            "accuracy": eval_metrics["accuracy"],
            "macro_f1": eval_metrics["macro_f1"],
            "negative_recall": eval_metrics["negative_recall"],
        },
        artifact_paths=artifact_paths,
        extras={
            "model_name": model_name,
            "search_type": search_type,
            "cv_macro_f1_mean": cv_summary["cv_macro_f1_mean"],
            "cv_accuracy_mean": cv_summary["cv_accuracy_mean"],
            "cv_negative_recall_mean": cv_summary["cv_negative_recall_mean"],
            "eval_macro_f1": eval_metrics["macro_f1"],
            "eval_accuracy": eval_metrics["accuracy"],
            "eval_negative_recall": eval_metrics["negative_recall"],
            "meets_target_macro_f1": meets_target,
            "best_params": best_params,
        },
    )


def main(
    argv=None,
    *,
    description="传统模型比较入口（也可使用 run_experiment.py classical-compare）",
    completion_label="传统模型比较完成",
):
    args = parse_args(argv, description=description)
    scoring = build_scoring()
    cv = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=args.seed)
    train_texts, train_labels, eval_texts, eval_labels = load_train_eval_texts_and_labels(
        args.train_dataset_path,
        args.eval_dataset_path,
    )

    ensure_workflow_output_dir(args.output_dir)
    leaderboard_rows = []

    for model_name in args.models:
        best_estimator, best_params, cv_summary, raw_cv_results = run_model_search(
            model_name,
            args,
            train_texts,
            train_labels,
            cv,
            scoring,
        )

        eval_predictions = best_estimator.predict(eval_texts)
        eval_metrics = calculate_classification_metrics(eval_labels, eval_predictions)
        meets_target = eval_metrics["macro_f1"] >= args.target_macro_f1

        model_output_dir = build_child_output_dir(args.output_dir, model_name)
        ensure_workflow_output_dir(model_output_dir)
        model_path = model_output_dir / "model.joblib"
        joblib.dump(best_estimator, model_path)

        report = {
            "model_name": model_name,
            "search_type": args.search_type,
            "target_macro_f1": args.target_macro_f1,
            "meets_target_macro_f1": meets_target,
            "train_rows": len(train_texts),
            "eval_rows": len(eval_texts),
            "best_params": best_params,
            "cv_summary": cv_summary,
            "eval_metrics": eval_metrics,
        }
        if raw_cv_results is not None:
            report["cv_results"] = raw_cv_results
        report_path = model_output_dir / "report.json"
        save_json(report_path, report)
        artifact_paths = persist_classical_model_artifacts(
            args,
            model_name,
            model_output_dir,
            train_rows=len(train_texts),
            eval_rows=len(eval_texts),
            cv_summary=cv_summary,
            eval_metrics=eval_metrics,
            best_params=best_params,
            report_path=report_path,
            model_path=model_path,
        )

        leaderboard_rows.append(
            build_classical_leaderboard_row(
                model_name,
                args.search_type,
                cv_summary,
                eval_metrics,
                meets_target,
                best_params,
                artifact_paths={
                    "config_snapshot_path": artifact_paths["config_snapshot_path"],
                    "result_summary_path": artifact_paths["result_summary_path"],
                    "model_path": to_artifact_path(model_path),
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
            workflow_type="classical_compare",
            target_macro_f1=args.target_macro_f1,
            dataset={
                "train_dataset_path": str(args.train_dataset_path),
                "eval_dataset_path": str(args.eval_dataset_path),
                "train_rows": len(train_texts),
                "eval_rows": len(eval_texts),
            },
            runtime={
                "seed": args.seed,
                "search_type": args.search_type,
                "max_trials": args.max_trials,
                "cv_folds": args.cv_folds,
                "n_jobs": args.n_jobs,
                "verbose": args.verbose,
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
                "best_model_report_path": best_row["artifact_paths"]["report_path"],
            },
            config_extras={
                "experiment_name": getattr(args, "experiment_name", None),
                "best_model_name": best_row["model_name"],
            },
            summary_extras={
                "best_model_name": best_row["model_name"],
                "best_params": best_row["best_params"],
                "search_type": args.search_type,
                "leaderboard_size": len(ranked_workflow.leaderboard_rows),
            },
        )
        write_best_run_summary(
            ranked_workflow.best_run_path,
            workflow_type="classical_compare",
            entry_key="model_name",
            entry_value=best_row["model_name"],
            summary_path=root_artifact_paths["result_summary_path"],
            config_snapshot_path=root_artifact_paths["config_snapshot_path"],
            core_metrics=root_result_summary["core_metrics"],
            artifact_paths=root_result_summary["artifact_paths"],
            extras={
                "best_params": best_row["best_params"],
            },
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
