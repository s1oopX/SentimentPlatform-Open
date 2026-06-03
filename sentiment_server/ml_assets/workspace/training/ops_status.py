import json
from datetime import datetime, timezone
from pathlib import Path


OPERATIONS_SUMMARY_PATTERN = 'operations_*_summary.json'
MAINTAINED_BATCH_SUMMARY_NAME = 'batch_summary.json'
RETRY_SUMMARY_PATTERN = 'retry_*_summary.json'
MAINTAINED_RETRY_SUMMARY_NAME = 'retry_batch_summary.json'


def _as_path(value):
    return value if isinstance(value, Path) else Path(value)


def _load_summary(path):
    path = _as_path(path).resolve()
    with path.open('r', encoding='utf-8') as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError('Summary payload must be a mapping')

    return path, payload


def _iter_matching_paths(root, pattern):
    root = _as_path(root)
    if not root.exists():
        return

    if root.is_file():
        if root.match(pattern) or root.name == pattern:
            yield root
        return

    yield from root.rglob(pattern)


def _record_type_for_path(path):
    return 'retry' if path.name.startswith('retry_') else 'operations'


def _iter_summary_paths(root):
    root = _as_path(root)
    if not root.exists():
        return

    patterns = (
        OPERATIONS_SUMMARY_PATTERN,
        MAINTAINED_BATCH_SUMMARY_NAME,
        RETRY_SUMMARY_PATTERN,
        MAINTAINED_RETRY_SUMMARY_NAME,
    )
    seen = set()
    for pattern in patterns:
        for path in _iter_matching_paths(root, pattern) or ():
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield resolved


def discover_operation_records(roots=None):
    roots = roots or []
    records = []
    seen_paths = set()

    for root in roots:
        for summary_path in _iter_summary_paths(root) or ():
            if summary_path in seen_paths:
                continue
            seen_paths.add(summary_path)
            loaded_path, payload = _load_summary(summary_path)
            record = dict(payload)
            record['record_type'] = _record_type_for_path(loaded_path)
            record['summary_path'] = str(loaded_path)
            record.setdefault('label', loaded_path.stem)
            records.append(record)

    return sorted(records, key=lambda item: (item.get('summary_path') or '', item.get('label') or ''))


def _coerce_int(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return None


def _sum_with_fallback(records, field, fallback):
    total = 0
    for record in records:
        value = _coerce_int(record.get(field))
        if value is None:
            total += fallback(record)
        else:
            total += value
    return total


def _result_items(record):
    results = record.get('results')
    if not isinstance(results, list):
        return []

    normalized = []
    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Operation result entry {index} must be a mapping")
        normalized.append(item)
    return normalized


def _failed_result_count(record):
    return sum(1 for item in _result_items(record) if item.get('status') != 'passed')


def _queued_operations_value(record):
    value = _coerce_int(record.get('queued_operations'))
    if value is not None:
        return value

    total_steps = _coerce_int(record.get('total_steps'))
    if total_steps is not None:
        return total_steps

    results = _result_items(record)
    if results:
        return len(results)

    return 1


def _failed_operations_value(record):
    value = _coerce_int(record.get('failed_operations'))
    if value is not None:
        return value

    failed_steps = _coerce_int(record.get('failed_steps'))
    if failed_steps is not None:
        return failed_steps

    if _result_items(record):
        return _failed_result_count(record)

    return 1 if record.get('status') == 'failed' else 0


def _retryable_operations_value(record):
    value = _coerce_int(record.get('retryable_operations'))
    if value is not None:
        return value

    if _result_items(record):
        return _failed_result_count(record)

    failed_steps = _coerce_int(record.get('failed_steps'))
    if failed_steps is not None:
        return failed_steps

    return 1 if record.get('status') == 'failed' else 0


def _scheduled_operations_value(record):
    value = _coerce_int(record.get('scheduled_operations'))
    if value is not None:
        return value

    if record.get('operation_type') in {'schedule', 'scheduled'} or record.get('scheduled'):
        return 1

    return 0


def _is_operations_record(record):
    return record.get('record_type') == 'operations'


def _is_retry_record(record):
    return record.get('record_type') == 'retry'


def _record_timestamp(record):
    for key in ('completed_at', 'updated_at', 'created_at', 'timestamp'):
        value = record.get(key)
        if not isinstance(value, str):
            continue
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            continue

    summary_path = record.get('summary_path')
    if summary_path:
        path = _as_path(summary_path)
        if path.exists():
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    return None


def _recovery_card(record):
    return {
        'label': record.get('label') or Path(record['summary_path']).stem,
        'status': record.get('status'),
        'completed_at': record.get('completed_at'),
        'summary_path': record['summary_path'],
        'origin_summary_path': record.get('origin_summary_path'),
        'source_kind': record.get('source_kind'),
        'total_steps': record.get('total_steps'),
        'failed_steps': record.get('failed_steps'),
        'retryable_steps': record.get('retryable_steps'),
    }


def _sorted_recoveries(records):
    def sort_key(record):
        timestamp = _record_timestamp(record)
        return (
            timestamp is None,
            -timestamp.timestamp() if timestamp else 0,
            record.get('summary_path') or '',
            record.get('label') or '',
        )

    return [_recovery_card(record) for record in sorted(records, key=sort_key)]


def build_operations_status_view(records):
    records = list(records or [])
    operations_records = [record for record in records if _is_operations_record(record)]
    retry_records = [record for record in records if _is_retry_record(record)]

    queued_operations = _sum_with_fallback(operations_records, 'queued_operations', _queued_operations_value)
    failed_operations = _sum_with_fallback(operations_records, 'failed_operations', _failed_operations_value)
    recovery_operations = _sum_with_fallback(retry_records, 'recovery_operations', lambda _: 1)
    retryable_operations = _sum_with_fallback(operations_records, 'retryable_operations', _retryable_operations_value)
    scheduled_operations = _sum_with_fallback(operations_records, 'scheduled_operations', _scheduled_operations_value)

    return {
        'totals': {
            'queued_operations': queued_operations,
            'failed_operations': failed_operations,
            'recovery_operations': recovery_operations,
        },
        'retry_health': {
            'retryable_operations': retryable_operations,
        },
        'schedule_health': {
            'scheduled_operations': scheduled_operations,
        },
        'recent_recoveries': _sorted_recoveries(retry_records),
    }


def render_operations_status_text(payload):
    lines = [
        f"queued_operations: {payload['totals']['queued_operations']}",
        f"failed_operations: {payload['totals']['failed_operations']}",
        f"recovery_operations: {payload['totals']['recovery_operations']}",
        f"retryable_operations: {payload['retry_health']['retryable_operations']}",
        f"scheduled_operations: {payload['schedule_health']['scheduled_operations']}",
    ]

    recoveries = payload.get('recent_recoveries', [])
    if not recoveries:
        lines.append('recent_recoveries: []')
        return lines

    lines.append('recent_recoveries:')
    for recovery in recoveries:
        lines.append(f"  - label: {recovery['label']}")
        lines.append(f"    status: {recovery.get('status')}")
        if recovery.get('completed_at'):
            lines.append(f"    completed_at: {recovery['completed_at']}")
        lines.append(f"    summary_path: {recovery['summary_path']}")
        if recovery.get('origin_summary_path'):
            lines.append(f"    origin_summary_path: {recovery['origin_summary_path']}")
    return lines
