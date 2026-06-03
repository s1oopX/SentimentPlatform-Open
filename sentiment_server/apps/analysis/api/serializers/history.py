from rest_framework import serializers


class DateRangeValidationMixin:
    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("开始日期不能晚于结束日期")
        return attrs


class AnalysisHistoryFilterSerializer(DateRangeValidationMixin, serializers.Serializer):
    sentiment = serializers.ChoiceField(
        label="情感类别",
        choices=[(1, "积极"), (0, "中性"), (-1, "消极")],
        required=False,
    )
    start_date = serializers.DateField(label="开始日期", required=False)
    end_date = serializers.DateField(label="结束日期", required=False)


class AnalysisHistorySerializer(AnalysisHistoryFilterSerializer):
    page = serializers.IntegerField(label="页码", default=1, min_value=1)
    page_size = serializers.IntegerField(
        label="每页数量", default=10, min_value=1, max_value=100
    )


class AnalysisHistorySummarySerializer(AnalysisHistoryFilterSerializer):
    keyword_limit = serializers.IntegerField(
        label="关键词数量", default=50, min_value=1, max_value=100
    )
    include_visuals = serializers.BooleanField(default=True, required=False)
