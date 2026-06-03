"""Maintained regression validation surface for the training workspace."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.training.automation import render_execution_summary_text, run_regression_suite


SUPPORTED_FORMATS = ("text", "json")
SUITE_NAME = "training-workspace-regression"


def _emit(payload, output_format):
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if isinstance(payload, list):
        for line in payload:
            print(line)
        return

    print(payload)


def _run_command(command):
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssertionError(
            f"Command failed ({completed.returncode}): {' '.join(str(part) for part in command)}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_batch_fixture_check(output_dir):
    def runner():
        fixture_root = output_dir / "_batch_fixture"
        fixture_root.mkdir(parents=True, exist_ok=True)
        spec_path = fixture_root / "batch_spec.json"
        batch_output_dir = fixture_root / "batch-output"
        spec_path.write_text(
            json.dumps(
                {
                    "summary_output_dir": str(batch_output_dir),
                    "steps": [
                        {
                            "label": "help-transformer-train-a",
                            "workflow": "transformer-train",
                            "argv": ["--help"],
                        },
                        {
                            "label": "help-transformer-train-b",
                            "workflow": "transformer-train",
                            "argv": ["--help"],
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        payload = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(CURRENT_DIR / "run_experiment.py"),
                    "batch",
                    "--spec",
                    str(spec_path),
                    "--format",
                    "json",
                ],
                text=True,
            )
        )
        summary_path = Path(payload["summary_path"])
        if payload["failed_steps"] != 0 or not summary_path.exists():
            raise AssertionError(
                f"Batch fixture smoke failed: failed_steps={payload['failed_steps']}, summary_path={summary_path}"
            )

    return runner


def _build_operations_fixture_check(output_dir):
    def runner():
        fixture_root = output_dir / "_operations_fixture"
        fixture_root.mkdir(parents=True, exist_ok=True)

        queue_spec_path = fixture_root / "queue_spec.json"
        schedule_spec_path = fixture_root / "schedule_spec.json"
        batch_root = fixture_root / "batch"
        status_root = fixture_root / "status"
        queue_summary_dir = fixture_root / "queue-output"

        _write_json(
            queue_spec_path,
            {
                "queue_name": "nightly-ops",
                "summary_output_dir": str(queue_summary_dir),
                "steps": [
                    {
                        "label": "train-transformer",
                        "kind": "workflow",
                        "workflow_name": "transformer_train",
                        "argv": ["--help"],
                    },
                    {
                        "label": "archive-old-runs",
                        "kind": "maintenance",
                        "command": "archive",
                        "argv": [],
                    },
                ],
            },
        )
        _write_json(
            schedule_spec_path,
            {
                "schedule_name": "daily-retention",
                "cadence": {
                    "frequency": "daily",
                    "hour": 3,
                    "minute": 15,
                },
                "queue_spec_path": str(queue_spec_path),
            },
        )

        queue_payload = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(CURRENT_DIR / "operate_training.py"),
                    "queue-preview",
                    "--spec",
                    str(queue_spec_path),
                    "--format",
                    "json",
                ],
                text=True,
            )
        )
        if (
            queue_payload["queue_name"] != "nightly-ops"
            or queue_payload["total_steps"] != 2
            or queue_payload["status"] != "pending"
        ):
            raise AssertionError(f"Queue preview smoke failed: {queue_payload}")

        schedule_payload = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(CURRENT_DIR / "operate_training.py"),
                    "schedule-preview",
                    "--spec",
                    str(schedule_spec_path),
                    "--format",
                    "json",
                ],
                text=True,
            )
        )
        if (
            schedule_payload["schedule_name"] != "daily-retention"
            or schedule_payload["queue_snapshot"]["queue_name"] != "nightly-ops"
            or schedule_payload["queue_snapshot"]["total_steps"] != 2
        ):
            raise AssertionError(f"Schedule preview smoke failed: {schedule_payload}")

        retry_source_path = batch_root / "fixture_source_summary.json"
        retry_summary_path = batch_root / "retry_fixture_source_summary.json"
        _write_json(
            retry_source_path,
            {
                "kind": "batch",
                "status": "failed",
                "summary_output_dir": str(batch_root),
                "total_steps": 2,
                "failed_steps": 1,
                "results": [
                    {
                        "label": "train-transformer",
                        "workflow": "transformer-train",
                        "argv": ["--help"],
                        "status": "failed",
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "boom",
                        "error": "ValueError: boom",
                    },
                    {
                        "label": "archive-old-runs",
                        "workflow": "transformer-search",
                        "argv": ["--help"],
                        "status": "passed",
                        "exit_code": 0,
                        "stdout": "",
                        "stderr": "",
                        "error": None,
                    },
                ],
                "summary_path": str(retry_source_path),
            },
        )

        retry_preview_payload = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(CURRENT_DIR / "operate_training.py"),
                    "retry-preview",
                    "--summary",
                    str(retry_source_path),
                    "--format",
                    "json",
                ],
                text=True,
            )
        )
        if retry_preview_payload["retryable_steps"] != 1:
            raise AssertionError(f"Retry preview smoke failed: {retry_preview_payload}")

        retry_run_payload = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(CURRENT_DIR / "operate_training.py"),
                    "retry-run",
                    "--summary",
                    str(retry_source_path),
                    "--format",
                    "json",
                ],
                text=True,
            )
        )
        if retry_run_payload["status"] != "passed" or retry_run_payload["retryable_steps"] != 1:
            raise AssertionError(f"Retry run smoke failed: {retry_run_payload}")
        if not retry_summary_path.exists():
            raise AssertionError(f"Retry run did not persist a retry summary at {retry_summary_path}")

        _write_json(
            status_root / "operations_queue_summary.json",
            {
                "kind": "operations",
                "label": "queue-nightly",
                "operation_type": "queue",
                "status": "passed",
                "queued_operations": 2,
                "failed_operations": 0,
                "scheduled_operations": 0,
                "retryable_operations": 0,
                "completed_at": "2026-04-03T08:00:00+08:00",
            },
        )
        _write_json(
            status_root / "operations_schedule_summary.json",
            {
                "kind": "operations",
                "label": "schedule-nightly",
                "operation_type": "schedule",
                "status": "failed",
                "queued_operations": 1,
                "failed_operations": 1,
                "scheduled_operations": 1,
                "retryable_operations": 1,
                "completed_at": "2026-04-03T09:00:00+08:00",
            },
        )

        status_payload = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(CURRENT_DIR / "operate_training.py"),
                    "status",
                    "--root",
                    str(status_root),
                    "--root",
                    str(batch_root),
                    "--format",
                    "json",
                ],
                text=True,
            )
        )
        if (
            status_payload["totals"]["queued_operations"] != 3
            or status_payload["totals"]["failed_operations"] != 1
            or status_payload["totals"]["recovery_operations"] != 1
            or status_payload["retry_health"]["retryable_operations"] != 1
            or status_payload["schedule_health"]["scheduled_operations"] != 1
        ):
            raise AssertionError(f"Status smoke failed: {status_payload}")

    return runner


def build_regression_checks(output_dir):
    compile_command = [
        sys.executable,
        "-m",
        "compileall",
        str(PROJECT_ROOT / "scripts/training"),
        str(PROJECT_ROOT / "workspace/training"),
        str(PROJECT_ROOT / "workspace/evaluation"),
    ]

    return [
        {
            "label": "compileall",
            "runner": lambda: _run_command(compile_command),
        },
        {
            "label": "launcher-batch-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "run_experiment.py"), "batch", "--help"]
            ),
        },
        {
            "label": "launcher-transformer-train-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "run_experiment.py"), "transformer-train", "--help"]
            ),
        },
        {
            "label": "operate-training-queue-preview-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "operate_training.py"), "queue-preview", "--help"]
            ),
        },
        {
            "label": "operate-training-schedule-preview-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "operate_training.py"), "schedule-preview", "--help"]
            ),
        },
        {
            "label": "operate-training-retry-preview-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "operate_training.py"), "retry-preview", "--help"]
            ),
        },
        {
            "label": "operate-training-retry-run-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "operate_training.py"), "retry-run", "--help"]
            ),
        },
        {
            "label": "operate-training-status-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "operate_training.py"), "status", "--help"]
            ),
        },
        {
            "label": "inspect-summary-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "inspect_experiments.py"), "summary", "--help"]
            ),
        },
        {
            "label": "maintain-retention-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "maintain_artifacts.py"), "retention", "--help"]
            ),
        },
        {
            "label": "maintain-archive-help",
            "runner": lambda: _run_command(
                [sys.executable, str(CURRENT_DIR / "maintain_artifacts.py"), "archive", "--help"]
            ),
        },
        {
            "label": "batch-fixture-smoke",
            "runner": _build_batch_fixture_check(output_dir),
        },
        {
            "label": "operations-fixture-smoke",
            "runner": _build_operations_fixture_check(output_dir),
        },
    ]


def handle_validate(args):
    output_dir = args.output_dir.resolve()
    checks = build_regression_checks(output_dir)
    summary = run_regression_suite(SUITE_NAME, checks, output_dir)
    if args.format == "json":
        _emit(summary, args.format)
        return 0 if summary["failed_checks"] == 0 else 1
    _emit(render_execution_summary_text(summary), args.format)
    return 0 if summary["failed_checks"] == 0 else 1


def build_parser():
    parser = argparse.ArgumentParser(
        description="维护态训练工作区回归验证入口。",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="回归摘要输出目录")
    parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    parser.set_defaults(handler=handle_validate)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    main()

