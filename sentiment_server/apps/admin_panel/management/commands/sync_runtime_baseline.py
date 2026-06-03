from django.core.management.base import BaseCommand, CommandError

from apps.admin_panel.application.runtime_registry.commands import (
    register_runtime_baseline_model,
)
from apps.admin_panel.infra.runtime_registry.registry import (
    cleanup_stale_training_run_model_rows,
)
from apps.users.models import User


class Command(BaseCommand):
    help = "Register current runtime baseline and optionally prune stale registry rows."

    def add_arguments(self, parser):
        parser.add_argument("--operator-email", required=True)
        parser.add_argument("--prune-stale", action="store_true")

    def _resolve_operator(self, email):
        operator = User.objects.filter(email=email, role="admin", status=1).first()
        if operator:
            return operator

        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            raise CommandError("operator-email 必须对应启用中的管理员账号")
        raise CommandError("operator-email 对应的管理员用户不存在")

    def handle(self, *_args, **options):
        operator = self._resolve_operator(options["operator_email"])
        try:
            model = register_runtime_baseline_model(operator=operator)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        removed = (
            cleanup_stale_training_run_model_rows() if options["prune_stale"] else 0
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"baseline_model={model.path} removed_stale_rows={removed}"
            )
        )
