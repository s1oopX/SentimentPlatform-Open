from pathlib import Path


def ensure_report_artifact_path_is_safe(*, report_root, file_path):
    if not file_path:
        return None

    report_root = Path(report_root).resolve()
    candidate = Path(file_path).resolve()
    try:
        candidate.relative_to(report_root)
    except ValueError:
        return None
    return candidate
