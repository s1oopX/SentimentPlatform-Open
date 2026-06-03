from io import BytesIO
from urllib.parse import quote

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import IsUserOrAdmin

from apps.admin_panel.infra.automation.system_config import get_max_batch_records
from apps.analysis.application.commands.analyze_batch import analyze_batch_comments
from apps.analysis.application.commands.analyze_single import analyze_single_comment
from apps.analysis.application.errors import AnalysisApplicationError
from apps.analysis.api.responses import (
    build_service_error_response,
    model_unavailable_response,
)
from apps.analysis.api.serializers.actions import (
    BatchAnalysisSerializer,
    PublicAnalysisResultSerializer,
    SingleAnalysisSerializer,
)
from apps.analysis.infra.file_parsing import parse_batch_comments
from apps.analysis.infra.model_runtime import ModelUnavailableError, predict_sentiment, predict_sentiment_batch
from core.request_ip import get_request_ip


BATCH_TEMPLATE_EXAMPLES = [
    "这款产品包装完整，物流很快，整体体验不错",
    "客服响应太慢，问题一直没有解决",
    "价格合适，质量中规中矩",
]
BATCH_SCHEMA_COLUMNS = [
    {
        "field": "content",
        "label": "评论内容",
        "required": True,
        "type": "string",
        "max_length": 1000,
        "description": "待分析的评论文本；xlsx 模板读取第一列，txt 模板每行一条评论",
        "examples": BATCH_TEMPLATE_EXAMPLES,
    },
]


def _normalize_template_format(raw_format):
    normalized = str(raw_format or "xlsx").strip().lower().lstrip(".")
    if normalized in {"xlsx", "txt"}:
        return normalized
    raise AnalysisApplicationError("模板格式仅支持 xlsx 或 txt", 400)


def _build_content_disposition(filename, ascii_fallback):
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )


def _build_xlsx_template_response():
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise AnalysisApplicationError("服务端缺少 Excel 模板生成依赖", 500) from exc

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "批量分析模板"
    worksheet.append(["评论内容"])
    for example in BATCH_TEMPLATE_EXAMPLES:
        worksheet.append([example])

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = _build_content_disposition(
        "批量分析模板.xlsx",
        "batch-analysis-template.xlsx",
    )
    return response


def _build_txt_template_response():
    content = "\n".join(BATCH_TEMPLATE_EXAMPLES) + "\n"
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = _build_content_disposition(
        "批量分析模板.txt",
        "batch-analysis-template.txt",
    )
    return response


def build_batch_schema_payload():
    return {
        "max_rows": get_max_batch_records(),
        "supported_formats": [".xlsx", ".txt"],
        "xlsx": {
            "sheet": "首个工作表",
            "header_required": True,
            "header_row": 1,
            "data_start_row": 2,
            "content_column": "A",
            "columns": BATCH_SCHEMA_COLUMNS,
        },
        "txt": {
            "encoding": "UTF-8",
            "line_rule": "每行一条评论，空行会被忽略",
            "columns": BATCH_SCHEMA_COLUMNS,
        },
    }


class SingleAnalyzeView(APIView):
    permission_classes = [IsUserOrAdmin]


    def post(self, request):
        serializer = SingleAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            analysis_result = analyze_single_comment(
                validated_data=serializer.validated_data,
                user=request.user,
                client_ip=get_request_ip(request),
                predict_sentiment=predict_sentiment,
            )
        except AnalysisApplicationError as exc:
            return build_service_error_response(exc)
        except ModelUnavailableError as exc:
            return model_unavailable_response(exc)

        return Response(PublicAnalysisResultSerializer(analysis_result).data)


class BatchAnalyzeView(APIView):
    permission_classes = [IsUserOrAdmin]


    def post(self, request):
        serializer = BatchAnalysisSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            payload = analyze_batch_comments(
                validated_data=serializer.validated_data,
                user=request.user,
                client_ip=get_request_ip(request),
                predict_sentiment=predict_sentiment,
                parse_batch_comments=parse_batch_comments,
                predict_sentiment_batch=predict_sentiment_batch,
            )
        except AnalysisApplicationError as exc:
            return build_service_error_response(exc)
        except ModelUnavailableError as exc:
            return model_unavailable_response(exc)

        return Response(
            {
                "total": payload["total"],
                "results": PublicAnalysisResultSerializer(
                    payload["results"], many=True
                ).data,
                "summary": payload["summary"],
            }
        )


class BatchTemplateView(APIView):
    permission_classes = [IsUserOrAdmin]

    def get(self, request):
        try:
            template_format = _normalize_template_format(
                request.query_params.get("format", "xlsx")
            )
        except AnalysisApplicationError as exc:
            return build_service_error_response(exc)

        if template_format == "txt":
            return _build_txt_template_response()
        try:
            return _build_xlsx_template_response()
        except AnalysisApplicationError as exc:
            return build_service_error_response(exc)


class BatchSchemaView(APIView):
    permission_classes = [IsUserOrAdmin]

    def get(self, _request):
        return Response(build_batch_schema_payload())
