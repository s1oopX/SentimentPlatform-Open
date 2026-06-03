"""Maintained queue and schedule preview entry point for training operations."""

import argparse
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_assets.workspace.training.operations import (
    build_queue_snapshot,
    build_schedule_preview,
    load_queue_spec,
    load_schedule_spec,
)
from ml_assets.workspace.training.ops_status import (
    build_operations_status_view,
    discover_operation_records,
    render_operations_status_text,
)
from ml_assets.workspace.training.launcher import run_workflow
from ml_assets.workspace.training.recovery import apply_retry_plan, build_retry_plan


SUPPORTED_FORMATS = ('text', 'json')


def _emit(payload, output_format):
    if output_format == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for line in payload:
        print(line)


def _capture_direct_call(func, *args):
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    exit_code = 0
    status = 'passed'
    error = None

    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        try:
            result = func(*args)
            if isinstance(result, int):
                exit_code = result
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
        except Exception as exc:
            status = 'failed'
            exit_code = 1
            error = f'{type(exc).__name__}: {exc}'

    if exit_code != 0 and status == 'passed':
        status = 'failed'

    stdout = stdout_buffer.getvalue()
    stderr = stderr_buffer.getvalue()
    if status != 'passed' and error is None:
        output = stderr.strip() or stdout.strip()
        error = output.splitlines()[-1] if output else f'Command exited with code {exit_code}'

    return {
        'status': status,
        'exit_code': exit_code,
        'stdout': stdout,
        'stderr': stderr,
        'error': error,
    }


def _ordered_items(mapping, preferred_keys=()):
    seen = set()
    for key in preferred_keys:
        if key in mapping:
            seen.add(key)
            yield key, mapping[key]
    for key in sorted(mapping):
        if key in seen:
            continue
        yield key, mapping[key]


def _append_mapping_section(lines, title, mapping, *, indent=0, preferred_keys=()):
    prefix = '  ' * indent
    if not mapping:
        lines.append(f'{prefix}{title}: {{}}')
        return

    lines.append(f'{prefix}{title}:')
    for key, value in _ordered_items(mapping, preferred_keys):
        lines.append(f'{prefix}  {key}: {value}')


def _append_steps_section(lines, steps, *, indent=0):
    prefix = '  ' * indent
    if not steps:
        lines.append(f'{prefix}steps: []')
        return

    lines.append(f'{prefix}steps:')
    item_prefix = '  ' * (indent + 1)
    value_prefix = '  ' * (indent + 2)
    for step in steps:
        lines.append(f"{item_prefix}- label: {step['label']}")
        lines.append(f"{value_prefix}kind: {step['kind']}")
        lines.append(f"{value_prefix}argv: {json.dumps(step.get('argv', []), ensure_ascii=False)}")
        _append_mapping_section(
            lines,
            'artifact_paths',
            step.get('artifact_paths', {}),
            indent=indent + 2,
            preferred_keys=(
                'summary_path',
                'config_snapshot_path',
                'spec_path',
                'queue_spec_path',
                'queue_snapshot_path',
                'schedule_spec_path',
                'schedule_preview_path',
            ),
        )


def render_queue_preview_text(payload, *, indent=0):
    prefix = '  ' * indent
    lines = [
        f"{prefix}queue_name: {payload['queue_name']}",
        f"{prefix}status: {payload['status']}",
        f"{prefix}summary_output_dir: {payload['summary_output_dir']}",
        f"{prefix}total_steps: {payload['total_steps']}",
        f"{prefix}pending_steps: {payload['pending_steps']}",
    ]
    _append_steps_section(lines, payload.get('steps', []), indent=indent)
    _append_mapping_section(
        lines,
        'artifact_paths',
        payload.get('artifact_paths', {}),
        indent=indent,
        preferred_keys=(
            'spec_path',
            'queue_spec_path',
            'summary_output_dir',
            'queue_snapshot_path',
            'schedule_spec_path',
            'schedule_preview_path',
        ),
    )
    return lines


