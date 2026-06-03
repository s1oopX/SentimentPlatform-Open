import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path


QUEUE_SNAPSHOT_NAME = 'queue_snapshot.json'


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _load_json(path):
    with path.open('r', encoding='utf-8') as file:
        return json.load(file)


def _resolve_path(value, *, relative_to=None):
    path = _as_path(value)
    if path.is_absolute() or relative_to is None:
        return path.resolve()
    return (relative_to / path).resolve()


def _normalize_artifact_paths(payload, *, relative_to=None):
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError('artifact_paths must be a mapping')

    artifact_paths = {}
    for key, value in payload.items():
        if value is None:
            artifact_paths[key] = None
            continue
        artifact_paths[key] = str(_resolve_path(value, relative_to=relative_to))
    return artifact_paths


def _normalize_queue_step(step, index, *, relative_to):
    if not isinstance(step, dict):
        raise ValueError(f"Queue step {index} must be a mapping")

    kind = step.get('kind')
    if not kind:
        raise ValueError(f"Queue step {index} is missing 'kind'")

    argv = step.get('argv') or []
    if not isinstance(argv, list):
        raise ValueError(f"Queue step {index} must provide argv as a list")

    normalized = dict(step)
    normalized['kind'] = str(kind)
    normalized['label'] = str(step.get('label') or f'step-{index:02d}')
    normalized['argv'] = [str(item) for item in argv]
    normalized['artifact_paths'] = _normalize_artifact_paths(
        step.get('artifact_paths'),
        relative_to=relative_to,
    )
    return normalized


def _queue_snapshot_path(summary_output_dir):
    return _as_path(summary_output_dir).resolve() / QUEUE_SNAPSHOT_NAME


def _schedule_preview_path(path):
    path = _as_path(path).resolve()
    return path.with_name(f'{path.stem}.preview.json')


def load_queue_spec(path):
    path = _as_path(path).resolve()
    payload = _load_json(path)

    summary_output_dir = payload.get('summary_output_dir')
    if not summary_output_dir:
        raise ValueError("Queue spec must define 'summary_output_dir'")

    steps = [
        _normalize_queue_step(step, index, relative_to=path.parent)
        for index, step in enumerate(payload.get('steps', []), start=1)
    ]
    if not steps:
        raise ValueError('Queue spec must contain at least one step')

    summary_output_dir = _resolve_path(summary_output_dir, relative_to=path.parent)
    artifact_paths = _normalize_artifact_paths(
        payload.get('artifact_paths'),
        relative_to=path.parent,
    )
    artifact_paths['spec_path'] = str(path)
    artifact_paths['queue_spec_path'] = str(path)
    artifact_paths['summary_output_dir'] = str(summary_output_dir)
    artifact_paths['queue_snapshot_path'] = str(_queue_snapshot_path(summary_output_dir))

    return {
        'path': str(path),
        'queue_name': str(payload.get('queue_name') or path.stem),
        'summary_output_dir': str(summary_output_dir),
        'steps': steps,
        'artifact_paths': artifact_paths,
    }


def load_schedule_spec(path):
    path = _as_path(path).resolve()
    payload = _load_json(path)

    queue_spec_path = payload.get('queue_spec_path')
    if not queue_spec_path:
        raise ValueError("Schedule spec must define 'queue_spec_path'")

    cadence = payload.get('cadence') or {}
    if not isinstance(cadence, dict):
        raise ValueError("Schedule spec must provide 'cadence' as a mapping")

    frequency = cadence.get('frequency')
    if not frequency:
        raise ValueError("Schedule spec cadence must define 'frequency'")
    frequency = str(frequency).lower()
    if frequency not in {'hourly', 'daily'}:
        raise ValueError("Schedule spec cadence frequency must be 'hourly' or 'daily'")
    cadence = dict(cadence)
    cadence['frequency'] = frequency

    queue_spec_path = str(_resolve_path(queue_spec_path, relative_to=path.parent))
    schedule_preview_path = _schedule_preview_path(path)

    artifact_paths = _normalize_artifact_paths(
        payload.get('artifact_paths'),
        relative_to=path.parent,
    )
    queue_spec = load_queue_spec(queue_spec_path)
    artifact_paths['spec_path'] = str(path)
    artifact_paths['schedule_spec_path'] = str(path)
    artifact_paths['queue_spec_path'] = queue_spec_path
    artifact_paths['queue_snapshot_path'] = queue_spec['artifact_paths']['queue_snapshot_path']
    artifact_paths['schedule_preview_path'] = str(schedule_preview_path)

    return {
        'path': str(path),
        'schedule_name': str(payload.get('schedule_name') or path.stem),
        'cadence': cadence,
        'queue_spec_path': queue_spec_path,
        'artifact_paths': artifact_paths,
    }


def build_queue_snapshot(spec, *, status='pending'):
    steps = deepcopy(spec['steps'])
    summary_output_dir = _as_path(spec['summary_output_dir']).resolve()
    artifact_paths = deepcopy(spec.get('artifact_paths', {}))
    artifact_paths['spec_path'] = spec.get('path') or artifact_paths.get('spec_path')
    artifact_paths['queue_spec_path'] = spec.get('path') or artifact_paths.get('queue_spec_path')
    artifact_paths['summary_output_dir'] = str(summary_output_dir)
    artifact_paths['queue_snapshot_path'] = str(_queue_snapshot_path(summary_output_dir))

    pending_steps = len(steps) if status == 'pending' else 0
    return {
        'queue_name': spec['queue_name'],
        'status': status,
        'summary_output_dir': str(summary_output_dir),
        'total_steps': len(steps),
        'pending_steps': pending_steps,
        'steps': steps,
        'artifact_paths': artifact_paths,
    }


def build_schedule_preview(schedule, *, status='pending'):
    queue_spec = load_queue_spec(schedule['queue_spec_path'])

    queue_snapshot = build_queue_snapshot(queue_spec, status=status)
    artifact_paths = deepcopy(schedule.get('artifact_paths', {}))
    artifact_paths['spec_path'] = schedule.get('path') or artifact_paths.get('spec_path')
    artifact_paths['schedule_spec_path'] = schedule.get('path') or artifact_paths.get('schedule_spec_path')
    artifact_paths['queue_spec_path'] = schedule['queue_spec_path']
    artifact_paths['queue_snapshot_path'] = queue_snapshot['artifact_paths']['queue_snapshot_path']
    artifact_paths['schedule_preview_path'] = str(_schedule_preview_path(schedule['path']))
    artifact_paths['summary_output_dir'] = queue_snapshot['artifact_paths']['summary_output_dir']

    return {
        'path': schedule['path'],
        'schedule_name': schedule['schedule_name'],
        'cadence': dict(schedule['cadence']),
        'queue_spec_path': queue_spec['artifact_paths']['queue_spec_path'],
        'queue_snapshot': queue_snapshot,
        'artifact_paths': artifact_paths,
    }
