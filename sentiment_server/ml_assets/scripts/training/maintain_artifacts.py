import argparse
import json
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.data.constants import MODELS_DIR
from ml_assets.workspace.training.hygiene import (
    apply_cleanup_plan,
    build_cleanup_plan,
    discover_hygiene_records,
    load_hygiene_record,
    validate_hygiene_record,
)
from ml_assets.workspace.training.lifecycle import (
    apply_retention_plan,
    build_retention_plan,
    discover_lifecycle_records,
    load_lifecycle_record,
)


SUPPORTED_FORMATS = ("text", "json")


def _emit(payload, output_format):
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if isinstance(payload, list):
        for line in payload:
            print(line)
        return

    print(payload)


def _default_roots(paths):
    if paths:
        return [Path(path) for path in paths]
    return [MODELS_DIR]


def _dedupe_records(records):
    deduped = {}
    for record in records:
        deduped[record["path"]] = record
    return list(deduped.values())


def _validation_payload(record):
    findings = validate_hygiene_record(record)
    cleanup_plan = build_cleanup_plan(record)
    return {
        "path": record["path"],
        "experiment_name": record["experiment_name"],
        "workflow_type": record["workflow_type"],
        "is_valid": findings["is_valid"],
        "missing_required_artifacts": findings["missing_required_artifacts"],
        "invalid_json_files": findings["invalid_json_files"],
        "broken_references": findings["broken_references"],
        "preserved_paths": cleanup_plan["preserved_paths"],
        "cleanup_candidates": cleanup_plan["cleanup_candidates"],
    }


def _render_validate_text(payloads):
    if not payloads:
        return ["No experiments found."]

    lines = []
    for payload in payloads:
        status = "OK" if payload["is_valid"] else "ISSUES"
        lines.append(
            f"{status} | {payload['workflow_type']} | "
            f"{payload['experiment_name']} | path={payload['path']}"
        )

        if payload["missing_required_artifacts"]:
            lines.append("missing_required_artifacts:")
            for item in payload["missing_required_artifacts"]:
                lines.append(f"- {item['name']}: {item['path']}")

        if payload["invalid_json_files"]:
            lines.append("invalid_json_files:")
            for item in payload["invalid_json_files"]:
                lines.append(f"- {item['path']}: {item['error']}")

        if payload["broken_references"]:
            lines.append("broken_references:")
            for item in payload["broken_references"]:
                lines.append(f"- {item['label']}: {item['path']}")

        lines.append(f"preserved_paths: {len(payload['preserved_paths'])}")
        lines.append(f"cleanup_candidates: {len(payload['cleanup_candidates'])}")

    return lines


def _render_cleanup_text(payloads):
    if not payloads:
        return ["No experiments found."]

    lines = []
    for payload in payloads:
        header = "APPLIED" if payload["applied"] else "DRY-RUN"
        lines.append(
            f"{header} | {payload['workflow_type']} | "
            f"{payload['experiment_name']} | path={payload['path']}"
        )
        lines.append(f"preserved_paths: {len(payload['preserved_paths'])}")
        lines.append(f"cleanup_candidates: {len(payload['cleanup_candidates'])}")
        if payload["removed_paths"]:
            lines.append("removed_paths:")
            for item in payload["removed_paths"]:
                lines.append(f"- {item}")
    return lines


def _render_retention_text(payloads):
    if not payloads:
        return ["No experiments found."]

    lines = []
    for payload in payloads:
        lines.append(
            f"{payload['action'].upper()} | {payload['workflow_type']} | "
            f"{payload['experiment_name']} | path={payload['path']}"
        )
        lines.append(f"reason: {payload['reason']}")
        lines.append(f"archive_root: {payload['archive_root']}")
        lines.append(f"archive_path: {payload['archive_path']}")
        lines.append(f"archive_manifest: {payload['archive_manifest_path']}")
        lines.append(f"preserved_paths: {len(payload['preserved_paths'])}")
    return lines


def _render_archive_text(payloads):
    if not payloads:
        return ["No experiments found."]

    lines = []
    for payload in payloads:
        header = "APPLIED" if payload["applied"] else "DRY-RUN"
        lines.append(
            f"{header} | {payload['action'].upper()} | {payload['workflow_type']} | "
            f"{payload['experiment_name']} | path={payload['path']}"
        )
        lines.append(f"reason: {payload['reason']}")
        lines.append(f"archive_root: {payload['archive_root']}")
        lines.append(f"archive_path: {payload['archive_path']}")
        lines.append(f"archive_manifest: {payload['archive_manifest_path']}")
        lines.append(f"preserved_paths: {len(payload['preserved_paths'])}")
    return lines


