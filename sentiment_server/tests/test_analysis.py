"""分析服务相关测试。"""
from datetime import timedelta
import threading

import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.admin_panel.api.serializers.datasets import DatasetAnalysisResultSerializer
from apps.admin_panel.infra.selectors.datasets import get_filtered_dataset_results
from apps.analysis.infra.file_parsing import (
    AnalysisValidationError,
    parse_batch_comments,
)
from apps.analysis.application.commands.analyze_batch import analyze_batch_comments
from apps.analysis.application.commands.analyst_comments import update_analyst_comment
from apps.analysis.application.commands.analyze_single import analyze_single_comment
from apps.analysis.application.queries.history import (
    build_history_list_payload,
    build_history_session_detail_payload,
)
from apps.analysis.application.queries.analyst import build_analyst_report_context
from apps.analysis.domain.category_rules import infer_comment_category
from apps.analysis.infra.selectors.analysis_results import build_category_distribution
from apps.analysis.infra.selectors.analyst import (
    get_visible_analyst_queryset,
    get_visible_analyst_review_queryset,
)
from apps.analysis.models import AnalysisResult, Comment
from apps.users.models import User


def _make_txt_file(content, name='test.txt'):
    return SimpleUploadedFile(name, content.encode('utf-8'), content_type='text/plain')


