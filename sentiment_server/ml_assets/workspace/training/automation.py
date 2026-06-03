import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


BATCH_SUMMARY_NAME = "batch_summary.json"
REGRESSION_SUMMARY_NAME = "regression_summary.json"


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _normalize_step(step, index):
    label = step.get("label") or f"step-{index:02d}"
    workflow = step.get("workflow")
    if not workflow:
        raise ValueError(f"Batch step '{label}' is missing 'workflow'")

    argv = step.get("argv") or []
    if not isinstance(argv, list):
        raise ValueError(f"Batch step '{label}' must provide argv as a list")

    return {
        "label": label,
        "workflow": workflow,
        "argv": [str(item) for item in argv],
    }


def load_batch_spec(path):
    path = _as_path(path)
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    steps = [
        _normalize_step(step, index)
        for index, step in enumerate(payload.get("steps", []), start=1)
    ]
    if not steps:
        raise ValueError("Batch spec must contain at least one step")

    summary_output_dir = payload.get("summary_output_dir")
    if not summary_output_dir:
        raise ValueError("Batch spec must define 'summary_output_dir'")

    return {
        "path": str(path.resolve()),
        "summary_output_dir": str(_as_path(summary_output_dir).resolve()),
        "steps": steps,
    }


def _summary_filename(kind):
    if kind == "batch":
        return BATCH_SUMMARY_NAME
    if kind == "regression":
        return REGRESSION_SUMMARY_NAME
    return f"{kind}_summary.json"


def build_execution_summary(kind, output_dir, results, metadata=None):
    output_dir = _as_path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / _summary_filename(kind)

    total = len(results)
    failed = sum(1 for item in results if item.get("status") != "passed")
    summary = {
        "kind": kind,
        "status": "passed" if failed == 0 else "failed",
        "summary_output_dir": str(output_dir),
        "total_steps": total,
        "failed_steps": failed,
        "results": results,
        "summary_path": str(summary_path),
    }
    if metadata:
        summary.update(metadata)

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return summary


def render_execution_summary_text(summary):
    total = summary.get("total_checks", summary.get("total_steps"))
    failed = summary.get("failed_checks", summary.get("failed_steps"))
    lines = [
        f"{summary['status'].upper()} | kind={summary['kind']} | total={total} | failed={failed}",
        f"summary_path: {summary['summary_path']}",
    ]
    results = summary.get("suite_results", summary.get("results", []))
    for result in results:
        workflow = result.get("workflow")
        prefix = f"- {result['label']}"
        if workflow:
            prefix = f"{prefix} | {workflow}"
        lines.append(
            f"{prefix} | {result['status']} | exit_code={result['exit_code']}"
        )
    return lines


def _capture_runner_output(func, *args, **kwargs):
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    exit_code = 0
    status = "passed"
    error = None

    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, int):
                exit_code = result
        except SystemExit as exc:
            exit_code = exc.code or 0
        except Exception as exc:  # pragma: no cover - exercised via regression summary, not bespoke unit tests
            status = "failed"
            exit_code = 1
            error = f"{type(exc).__name__}: {exc}"

    if exit_code != 0 and status == "passed":
        status = "failed"

    return {
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout_buffer.getvalue(),
        "stderr": stderr_buffer.getvalue(),
        "error": error,
    }


def run_batch_plan(spec, runner):
    results = []
    for step in spec["steps"]:
        outcome = _capture_runner_output(runner, step["workflow"], step["argv"])
        results.append(
            {
                "label": step["label"],
                "workflow": step["workflow"],
                "argv": list(step["argv"]),
                "status": outcome["status"],
                "exit_code": outcome["exit_code"],
                "stdout": outcome["stdout"],
                "stderr": outcome["stderr"],
                "error": outcome["error"],
            }
        )

    return build_execution_summary(
        "batch",
        spec["summary_output_dir"],
        results,
        metadata={
            "spec_path": spec["path"],
        },
    )


def run_regression_suite(suite_name, checks, output_dir):
    results = []
    for check in checks:
        label = check["label"]
        outcome = _capture_runner_output(check["runner"])
        results.append(
            {
                "label": label,
                "status": outcome["status"],
                "exit_code": outcome["exit_code"],
                "stdout": outcome["stdout"],
                "stderr": outcome["stderr"],
                "error": outcome["error"],
            }
        )

    summary = build_execution_summary(
        "regression",
        output_dir,
        results,
        metadata={
            "suite_name": suite_name,
            "total_checks": len(results),
            "failed_checks": sum(1 for item in results if item["status"] != "passed"),
            "suite_results": results,
        },
    )
    return summary
