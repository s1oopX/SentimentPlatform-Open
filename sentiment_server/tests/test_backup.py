from types import SimpleNamespace

from rest_framework import status

from apps.admin_panel.api.views.backup import DatabaseBackupView


def test_backup_view_handles_empty_process_output(settings, tmp_path, monkeypatch):
    script_dir = tmp_path / "scripts" / "ops"
    script_dir.mkdir(parents=True)
    (script_dir / "backup_database.ps1").write_text("Write-Output ok", encoding="utf-8")
    settings.BASE_DIR = tmp_path
    monkeypatch.setattr("apps.admin_panel.api.views.backup.shutil.which", lambda _name: "pwsh")
    monkeypatch.setattr(
        "apps.admin_panel.api.views.backup.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=None, stderr=None),
    )

    response = DatabaseBackupView().post(SimpleNamespace())

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"message": "数据库备份成功", "output": ""}


def test_backup_view_uses_stdout_when_failure_stderr_is_empty(settings, tmp_path, monkeypatch):
    script_dir = tmp_path / "scripts" / "ops"
    script_dir.mkdir(parents=True)
    (script_dir / "backup_database.ps1").write_text("Write-Output failed", encoding="utf-8")
    settings.BASE_DIR = tmp_path
    monkeypatch.setattr("apps.admin_panel.api.views.backup.shutil.which", lambda _name: "pwsh")
    monkeypatch.setattr(
        "apps.admin_panel.api.views.backup.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="失败原因", stderr=None),
    )

    response = DatabaseBackupView().post(SimpleNamespace())

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data == {"error": "备份执行失败", "detail": "失败原因"}
