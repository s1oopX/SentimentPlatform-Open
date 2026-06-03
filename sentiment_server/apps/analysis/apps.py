import logging
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AnalysisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analysis"
    verbose_name = "Sentiment Analysis"

    def ready(self):
        self._preload_model_async()

    @staticmethod
    def _preload_model_async():
        """Pre-load the sentiment model in a background thread so the first
        request is not blocked by model loading (which can take seconds)."""
        import os

        if os.environ.get("RUN_MAIN") != "true" and not os.environ.get("CELERY_WORKER"):
            return

        def _load():
            try:
                from apps.analysis.infra.model_runtime import get_model_loader

                get_model_loader()
                logger.info("Sentiment model pre-loaded successfully")
            except Exception:
                logger.warning("Sentiment model pre-load failed", exc_info=True)

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()
