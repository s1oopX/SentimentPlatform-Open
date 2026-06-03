import json
from copy import deepcopy
from pathlib import Path


RETRYABLE_STATUS = 'failed'
TERMINAL_SUCCESS_STATUS = 'passed'
SUPPORTED_SUMMARY_KINDS = {'batch'}
RETRY_SUMMARY_PREFIX = 'retry_'


def _load_summary(path):
    path = Path(path).resolve()
    with path.open('r', encoding='utf-8') as file:
        summary = json.load(file)
    if not isinstance(summary, dict):
        raise ValueError('Summary payload must be a mapping')
    return path, summary


def _normalize_attempt_number(step):
    return int(step.get('attempt_number', 1))


def _require_results_list(summary):
    results = summary.get('results')
    if not isinstance(results, list):
        raise ValueError("Summary 'results' must be a list")
    return results


def _normalize_artifact_paths(label, artifact_paths):
    if artifact_paths is None:
        return {}
    if not isinstance(artifact_paths, dict):
        raise ValueError(f"Batch result '{label}' must provide artifact_paths as a mapping")
    return deepcopy(artifact_paths)


def _normalize_batch_retry_step(step, *, summary, summary_path, max_attempts):
    if not isinstance(step, dict):
        raise ValueError('Each batch result must be a mapping')

    label = step.get('label') or 'unknown-step'
    status = step.get('status')
    if status == TERMINAL_SUCCESS_STATUS:
        return None
    if status != RETRYABLE_STATUS:
        raise ValueError(f"Step '{label}' is not retryable from status '{status}'")

    workflow = step.get('workflow')
    if not workflow:
        raise ValueError(f"Batch result '{label}' is missing 'workflow'")

    argv = step.get('argv')
    if argv is None:
        argv = []
    if not isinstance(argv, list):
        raise ValueError(f"Batch result '{label}' must provide argv as a list")

    attempts = _normalize_attempt_number(step)
    if attempts >= max_attempts:
        raise ValueError(f"Retry exhausted for step '{label}'")

    artifact_paths = _normalize_artifact_paths(label, step.get('artifact_paths'))
    artifact_paths['origin_summary_path'] = str(summary_path)
    if summary.get('summary_path'):
        artifact_paths.setdefault('summary_path', summary['summary_path'])

    return {
        'label': label,
        'kind': 'workflow',
        'command': str(workflow),
        'argv': [str(item) for item in argv],
        'attempt_number': attempts + 1,
        'origin_summary_path': str(summary_path),
        'artifact_paths': artifact_paths,
    }


def _retry_summary_path(origin_summary_path):
    origin_summary_path = Path(origin_summary_path).resolve()
    return origin_summary_path.with_name(f'{RETRY_SUMMARY_PREFIX}{origin_summary_path.name}')


def build_retry_plan(summary_path, *, max_attempts=3):
    summary_path, summary = _load_summary(summary_path)
    source_kind = summary.get('kind')
    if source_kind not in SUPPORTED_SUMMARY_KINDS:
        raise ValueError(f"Retry is not supported for summary kind '{source_kind}'")

    results = _require_results_list(summary)
    retry_steps = []

    for step in results:
        retry_step = _normalize_batch_retry_step(
            step,
            summary=summary,
            summary_path=summary_path,
            max_attempts=max_attempts,
        )
        if retry_step is None:
            continue
        retry_steps.append(retry_step)

    if not retry_steps:
        raise ValueError('No failed steps available for retry')

    return {
        'source_kind': source_kind,
        'origin_summary_path': str(summary_path),
        'summary_path': summary.get('summary_path', str(summary_path)),
        'retryable_steps': len(retry_steps),
        'steps': retry_steps,
    }


def apply_retry_plan(plan, runner):
    results = []
    for step in plan.get('steps', []):
        outcome = runner(step)
        results.append({**step, **outcome})

    failed_steps = sum(1 for item in results if item.get('status') != 'passed')
    summary_path = _retry_summary_path(plan['origin_summary_path'])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'kind': 'retry',
        'source_kind': plan.get('source_kind'),
        'origin_summary_path': plan['origin_summary_path'],
        'summary_path': str(summary_path),
        'total_steps': len(results),
        'failed_steps': failed_steps,
        'retryable_steps': plan['retryable_steps'],
        'results': results,
        'status': 'passed' if results and failed_steps == 0 else 'failed',
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary
