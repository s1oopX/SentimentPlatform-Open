from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


def get_filtered_users(*, search="", role="", status_filter="", excluded_user_id=None):
    users = User.objects.all()
    if excluded_user_id is not None:
        users = users.exclude(pk=excluded_user_id)
    if search:
        users = users.filter(
            Q(email__icontains=search)
            | Q(phone__icontains=search)
            | Q(nickname__icontains=search)
        )
    if role:
        users = users.filter(role=role)
    if status_filter:
        users = users.filter(status=status_filter)
    return users.order_by("-created_at")


def get_user_by_id(pk, *, excluded_user_id=None):
    queryset = User.objects.filter(pk=pk)
    if excluded_user_id is not None:
        queryset = queryset.exclude(pk=excluded_user_id)
    return queryset.first()
