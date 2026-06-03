import argparse
import json
from pathlib import Path
from dataclasses import dataclass

from ml_assets.workspace.training.automation import (
    load_batch_spec,
    render_execution_summary_text,
    run_batch_plan,
)


@dataclass(frozen=True)
class WorkflowSpec:
    workflow_name: str
    help_text: str
    description: str
    runner: object


def _run_transformer_train(
    argv=None,
    *,
    description="通过统一实验启动器执行 Transformer 单次训练",
    completion_label="Transformer 训练完成",
):
    from ml_assets.workspace.training.orchestration import run_transformer_training_entrypoint

    return run_transformer_training_entrypoint(
        argv,
        description=description,
        completion_label=completion_label,
    )


def _run_transformer_search(
    argv=None,
    *,
    description="通过统一实验启动器执行 Transformer 超参数搜索",
    completion_label="Transformer 超参数搜索定义已完成",
):
    from scripts.training import search_transformer

    return search_transformer.main(
        argv,
        description=description,
        completion_label=completion_label,
    )


def _run_classical_compare(
    argv=None,
    *,
    description="通过统一实验启动器执行传统模型比较",
    completion_label="传统模型比较完成",
):
    from scripts.training import compare_models

    return compare_models.main(
        argv,
        description=description,
        completion_label=completion_label,
    )


def _run_neural_baselines(
    argv=None,
    *,
    description="通过统一实验启动器执行神经网络基线训练",
    completion_label="神经网络基线训练定义已完成",
):
    from scripts.training import train_neural_baselines

    return train_neural_baselines.main(
        argv,
        description=description,
        completion_label=completion_label,
    )


workflow_registry = {
    "transformer-train": WorkflowSpec(
        workflow_name="transformer-train",
        help_text="执行 Transformer 单次训练",
        description="通过统一实验启动器执行 Transformer 单次训练",
        runner=_run_transformer_train,
    ),
    "transformer-search": WorkflowSpec(
        workflow_name="transformer-search",
        help_text="执行 Transformer 超参数搜索",
        description="通过统一实验启动器执行 Transformer 超参数搜索",
        runner=_run_transformer_search,
    ),
    "classical-compare": WorkflowSpec(
        workflow_name="classical-compare",
        help_text="比较传统机器学习基线模型",
        description="通过统一实验启动器执行传统模型比较",
        runner=_run_classical_compare,
    ),
    "neural-baselines": WorkflowSpec(
        workflow_name="neural-baselines",
        help_text="训练神经网络基线模型",
        description="通过统一实验启动器执行神经网络基线训练",
        runner=_run_neural_baselines,
    ),
}


BATCH_FORMATS = ("text", "json")

def _emit(payload, output_format):
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if isinstance(payload, list):
        for line in payload:
            print(line)
        return

    print(payload)

def handle_batch(args):
    spec = load_batch_spec(args.spec)
    summary = run_batch_plan(spec, run_workflow)
    if args.format == "json":
        _emit(summary, args.format)
        return 0
    _emit(render_execution_summary_text(summary), args.format)
    return 0 if summary["failed_steps"] == 0 else 1


def build_launcher_parser():
    parser = argparse.ArgumentParser(
        description="统一实验运行入口。使用 workflow 子命令发起 maintained training workflows。",
    )
    subparsers = parser.add_subparsers(dest="workflow", metavar="workflow")
    subparsers.required = True

    for spec in workflow_registry.values():
        subparsers.add_parser(
            spec.workflow_name,
            add_help=False,
            help=spec.help_text,
            description=spec.description,
        )

    batch_parser = subparsers.add_parser(
        "batch",
        help="按 batch spec 顺序执行多个 maintained workflow",
        description="通过统一实验启动器执行 batch spec 中的多个 maintained workflow。",
    )
    batch_parser.add_argument("--spec", type=Path, required=True, help="batch spec JSON 文件")
    batch_parser.add_argument("--format", choices=BATCH_FORMATS, default="text", help="输出格式")

    return parser


def run_workflow(workflow_name, argv=None, **overrides):
    try:
        spec = workflow_registry[workflow_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported workflow: {workflow_name}") from exc
    return spec.runner(argv, **overrides)


def main(argv=None):
    parser = build_launcher_parser()
    args, workflow_args = parser.parse_known_args(argv)
    if args.workflow == "batch":
        return handle_batch(args)
    return run_workflow(args.workflow, workflow_args)

