"""分析服务相关测试。"""
import threading

import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.analysis.infra.file_parsing import (
    AnalysisValidationError,
    parse_batch_comments,
)
from apps.analysis.application.commands.analyze_batch import analyze_batch_comments
from apps.analysis.domain.category_rules import infer_comment_category
from apps.analysis.infra.selectors.analysis_results import build_category_distribution
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
