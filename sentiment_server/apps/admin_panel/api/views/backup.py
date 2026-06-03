import subprocess
import logging
import shutil
from pathlib import Path

from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

from apps.admin_panel.api.views.base import AdminOnlyAPIView

logger = logging.getLogger(__name__)


class DatabaseBackupView(AdminOnlyAPIView):
    """触发数据库备份（调用 backup_database.ps1 脚本）"""

    def post(self, request):
        script_path = Path(settings.BASE_DIR) / "scripts" / "ops" / "backup_database.ps1"
        if not script_path.exists():
            return Response(
                {"error": "备份脚本不存在", "path": str(script_path)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        pwsh_path = shutil.which("pwsh") or shutil.which("powershell")
        if not pwsh_path:
            return Response(
                {"error": "PowerShell 未安装，无法执行备份脚本"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            result = subprocess.run(  # noqa: S603 - command and script path are server-controlled.
                [pwsh_path, "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                cwd=str(settings.BASE_DIR),
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if result.returncode == 0:
                logger.info("数据库备份成功: %s", stdout.strip())
                return Response({
                    "message": "数据库备份成功",
                    "output": stdout.strip(),
                })
            else:
                detail = (stderr or stdout).strip()
                logger.error("数据库备份失败: %s", detail)
                return Response(
                    {"error": "备份执行失败", "detail": detail},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except subprocess.TimeoutExpired:
            return Response(
                {"error": "备份超时（120秒）"},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except FileNotFoundError:
            return Response(
                {"error": "pwsh 未安装，无法执行备份脚本"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