def render_schedule_preview_text(payload, *, indent=0):
    prefix = '  ' * indent
    lines = [
        f"{prefix}schedule_name: {payload['schedule_name']}",
    ]
    _append_mapping_section(
        lines,
        'cadence',
        payload.get('cadence', {}),
        indent=indent,
        preferred_keys=('frequency', 'hour', 'minute'),
    )
    lines.append(f"{prefix}queue_spec_path: {payload['queue_spec_path']}")
    lines.append(f"{prefix}queue_snapshot:")
    lines.extend(render_queue_preview_text(payload['queue_snapshot'], indent=indent + 1))
    _append_mapping_section(
        lines,
        'artifact_paths',
        payload.get('artifact_paths', {}),
        indent=indent,
        preferred_keys=(
            'spec_path',
            'schedule_spec_path',
            'queue_spec_path',
            'queue_snapshot_path',
            'schedule_preview_path',
        ),
    )
    return lines


def _render_preview_text(payload, command_name):
    if command_name == 'queue-preview':
        return render_queue_preview_text(payload)
    if command_name == 'schedule-preview':
        return render_schedule_preview_text(payload)
    if command_name == 'retry-preview':
        return render_retry_preview_text(payload)
    if command_name == 'retry-run':
        return render_retry_run_text(payload)
    raise ValueError(f'Unsupported command: {command_name}')


def _print_cli_error(command_name, exc):
    if isinstance(exc, FileNotFoundError):
        missing_path = exc.filename or str(exc)
        print(f'{command_name}: file not found: {missing_path}', file=sys.stderr)
        return 1

    if isinstance(exc, ValueError):
        error_kind = (
            'invalid summary'
            if command_name.startswith('retry-') or command_name == 'status'
            else 'invalid spec'
        )
        print(f'{command_name}: {error_kind}: {exc}', file=sys.stderr)
        return 1

    raise exc


def render_retry_preview_text(payload, *, indent=0):
    prefix = '  ' * indent
    lines = [
        f"{prefix}origin_summary_path: {payload['origin_summary_path']}",
        f"{prefix}retryable_steps: {payload['retryable_steps']}",
    ]
    steps = payload.get('steps', [])
    if not steps:
        lines.append(f'{prefix}steps: []')
        return lines

    lines.append(f'{prefix}steps:')
    item_prefix = '  ' * (indent + 1)
    value_prefix = '  ' * (indent + 2)
    for step in steps:
        lines.append(f"{item_prefix}- label: {step['label']}")
        lines.append(f"{value_prefix}kind: {step['kind']}")
        lines.append(f"{value_prefix}command: {step['command']}")
        lines.append(f"{value_prefix}argv: {json.dumps(step.get('argv', []), ensure_ascii=False)}")
        lines.append(f"{value_prefix}attempt_number: {step['attempt_number']}")
        _append_mapping_section(
            lines,
            'artifact_paths',
            step.get('artifact_paths', {}),
            indent=indent + 2,
            preferred_keys=('summary_path', 'origin_summary_path'),
        )
    return lines


def render_retry_run_text(payload, *, indent=0):
    prefix = '  ' * indent
    lines = [
        f"{prefix}origin_summary_path: {payload['origin_summary_path']}",
        f"{prefix}retryable_steps: {payload['retryable_steps']}",
        f"{prefix}status: {payload['status']}",
    ]
    results = payload.get('results', [])
    if not results:
        lines.append(f'{prefix}results: []')
        return lines

    lines.append(f'{prefix}results:')
    item_prefix = '  ' * (indent + 1)
    value_prefix = '  ' * (indent + 2)
    for result in results:
        lines.append(f"{item_prefix}- label: {result['label']}")
        lines.append(f"{value_prefix}status: {result['status']}")
        lines.append(f"{value_prefix}attempt_number: {result['attempt_number']}")
        lines.append(f"{value_prefix}command: {result['command']}")
        lines.append(f"{value_prefix}argv: {json.dumps(result.get('argv', []), ensure_ascii=False)}")
        lines.append(f"{value_prefix}exit_code: {result['exit_code']}")
        if 'error' in result:
            lines.append(f"{value_prefix}error: {result['error']}")
    return lines


