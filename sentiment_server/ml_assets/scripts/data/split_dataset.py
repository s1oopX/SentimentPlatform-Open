import argparse
import sys
from pathlib import Path

from datasets import load_from_disk


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.data.constants import DEFAULT_DATASET_DIR
from ml_assets.workspace.data.processing import stratified_three_way_split


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "generated" / "splits"
TRACKED_SAMPLE_SPLITS_DIR = PROJECT_ROOT / "data" / "splits"


def validate_output_dir(output_dir, *, allow_tracked_output):
    resolved_output_dir = Path(output_dir).resolve()
    tracked_splits_dir = TRACKED_SAMPLE_SPLITS_DIR.resolve()
    if (
        (
            resolved_output_dir == tracked_splits_dir
            or tracked_splits_dir in resolved_output_dir.parents
        )
        and not allow_tracked_output
    ):
        raise ValueError(
            "Refusing to overwrite tracked sample splits without --allow-tracked-output."
        )
    return resolved_output_dir


def build_parser():
    parser = argparse.ArgumentParser(description="分层切分 canonical raw dataset。")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"切分输出目录，默认写入 {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--allow-tracked-output",
        action="store_true",
        help="仅在维护受控 sample split baseline 时允许写入 data/splits。",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    output_dir = validate_output_dir(
        args.output_dir,
        allow_tracked_output=args.allow_tracked_output,
    )
    dataset = load_from_disk(str(DEFAULT_DATASET_DIR))
    train_dataset, val_dataset, test_dataset = stratified_three_way_split(
        dataset,
        train_size=0.7,
        val_size=0.1,
        test_size=0.2,
        seed=42,
    )

    train_dir = output_dir / "train"
    val_dir = output_dir / "val"
    test_dir = output_dir / "test"
    output_dir.mkdir(parents=True, exist_ok=True)

    train_dataset.save_to_disk(str(train_dir))
    val_dataset.save_to_disk(str(val_dir))
    test_dataset.save_to_disk(str(test_dir))

    print(f"train saved to: {train_dir}  ({len(train_dataset)} rows)")
    print(f"val   saved to: {val_dir}    ({len(val_dataset)} rows)")
    print(f"test  saved to: {test_dir}   ({len(test_dataset)} rows)")
    print(
        "可通过 python scripts/training/run_experiment.py transformer-train "
        f"--train-dataset-path {train_dir} --eval-dataset-path {val_dir} 使用该切分结果训练"
    )


if __name__ == "__main__":
    main()
