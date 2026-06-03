from django.core.management.base import BaseCommand

from apps.analysis.domain.keyword_rules import normalize_keywords
from apps.analysis.models import AnalysisResult


class Command(BaseCommand):
    help = "Normalize analysis_result.keywords to list[str]. Defaults to dry-run."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true", help="Persist normalized keywords."
        )
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *_args, **options):
        batch_size = max(int(options["batch_size"] or 0), 1)
        should_apply = bool(options["apply"])
        scanned = 0
        pending = 0
        repaired = 0
        dirty_results = []

        queryset = AnalysisResult.objects.only("pk", "keywords").order_by("pk")

        for result in queryset.iterator(chunk_size=batch_size):
            scanned += 1
            normalized_keywords = normalize_keywords(result.keywords)
            if normalized_keywords == result.keywords:
                continue

            pending += 1
            if not should_apply:
                continue

            result.keywords = normalized_keywords
            dirty_results.append(result)
            if len(dirty_results) >= batch_size:
                repaired += self._flush_updates(dirty_results, batch_size=batch_size)
                dirty_results.clear()

        if should_apply and dirty_results:
            repaired += self._flush_updates(dirty_results, batch_size=batch_size)

        self.stdout.write(
            self.style.SUCCESS(
                f"scanned={scanned} pending={pending} repaired={repaired}"
            )
        )

    @staticmethod
    def _flush_updates(results, *, batch_size):
        AnalysisResult.objects.bulk_update(results, ["keywords"], batch_size=batch_size)
        return len(results)
