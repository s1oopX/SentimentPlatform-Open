import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.reports.api.views.download import ReportDownloadView
from apps.reports.application.user_messages import REPORT_ENQUEUE_FAILURE_MESSAGE
from apps.reports.infra.report_updates import mark_report_enqueue_attempt
from apps.reports.models import Report, ReportStatus
from apps.users.models import User


def _make_user(email="report-owner@example.com", role="user"):
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        role=role,
    )


def _make_completed_report(*, user, file_path):
    return Report.objects.create(
        user=user,
        report_type="single",
        report_format="pdf",
        status=ReportStatus.COMPLETED,
        file_path=str(file_path),
        file_size=file_path.stat().st_size if file_path.exists() else 0,
    )


def _request_download(*, user, pk):
    request = APIRequestFactory().get(f"/api/report/download/{pk}/")
    force_authenticate(request, user=user)
    return ReportDownloadView.as_view()(request, pk=pk)


@pytest.fixture
def report_root(tmp_path, settings):
    """Isolate REPORT_ROOT to a per-test tmp directory."""
    settings.REPORT_ROOT = str(tmp_path)
    return tmp_path


@pytest.mark.django_db
def test_download_completed_report_streams_file_with_disposition(report_root):
    owner = _make_user()
    artifact = report_root / "report-1.pdf"
    artifact.write_bytes(b"%PDF-1.4 dummy report payload")
    report = _make_completed_report(user=owner, file_path=artifact)

    response = _request_download(user=owner, pk=report.pk)

    assert response.status_code == 200
    disposition = response["Content-Disposition"]
    assert "attachment" in disposition
    # Sanitized filename is whitelisted to alnum/dot/dash/underscore.
    assert 'filename="report-1.pdf"' in disposition
    streamed = b"".join(response.streaming_content)
    assert streamed == b"%PDF-1.4 dummy report payload"


@pytest.mark.django_db
def test_download_unknown_report_returns_404_without_disclosing_other_users_files(
    report_root,
):
    owner = _make_user()
    intruder = _make_user(email="intruder@example.com")
    artifact = report_root / "owner-only.pdf"
    artifact.write_bytes(b"secret")
    owner_report = _make_completed_report(user=owner, file_path=artifact)

    # Intruder asks for a report that exists but belongs to another user.
    response = _request_download(user=intruder, pk=owner_report.pk)

    assert response.status_code == 404
    assert response.data == {"error": "报告不存在"}


@pytest.mark.django_db
def test_download_pending_report_rejects_with_400(report_root):  # noqa: ARG001
    owner = _make_user()
    pending = Report.objects.create(
        user=owner,
        report_type="single",
        report_format="pdf",
        status=ReportStatus.PROCESSING,
        file_path="",
    )

    response = _request_download(user=owner, pk=pending.pk)

    assert response.status_code == 400
    assert response.data == {"error": "报告尚未生成"}


@pytest.mark.django_db
def test_download_completed_report_with_missing_file_returns_404(report_root):
    owner = _make_user()
    # Reference a file that was never written to disk.
    report = _make_completed_report(user=owner, file_path=report_root / "ghost.pdf")

    response = _request_download(user=owner, pk=report.pk)

    assert response.status_code == 404
    assert response.data == {"error": "报告文件不存在"}


@pytest.mark.django_db
def test_enqueue_failure_marks_report_failed():
    owner = _make_user()
    report = Report.objects.create(
        user=owner,
        report_type="daily",
        report_format="csv",
        status=ReportStatus.PENDING_ENQUEUE,
    )

    updated = mark_report_enqueue_attempt(
        report.pk,
        succeeded=False,
        error_message=REPORT_ENQUEUE_FAILURE_MESSAGE,
    )

    assert updated == 1
    report.refresh_from_db()
    assert report.status == ReportStatus.FAILED
    assert report.enqueue_attempts == 1
    assert report.last_enqueue_error == REPORT_ENQUEUE_FAILURE_MESSAGE
