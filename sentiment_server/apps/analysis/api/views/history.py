from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.application.queries.history import (
    build_history_detail_payload,
    build_history_list_payload,
    build_history_session_detail_payload,
    build_history_summary_payload,
)
from apps.analysis.api.serializers.history import (
    AnalysisHistorySerializer,
    AnalysisHistorySummarySerializer,
)
from apps.analysis.infra.selectors import get_analysis_result_detail_for_user


class AnalysisHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = AnalysisHistorySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            build_history_list_payload(
                user=request.user,
                validated_data=serializer.validated_data,
                request=request,
                view=self,
            )
        )


class AnalysisHistorySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = AnalysisHistorySummarySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            build_history_summary_payload(
                user=request.user,
                validated_data=serializer.validated_data,
            )
        )


class AnalysisHistorySessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payload = build_history_session_detail_payload(pk=pk, user=request.user)
        if not payload:
            return Response(
                {"error": "分析记录不存在"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(payload)


class AnalysisResultDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        # Defense-in-depth: verify ownership at the view layer in addition
        # to the query layer, so a future refactor cannot silently drop
        # the user filter and introduce IDOR.
        result = get_analysis_result_detail_for_user(pk=pk, user=request.user)
        if not result:
            return Response(
                {"error": "分析结果不存在"}, status=status.HTTP_404_NOT_FOUND
            )

        payload = build_history_detail_payload(result=result)
        return Response(payload)