def _load_records(args):
    records = []
    if args.path:
        records.extend(load_hygiene_record(path) for path in args.path)
    records.extend(
        discover_hygiene_records(
            roots=_default_roots(args.root),
            workflow_names=args.workflow,
        )
    )
    return _dedupe_records(records)


def _load_lifecycle_records(args):
    records = []
    if args.path:
        records.extend(
            load_lifecycle_record(path, archive_root=args.archive_root)
            for path in args.path
        )
    records.extend(
        discover_lifecycle_records(
            roots=_default_roots(args.root),
            workflow_names=args.workflow,
            archive_root=args.archive_root,
        )
    )
    return _dedupe_records(records)


def handle_validate(args):
    records = _load_records(args)
    payload = [_validation_payload(record) for record in records]
    if args.format == "json":
        _emit(payload, args.format)
        return
    _emit(_render_validate_text(payload), args.format)


def handle_cleanup(args):
    records = _load_records(args)
    payload = []
    for record in records:
        cleanup_plan = build_cleanup_plan(record)
        removed_paths = []
        if args.apply:
            removed_paths = apply_cleanup_plan(cleanup_plan)
        payload.append(
            {
                "path": record["path"],
                "experiment_name": record["experiment_name"],
                "workflow_type": record["workflow_type"],
                "applied": args.apply,
                "preserved_paths": cleanup_plan["preserved_paths"],
                "cleanup_candidates": cleanup_plan["cleanup_candidates"],
                "removed_paths": removed_paths,
            }
        )

    if args.format == "json":
        _emit(payload, args.format)
        return
    _emit(_render_cleanup_text(payload), args.format)


def handle_retention(args):
    records = _load_lifecycle_records(args)
    payload = [build_retention_plan(record, archive_root=args.archive_root) for record in records]
    if args.format == "json":
        _emit(payload, args.format)
        return
    _emit(_render_retention_text(payload), args.format)


def handle_archive(args):
    records = _load_lifecycle_records(args)
    payload = []
    for record in records:
        retention_plan = build_retention_plan(record, archive_root=args.archive_root)
        archive_result = apply_retention_plan(retention_plan) if args.apply else {
            "applied": False,
            "archive_root": retention_plan["archive_root"],
            "archive_path": retention_plan["archive_path"],
            "archive_manifest_path": retention_plan["archive_manifest_path"],
            "archive_manifest": retention_plan["archive_manifest"],
        }
        payload.append(
            {
                "path": retention_plan["path"],
                "experiment_name": retention_plan["experiment_name"],
                "workflow_type": retention_plan["workflow_type"],
                "action": retention_plan["action"],
                "reason": retention_plan["reason"],
                "applied": archive_result["applied"],
                "archive_root": archive_result["archive_root"],
                "archive_path": archive_result["archive_path"],
                "archive_manifest_path": archive_result["archive_manifest_path"],
                "archive_manifest": archive_result["archive_manifest"],
                "preserved_paths": retention_plan["preserved_paths"],
            }
        )

    if args.format == "json":
        _emit(payload, args.format)
        return
    _emit(_render_archive_text(payload), args.format)


def build_parser(
    description="维护态实验产物维护入口：校验和清理已完成实验 artifact。",
):
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest="command", metavar="command")
    subparsers.required = True

    validate_parser = subparsers.add_parser("validate", help="校验实验 artifact 完整性")
    validate_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    validate_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    validate_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    validate_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    validate_parser.set_defaults(handler=handle_validate)

    cleanup_parser = subparsers.add_parser("cleanup", help="预览或执行实验 artifact 清理")
    cleanup_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    cleanup_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    cleanup_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    cleanup_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    cleanup_parser.add_argument("--apply", action="store_true", help="实际执行清理；默认仅 dry-run")
    cleanup_parser.set_defaults(handler=handle_cleanup)

    retention_parser = subparsers.add_parser("retention", help="预览实验 retention / archive 策略")
    retention_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    retention_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    retention_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    retention_parser.add_argument("--archive-root", type=Path, default=None, help="归档根目录；默认使用 maintained archive root")
    retention_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    retention_parser.set_defaults(handler=handle_retention)

    archive_parser = subparsers.add_parser("archive", help="预览或执行实验归档")
    archive_parser.add_argument("--root", action="append", default=[], help="实验根目录；可重复传入")
    archive_parser.add_argument("--path", type=Path, action="append", default=[], help="直接指定实验根目录；可重复传入")
    archive_parser.add_argument("--workflow", action="append", default=[], help="按 workflow_type 过滤")
    archive_parser.add_argument("--archive-root", type=Path, default=None, help="归档根目录；默认使用 maintained archive root")
    archive_parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="text", help="输出格式")
    archive_parser.add_argument("--apply", action="store_true", help="实际执行归档；默认仅 dry-run")
    archive_parser.set_defaults(handler=handle_archive)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    main()

