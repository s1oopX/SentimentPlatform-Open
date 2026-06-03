from ml_assets.workspace.training.history import build_history_browser_view


def _best_so_far(records):
    browser = build_history_browser_view(
        records,
        archived='all',
        ranked_only=False,
        meets_target='all',
        sort_by='best',
        limit=1,
    )
    return browser['items'][0] if browser['items'] else None


def _recent_regression(records, best_item):
    if not best_item:
        return None

    best_macro_f1 = best_item['metric_highlights'].get('macro_f1')
    recent_browser = build_history_browser_view(
        records,
        archived='active',
        ranked_only=False,
        meets_target='all',
        sort_by='recent',
        limit=len(records) or 1,
    )
    for item in recent_browser['items']:
        macro_f1 = item['metric_highlights'].get('macro_f1')
        if macro_f1 is None or best_macro_f1 is None:
            continue
        if macro_f1 < best_macro_f1:
            enriched = dict(item)
            enriched['delta_from_best'] = macro_f1 - best_macro_f1
            return enriched
    return None


def _archive_status(records):
    archived_records = sum(1 for item in records if '/_archive/' in str(item.get('path', '')).replace('\\', '/'))
    return {
        'total_records': len(records),
        'active_records': len(records) - archived_records,
        'archived_records': archived_records,
    }


def _recent_window(records, limit=3):
    return build_history_browser_view(
        records,
        archived='all',
        ranked_only=False,
        meets_target='all',
        sort_by='recent',
        limit=limit,
    )


def _workflow_statuses(records):
    browser = build_history_browser_view(
        records,
        archived='all',
        ranked_only=False,
        meets_target='all',
        sort_by='recent',
        limit=len(records) or 1,
    )
    grouped = {}
    for item in browser['items']:
        grouped.setdefault(item['workflow_type'], []).append(item)

    statuses = []
    for workflow_type, items in sorted(grouped.items(), key=lambda item: item[0]):
        latest = items[0]
        previous = items[1] if len(items) > 1 else None
        latest_metric = latest['metric_highlights'].get('macro_f1')
        previous_metric = previous['metric_highlights'].get('macro_f1') if previous else None
        best_metric = max(
            (
                entry['metric_highlights'].get('macro_f1')
                for entry in items
                if entry['metric_highlights'].get('macro_f1') is not None
            ),
            default=None,
        )

        if previous_metric is None or latest_metric is None:
            status_label = 'insufficient_history'
            delta_from_previous = None
        else:
            delta_from_previous = latest_metric - previous_metric
            if delta_from_previous > 0:
                status_label = 'improved'
            elif delta_from_previous < 0:
                status_label = 'regressed'
            else:
                status_label = 'steady'

        statuses.append(
            {
                'workflow_type': workflow_type,
                'status_label': status_label,
                'latest_item': latest,
                'previous_item': previous,
                'delta_from_previous': delta_from_previous,
                'delta_from_best': (
                    None
                    if latest_metric is None or best_metric is None
                    else latest_metric - best_metric
                ),
            }
        )

    return statuses


def _tracking_facets(records):
    browser = build_history_browser_view(
        records,
        archived='all',
        ranked_only=False,
        meets_target='all',
        sort_by='recent',
        limit=len(records) or 1,
    )
    workflow_counts = {}
    profile_counts = {}
    archive = {'active_records': 0, 'archived_records': 0}
    target = {'met': 0, 'unmet': 0, 'unknown': 0}

    for item in browser['items']:
        workflow_counts[item['workflow_type']] = workflow_counts.get(item['workflow_type'], 0) + 1
        profile_key = item.get('runtime_profile')
        profile_counts[profile_key] = profile_counts.get(profile_key, 0) + 1
        if item['status']['archived']:
            archive['archived_records'] += 1
        else:
            archive['active_records'] += 1
        target[item['status_labels']['target']] += 1

    return {
        'workflows': [
            {'workflow_type': key, 'record_count': workflow_counts[key]}
            for key in sorted(workflow_counts.keys(), key=str)
        ],
        'runtime_profiles': [
            {'runtime_profile': key, 'record_count': profile_counts[key]}
            for key in sorted(profile_counts.keys(), key=lambda value: '' if value is None else str(value))
        ],
        'archive': archive,
        'target': target,
    }


def _profile_statuses(records):
    browser = build_history_browser_view(
        records,
        archived='all',
        ranked_only=False,
        meets_target='all',
        sort_by='recent',
        limit=len(records) or 1,
    )
    grouped = {}
    for item in browser['items']:
        grouped.setdefault(item.get('runtime_profile'), []).append(item)

    statuses = []
    for runtime_profile, items in sorted(grouped.items(), key=lambda item: '' if item[0] is None else str(item[0])):
        latest = items[0]
        previous = items[1] if len(items) > 1 else None
        latest_metric = latest['metric_highlights'].get('macro_f1')
        previous_metric = previous['metric_highlights'].get('macro_f1') if previous else None
        best_metric = max(
            (
                entry['metric_highlights'].get('macro_f1')
                for entry in items
                if entry['metric_highlights'].get('macro_f1') is not None
            ),
            default=None,
        )

        if previous_metric is None or latest_metric is None:
            status_label = 'insufficient_history'
            delta_from_previous = None
        else:
            delta_from_previous = latest_metric - previous_metric
            if delta_from_previous > 0:
                status_label = 'improved'
            elif delta_from_previous < 0:
                status_label = 'regressed'
            else:
                status_label = 'steady'

        statuses.append(
            {
                'runtime_profile': runtime_profile,
                'status_label': status_label,
                'latest_item': latest,
                'previous_item': previous,
                'delta_from_previous': delta_from_previous,
                'delta_from_best': (
                    None
                    if latest_metric is None or best_metric is None
                    else latest_metric - best_metric
                ),
            }
        )

    return statuses


def build_long_term_tracking_view(records):
    best_item = _best_so_far(records)
    return {
        'total_records': len(records),
        'best_so_far': best_item,
        'recent_regression': _recent_regression(records, best_item),
        'archive_status': _archive_status(records),
        'recent_window': _recent_window(records),
        'workflow_statuses': _workflow_statuses(records),
        'tracking_facets': _tracking_facets(records),
        'profile_statuses': _profile_statuses(records),
    }