def run_operation_step(step):
    kind = step.get('kind')
    command = step.get('command')
    argv = list(step.get('argv') or [])

    if kind == 'workflow':
        return _capture_direct_call(run_workflow, command, argv)

    return {
        'status': 'failed',
        'exit_code': 1,
        'stdout': '',
        'stderr': '',
        'error': f"Unsupported retry step kind '{kind}'",
    }


def handle_queue_preview(args):
    spec = load_queue_spec(args.spec)
    payload = build_queue_snapshot(spec)
    if args.format == 'json':
        _emit(payload, args.format)
    else:
        _emit(_render_preview_text(payload, 'queue-preview'), args.format)
    return 0


def handle_schedule_preview(args):
    schedule = load_schedule_spec(args.spec)
    payload = build_schedule_preview(schedule)
    if args.format == 'json':
        _emit(payload, args.format)
    else:
        _emit(_render_preview_text(payload, 'schedule-preview'), args.format)
    return 0


def handle_retry_preview(args):
    payload = build_retry_plan(args.summary, max_attempts=args.max_attempts)
    if args.format == 'json':
        _emit(payload, args.format)
    else:
        _emit(_render_preview_text(payload, 'retry-preview'), args.format)
    return 0


def handle_retry_run(args):
    plan = build_retry_plan(args.summary, max_attempts=args.max_attempts)
    payload = apply_retry_plan(plan, run_operation_step)
    if args.format == 'json':
        _emit(payload, args.format)
    else:
        _emit(_render_preview_text(payload, 'retry-run'), args.format)
    return 0 if payload['status'] == 'passed' else 1


def handle_status(args):
    records = discover_operation_records(args.root)
    payload = build_operations_status_view(records)
    if args.format == 'json':
        _emit(payload, args.format)
    else:
        _emit(render_operations_status_text(payload), args.format)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description='维护态训练队列与调度预览入口。',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    queue_parser = subparsers.add_parser('queue-preview', help='预览 queue spec 归一化结果')
    queue_parser.add_argument('--spec', type=Path, required=True, help='queue spec 路径')
    queue_parser.add_argument('--format', choices=SUPPORTED_FORMATS, default='text', help='输出格式')
    queue_parser.set_defaults(handler=handle_queue_preview)

    schedule_parser = subparsers.add_parser(
        'schedule-preview',
        help='预览 schedule spec materialization 结果',
    )
    schedule_parser.add_argument('--spec', type=Path, required=True, help='schedule spec 路径')
    schedule_parser.add_argument('--format', choices=SUPPORTED_FORMATS, default='text', help='输出格式')
    schedule_parser.set_defaults(handler=handle_schedule_preview)

    retry_preview_parser = subparsers.add_parser('retry-preview', help='预览失败步骤的 retry 计划')
    retry_preview_parser.add_argument('--summary', type=Path, required=True, help='operation summary 路径')
    retry_preview_parser.add_argument('--max-attempts', type=int, default=3, help='允许的最大尝试次数')
    retry_preview_parser.add_argument('--format', choices=SUPPORTED_FORMATS, default='text', help='输出格式')
    retry_preview_parser.set_defaults(handler=handle_retry_preview)

    retry_run_parser = subparsers.add_parser('retry-run', help='执行失败步骤的 retry 计划')
    retry_run_parser.add_argument('--summary', type=Path, required=True, help='operation summary 路径')
    retry_run_parser.add_argument('--max-attempts', type=int, default=3, help='允许的最大尝试次数')
    retry_run_parser.add_argument('--format', choices=SUPPORTED_FORMATS, default='text', help='输出格式')
    retry_run_parser.set_defaults(handler=handle_retry_run)

    status_parser = subparsers.add_parser('status', help='汇总 operations 与 retry summaries')
    status_parser.add_argument(
        '--root',
        type=Path,
        action='append',
        required=True,
        help='operations summary 根目录',
    )
    status_parser.add_argument('--format', choices=SUPPORTED_FORMATS, default='text', help='输出格式')
    status_parser.set_defaults(handler=handle_status)

    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError) as exc:
        return _print_cli_error(args.command, exc)


if __name__ == '__main__':
    raise SystemExit(main())

