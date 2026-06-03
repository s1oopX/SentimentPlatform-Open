from django.conf import settings

from apps.admin_panel.domain.rules.dataset_import import (
    DATASET_IMPORT_SUPPORTED_FORMATS,
)
from apps.admin_panel.infra.automation.system_config import load_system_config
from apps.analysis.infra.file_parsing import BATCH_ANALYSIS_SUPPORTED_FORMATS


def build_runtime_capabilities_payload():
    config = load_system_config()
    return {
        "max_upload_size_mb": round(
            int(getattr(settings, "MAX_UPLOAD_SIZE", 0)) / (1024 * 1024), 2
        ),
        "batch_analysis_supported_formats": list(BATCH_ANALYSIS_SUPPORTED_FORMATS),
        "dataset_import_supported_formats": list(DATASET_IMPORT_SUPPORTED_FORMATS),
        "report_defaults": {
            "report_type": config.get("default_report_type", "weekly"),
            "report_format": config.get("default_report_format", "pdf"),
        },
    }
