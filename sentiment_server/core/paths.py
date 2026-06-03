from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BLOCKED_LEGACY_PROJECT_PATHS = {
    "backend/model",
    "backend/model/models/bert",
    "sentiment_server/model/models/bert",
    "model",
    "model/models/bert",
    "reports",
}


def find_workspace_root(
    start_path: str | Path, *, marker_dirs: tuple[str, ...]
) -> Path:
    candidate = Path(start_path).resolve()
    search_roots = (candidate, *candidate.parents)

    for root in search_roots:
        if all((root / marker).exists() for marker in marker_dirs):
            return root

    markers = ", ".join(marker_dirs)
    raise ImproperlyConfigured(
        f"could not locate workspace root from {start_path}; missing marker dirs: {markers}"
    )


def resolve_project_path(raw_value: str | Path, *, base_dir: Path) -> Path:
    value = str(raw_value).replace("\\", "/").strip()
    if value == "":
        raise ImproperlyConfigured("runtime path values must not be blank")

    candidate = Path(value)
    if candidate.name:
        value = value.rstrip("/")

    # Keep old runtime paths blocked so stale deployments fail loudly instead
    # of writing models or reports into historical locations.
    if value in BLOCKED_LEGACY_PROJECT_PATHS:
        raise ImproperlyConfigured(
            f"{raw_value} is a deprecated runtime path. Use ml_assets and generated_reports paths instead."
        )

    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
