from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.application.queries.analyst import (
    build_analyst_comment_list_context,
    build_analyst_overview_context,
    build_analyst_report_context,
)
from apps.analysis.api.responses import StandardResultsSetPagination
from apps.analysis.api.serializers.actions import (
    PublicAnalysisResultSerializer,
)
from apps.analysis.api.serializers.analyst import (
    AnalystCommentFilterSerializer,
    AnalystCommentNoteSerializer,
    AnalystOverviewSerializer,
    AnalystReportSerializer,
)
from apps.analysis.application.commands.analyst_comments import (
    delete_analyst_comment,
    update_analyst_comment,
)
from apps.analysis.infra.selectors.analyst import get_visible_analyst_queryset
from apps.users.permissions import IsAnalystOrAdmin
from core.request_ip import get_request_ip


def _serialize_overview_payload(payload):
    return {
        **payload,
        "recent_results": PublicAnalysisResultSerializer(
            payload["recent_results"], many=True
        ).data,
    }


def _serialize_report_payload(payload):
    return payload


class AnalystOverviewView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        serializer = AnalystOverviewSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        context = build_analyst_overview_context(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        return Response(_serialize_overview_payload(context))


class AnalystCommentListView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        serializer = AnalystCommentFilterSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        context = build_analyst_comment_list_context(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        paginator = StandardResultsSetPagination()
        paginator.page_size = serializer.validated_data["page_size"]
        page = paginator.paginate_queryset(context["queryset"], request, view=self)
        response = paginator.get_paginated_response(
            PublicAnalysisResultSerializer(page, many=True).data
        )
        response.data["category_options"] = context["category_options"]
        return Response(response.data)


class AnalystCommentDetailView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get_object(self, pk):
        return get_visible_analyst_queryset(self.request.user).filter(pk=pk).first()

    def patch(self, request, pk):
        result = self.get_object(pk)
        if not result:
            return Response(
                {"error": "分析结果不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = AnalystCommentNoteSerializer(
            result, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = update_analyst_comment(
            result=result,
            validated_data=serializer.validated_data,
            user=request.user,
            client_ip=get_request_ip(request),
        )
        return Response(PublicAnalysisResultSerializer(result).data)

    def delete(self, request, pk):
        result = self.get_object(pk)
        if not result:
            return Response(
                {"error": "分析结果不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        delete_analyst_comment(
            result=result,
            user=request.user,
            client_ip=get_request_ip(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnalystReportView(APIView):
    permission_classes = [IsAnalystOrAdmin]

    def get(self, request):
        serializer = AnalystReportSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        context = build_analyst_report_context(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        return Response(_serialize_report_payload(context))
