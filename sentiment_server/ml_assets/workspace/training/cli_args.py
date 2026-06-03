import argparse
from pathlib import Path

from ml_assets.workspace.data.constants import (
    DEFAULT_BASE_MODEL,
    DEFAULT_EVAL_SPLIT_DIR,
    DEFAULT_TRAIN_SPLIT_DIR,
    get_transformer_output_dir,
    resolve_output_dir,
)


def validate_args(args, *, default_output_dir=None):
    if args.fp16 and args.bf16:
        raise ValueError("fp16 和 bf16 不能同时启用")

    if args.train_dataset_path is None or args.eval_dataset_path is None:
        raise ValueError("必须显式传入 train_dataset_path 和 eval_dataset_path")

    experiment_name = getattr(args, "experiment_name", None)
    if args.output_dir is None:
        if default_output_dir is None:
            args.output_dir = get_transformer_output_dir(
                args.model_name_or_path,
                experiment_name=experiment_name,
            )
        else:
            args.output_dir = resolve_output_dir(
                default_output_dir,
                experiment_name=experiment_name,
            )

    if args.logging_dir is None:
        args.logging_dir = args.output_dir / "logs"

    if not 0 < args.target_macro_f1 <= 1:
        raise ValueError("target_macro_f1 必须位于 0 到 1 之间")

    if args.save_strategy != args.eval_strategy:
        raise ValueError("save_strategy 与 eval_strategy 必须保持一致，才能加载最佳模型")

    if args.save_strategy == "no":
        raise ValueError("save_strategy 不能为 'no'，否则无法在训练结束时加载最佳模型")

    return args


def build_transformer_arg_parser(
    *,
    description="复现中文新闻情感三分类训练流程",
    default_model_name_or_path=DEFAULT_BASE_MODEL,
    default_output_dir=None,
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
        "--model-name-or-path",
        type=str,
        default=default_model_name_or_path,
        help="基础模型名称或本地模型目录",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help="训练模型输出目录；默认遵循统一的训练工作区命名规则",
    )
    parser.add_argument(
        "--logging-dir",
        type=Path,
        default=None,
        help="TensorBoard 日志目录，默认落到输出目录下的 logs/",
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="实验名称；未显式传入 output-dir 时会作为统一输出目录的子目录名",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--max-length", type=int, default=256, help="最大文本长度")
    parser.add_argument(
        "--num-train-epochs",
        "--epochs",
        dest="num_train_epochs",
        type=float,
        default=3.0,
        help="训练轮数",
    )
    parser.add_argument("--learning-rate", type=float, default=2e-5, help="学习率")
    parser.add_argument("--weight-decay", type=float, default=0.01, help="权重衰减")
    parser.add_argument("--warmup-ratio", type=float, default=0.1, help="预热比例")
    parser.add_argument(
        "--per-device-train-batch-size",
        "--train-batch-size",
        dest="per_device_train_batch_size",
        type=int,
        default=16,
        help="单设备训练 batch size",
    )
    parser.add_argument(
        "--per-device-eval-batch-size",
        "--eval-batch-size",
        dest="per_device_eval_batch_size",
        type=int,
        default=32,
        help="单设备验证 batch size",
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=1,
        help="梯度累积步数",
    )
    parser.add_argument(
        "--save-total-limit",
        type=int,
        default=2,
        help="最多保留多少份 checkpoint",
    )
    parser.add_argument(
        "--lr-scheduler-type",
        type=str,
        default="cosine",
        help="学习率调度器类型，如 linear/cosine",
    )
    parser.add_argument(
        "--fp16",
        action="store_true",
        help="是否启用 fp16；原 README 不建议默认开启",
    )
    parser.add_argument(
        "--bf16",
        action="store_true",
        help="是否启用 bf16",
    )
    parser.add_argument(
        "--dataloader-num-workers",
        type=int,
        default=4,
        help="DataLoader worker 数量",
    )
    parser.add_argument(
        "--save-strategy",
        type=str,
        default="epoch",
        choices=["no", "steps", "epoch"],
        help="保存策略",
    )
    parser.add_argument(
        "--eval-strategy",
        type=str,
        default="epoch",
        choices=["no", "steps", "epoch"],
        help="验证策略",
    )
    parser.add_argument(
        "--logging-steps",
        type=int,
        default=10,
        help="日志打印步数",
    )
    parser.add_argument(
        "--report-to",
        type=str,
        default="tensorboard",
        help="日志上报目标，传 none 可关闭",
    )
    parser.add_argument(
        "--target-macro-f1",
        type=float,
        default=0.85,
        help="目标测试集 Macro-F1 阈值",
    )
    return parser


def parse_args(
    argv=None,
    *,
    description="复现中文新闻情感三分类训练流程",
    default_model_name_or_path=DEFAULT_BASE_MODEL,
    default_output_dir=None,
):
    parser = build_transformer_arg_parser(
        description=description,
        default_model_name_or_path=default_model_name_or_path,
        default_output_dir=default_output_dir,
    )
    return validate_args(parser.parse_args(argv), default_output_dir=default_output_dir)

