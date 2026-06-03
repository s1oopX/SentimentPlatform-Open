from rest_framework import serializers


class DashboardStatsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_analyses = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    today_analyses = serializers.IntegerField()
    sentiment_distribution = serializers.DictField()