def _make_xlsx_file(name='test.xlsx'):
    """Create a minimal valid xlsx file with one data row."""
    import openpyxl
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['评论内容'])
    ws.append(['这是一条测试评论'])
    ws.append(['这是另一条评论'])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class TestBatchFileParsing(TestCase):
    """批量文件解析测试。"""

    def test_parse_txt_file(self):
        f = _make_txt_file('评论一\n评论二\n评论三')
        result = parse_batch_comments(f)
        assert result == ['评论一', '评论二', '评论三']

    def test_parse_txt_skips_empty_lines(self):
        f = _make_txt_file('评论一\n\n\n评论二')
        result = parse_batch_comments(f)
        assert result == ['评论一', '评论二']

    def test_parse_txt_must_be_utf8(self):
        f = SimpleUploadedFile('test.txt', '非UTF8内容'.encode('gbk'), content_type='text/plain')
        with pytest.raises(AnalysisValidationError, match='UTF-8'):
            parse_batch_comments(f)

    def test_parse_xlsx_file(self):
        f = _make_xlsx_file()
        result = parse_batch_comments(f)
        assert len(result) == 2
        assert '测试评论' in result[0]

    def test_parse_unsupported_format(self):
        f = SimpleUploadedFile('test.csv', b'a,b,c', content_type='text/csv')
        with pytest.raises(AnalysisValidationError, match='格式'):
            parse_batch_comments(f)

    def test_parse_oversized_file(self):
        """文件大小超过限制时应拒绝。"""
        large_content = 'x' * (11 * 1024 * 1024)  # 11 MB
        f = SimpleUploadedFile('big.txt', large_content.encode('utf-8'), content_type='text/plain')
        with pytest.raises(AnalysisValidationError, match='大小'):
            parse_batch_comments(f)

    def test_parse_xlsx_skips_empty_rows(self):
        import openpyxl
        from io import BytesIO

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['评论内容'])
        ws.append(['有效评论'])
        ws.append([None])
        ws.append([' '])
        ws.append(['另一条有效评论'])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        f = SimpleUploadedFile('test.xlsx', buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        result = parse_batch_comments(f)
        assert len(result) == 2


def test_model_loader_singleton_initializes_without_self_deadlock(monkeypatch):
    from apps.analysis.infra import model_runtime

    monkeypatch.setattr(model_runtime, '_model_loader', None)
    monkeypatch.setattr(model_runtime.SentimentModelLoader, '_instance', None)
    monkeypatch.setattr(
        model_runtime.SentimentModelLoader,
        'load_model',
        lambda self: True,
    )

    result = []
    errors = []

    def initialize_loader():
        try:
            result.append(model_runtime.get_model_loader())
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    thread = threading.Thread(target=initialize_loader, daemon=True)
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert not errors
    assert result


@pytest.mark.django_db
def test_analyze_batch_comments_persists_comments_and_results():
    user = User.objects.create_user(
        email='batch-user@example.com',
        password='TestPass123!',
    )
    upload = _make_txt_file('体验很好\n服务太慢')

    def fake_predict_batch(contents):
        assert contents == ['体验很好', '服务太慢']
        return [
            (1, 0.91, ['体验', '很好']),
            (-1, 0.88, ['服务', '太慢']),
        ]

    payload = analyze_batch_comments(
        validated_data={'file': upload},
        user=user,
        parse_batch_comments=parse_batch_comments,
        predict_sentiment=lambda _content: (0, 0.5, []),
        predict_sentiment_batch=fake_predict_batch,
    )

    assert payload['total'] == 2
    assert Comment.objects.count() == 2
    assert AnalysisResult.objects.filter(user=user).count() == 2
    assert [result.comment.content for result in payload['results']] == [
        '体验很好',
        '服务太慢',
    ]
    assert [result.comment.category for result in payload['results']] == [
        '综合体验',
        '售后服务',
    ]
    assert {result.analysis_channel for result in payload['results']} == {'batch'}
    assert len({result.analysis_session_id for result in payload['results']}) == 1
    assert {result.analysis_source_name for result in payload['results']} == {'test.txt'}


@pytest.mark.django_db
def test_analyze_single_comment_marks_single_session():
    user = User.objects.create_user(
        email='single-user@example.com',
        password='TestPass123!',
    )

    result = analyze_single_comment(
        validated_data={'content': '这次体验很好，页面反馈很清楚'},
        user=user,
        predict_sentiment=lambda _content: (1, 0.92, ['体验', '清楚']),
    )

    assert result.analysis_channel == 'single'
    assert result.analysis_session_id
    assert result.analysis_source_name == ''


@pytest.mark.django_db
def test_analyst_update_records_corrected_sentiment_metadata():
    user = User.objects.create_user(
        email='review-target@example.com',
        password='TestPass123!',
    )
    analyst = User.objects.create_user(
        email='reviewer@example.com',
        password='TestPass123!',
        role='analyst',
    )
    comment = Comment.objects.create(content='客服回复很慢')
    result = AnalysisResult.objects.create(
        user=user,
        comment=comment,
        sentiment=1,
        confidence=0.82,
        keywords=['客服'],
    )

    updated = update_analyst_comment(
        result=result,
        validated_data={
            'corrected_sentiment': -1,
            'analyst_note': '人工复核后应为消极',
            'is_priority': True,
        },
        user=analyst,
    )

    assert updated.final_sentiment == -1
    assert updated.corrected_sentiment == -1
    assert updated.reviewed_by == analyst
    assert updated.reviewed_at is not None


@pytest.mark.django_db
def test_analyst_review_queryset_only_includes_low_confidence_results():
    analyst = User.objects.create_user(
        email='low-confidence-reviewer@example.com',
        password='TestPass123!',
        role='analyst',
    )
    user = User.objects.create_user(
        email='low-confidence-user@example.com',
        password='TestPass123!',
    )
    low_comment = Comment.objects.create(content='物流太慢了')
    boundary_comment = Comment.objects.create(content='包装还可以')
    high_comment = Comment.objects.create(content='体验非常好')
    low_result = AnalysisResult.objects.create(
        user=user,
        comment=low_comment,
        sentiment=-1,
        confidence=0.69,
        keywords=[],
    )
    AnalysisResult.objects.create(
        user=user,
        comment=boundary_comment,
        sentiment=0,
        confidence=0.70,
        keywords=[],
    )
    AnalysisResult.objects.create(
        user=user,
        comment=high_comment,
        sentiment=1,
        confidence=0.91,
        keywords=[],
    )

    all_visible_ids = set(get_visible_analyst_queryset(analyst).values_list('id', flat=True))
    review_visible_ids = set(
        get_visible_analyst_review_queryset(analyst).values_list('id', flat=True)
    )

    assert len(all_visible_ids) == 3
    assert review_visible_ids == {low_result.id}


@pytest.mark.django_db
def test_analyst_report_context_includes_quality_and_final_label_metrics():
    analyst = User.objects.create_user(
        email='analyst-report@example.com',
        password='TestPass123!',
        role='analyst',
    )
    low_comment = Comment.objects.create(content='售后一直没有回复')
    high_comment = Comment.objects.create(content='物流很快体验很好')
    AnalysisResult.objects.create(
        user=analyst,
        comment=low_comment,
        sentiment=1,
        corrected_sentiment=-1,
        confidence=0.61,
        keywords=['售后'],
        reviewed_by=analyst,
    )
    AnalysisResult.objects.create(
        user=analyst,
        comment=high_comment,
        sentiment=1,
        confidence=0.93,
        keywords=['物流'],
    )

    context = build_analyst_report_context(
        user=analyst,
        validated_data={'keyword_limit': 20},
    )

    assert context['summary']['total'] == 2
    assert context['summary']['positive'] == 1
    assert context['summary']['negative'] == 1
    assert context['quality_summary']['low_confidence_count'] == 1
    assert context['quality_summary']['corrected_count'] == 1
    assert context['correction_matrix'] == [
        {
            'model_sentiment': 1,
            'model_sentiment_display': '积极',
            'final_sentiment': -1,
            'final_sentiment_display': '消极',
            'count': 1,
        },
        {
            'model_sentiment': 1,
            'model_sentiment_display': '积极',
            'final_sentiment': 1,
            'final_sentiment_display': '积极',
            'count': 1,
        },
    ]


@pytest.mark.django_db
def test_analyst_report_total_uses_full_result_count_across_trend_days():
    analyst = User.objects.create_user(
        email='analyst-report-total@example.com',
        password='TestPass123!',
        role='analyst',
    )
    yesterday = timezone.now() - timedelta(days=1)
    comments = [
        Comment.objects.create(content='昨天体验不错', comment_time=yesterday),
        Comment.objects.create(content='今天体验很好'),
        Comment.objects.create(content='今天服务一般'),
    ]
    for comment in comments:
        AnalysisResult.objects.create(
            user=analyst,
            comment=comment,
            sentiment=1,
            confidence=0.9,
            keywords=[],
        )

    context = build_analyst_report_context(
        user=analyst,
        validated_data={'keyword_limit': 20},
    )

    assert context['summary']['total'] == 3
    assert context['quality_summary']['low_confidence_rate'] == 0.0


@pytest.mark.django_db
def test_dataset_review_status_treats_high_confidence_as_reviewed():
    user = User.objects.create_user(
        email='dataset-status-user@example.com',
        password='TestPass123!',
    )
    analyst = User.objects.create_user(
        email='dataset-status-analyst@example.com',
        password='TestPass123!',
        role='analyst',
    )
    high_comment = Comment.objects.create(content='高置信记录')
    low_comment = Comment.objects.create(content='低置信未审核记录')
    reviewed_low_comment = Comment.objects.create(content='低置信已审核记录')
    high_result = AnalysisResult.objects.create(
        user=user,
        comment=high_comment,
        sentiment=1,
        confidence=0.70,
        keywords=[],
    )
    low_result = AnalysisResult.objects.create(
        user=user,
        comment=low_comment,
        sentiment=-1,
        confidence=0.69,
        keywords=[],
    )
    reviewed_low_result = AnalysisResult.objects.create(
        user=user,
        comment=reviewed_low_comment,
        sentiment=1,
        corrected_sentiment=0,
        confidence=0.61,
        keywords=[],
        reviewed_by=analyst,
        reviewed_at=timezone.now(),
    )

    reviewed_ids = set(
        get_filtered_dataset_results(review_status='reviewed').values_list('id', flat=True)
    )
    unreviewed_ids = set(
        get_filtered_dataset_results(review_status='unreviewed').values_list('id', flat=True)
    )
    serialized = DatasetAnalysisResultSerializer(
        [high_result, low_result, reviewed_low_result],
        many=True,
    ).data

    assert high_result.id in reviewed_ids
    assert reviewed_low_result.id in reviewed_ids
    assert low_result.id not in reviewed_ids
    assert unreviewed_ids == {low_result.id}
    assert serialized[0]['review_status_display'] == '已审核'
    assert serialized[1]['review_status_display'] == '未审核'
    assert serialized[2]['review_status_display'] == '已审核'
    assert serialized[2]['has_manual_correction'] is True


@pytest.mark.django_db
def test_history_list_groups_batch_results_by_analysis_session():
    user = User.objects.create_user(
        email='history-session@example.com',
        password='TestPass123!',
    )
    upload = _make_txt_file('体验很好\n服务太慢\n价格一般')

    batch_payload = analyze_batch_comments(
        validated_data={'file': upload},
        user=user,
        parse_batch_comments=parse_batch_comments,
        predict_sentiment=lambda _content: (0, 0.5, []),
        predict_sentiment_batch=lambda _contents: [
            (1, 0.91, ['体验']),
            (-1, 0.88, ['服务']),
            (0, 0.77, ['价格']),
        ],
    )
    single_result = analyze_single_comment(
        validated_data={'content': '单独分析体验不错'},
        user=user,
        predict_sentiment=lambda _content: (1, 0.93, ['体验']),
    )

    request = Request(APIRequestFactory().get('/api/analyze/history/?page=1&page_size=10'))
    response_payload = build_history_list_payload(
        user=user,
        validated_data={'page': 1, 'page_size': 10},
        request=request,
    )

    rows = response_payload['results']
    batch_rows = [row for row in rows if row['analysis_channel'] == 'batch']
    single_rows = [row for row in rows if row['analysis_channel'] == 'single']

    assert response_payload['count'] == 2
    assert len(batch_rows) == 1
    assert batch_rows[0]['result_count'] == 3
    assert batch_rows[0]['analysis_source_name'] == 'test.txt'
    assert batch_rows[0]['analysis_session_id'] == str(
        batch_payload['results'][0].analysis_session_id
    )
    assert len(batch_rows[0]['sample_results']) == 3
    assert any(row['id'] == single_result.pk for row in single_rows)


@pytest.mark.django_db
def test_history_session_detail_returns_all_batch_results():
    user = User.objects.create_user(
        email='history-session-detail@example.com',
        password='TestPass123!',
    )
    upload = _make_txt_file('体验很好\n服务太慢\n价格一般')
    batch_payload = analyze_batch_comments(
        validated_data={'file': upload},
        user=user,
        parse_batch_comments=parse_batch_comments,
        predict_sentiment=lambda _content: (0, 0.5, []),
        predict_sentiment_batch=lambda _contents: [
            (1, 0.91, ['体验']),
            (-1, 0.88, ['服务']),
            (0, 0.77, ['价格']),
        ],
    )

    payload = build_history_session_detail_payload(
        pk=batch_payload['results'][0].pk,
        user=user,
    )

    assert payload['analysis_channel'] == 'batch'
    assert payload['result_count'] == 3
    assert [row['comment_content'] for row in payload['results']] == [
        '体验很好',
        '服务太慢',
        '价格一般',
    ]


def test_infer_comment_category_uses_local_business_rules():
    assert infer_comment_category('上传 Excel 后等待时间有点长') == '批量上传'
    assert infer_comment_category('报告中心的 PDF 下载很方便') == '报告导出'
    assert infer_comment_category('客服回复很及时') == '售后服务'


@pytest.mark.django_db
def test_category_distribution_infers_existing_uncategorized_comments():
    user = User.objects.create_user(
        email='category-user@example.com',
        password='TestPass123!',
    )
    comments = [
        Comment.objects.create(content='物流很快，包装完整'),
        Comment.objects.create(content='验证码有时候看不清楚'),
        Comment.objects.create(content='客服回复很及时'),
    ]
    for comment in comments:
        AnalysisResult.objects.create(
            user=user,
            comment=comment,
            sentiment=1,
            confidence=0.9,
            keywords=[],
        )

    distribution = build_category_distribution(AnalysisResult.objects.filter(user=user))

    assert {item['category'] for item in distribution} >= {
        '物流包装',
        '账户安全',
        '售后服务',
    }
