from django.contrib.auth import get_user_model

User = get_user_model()


def get_user_by_email(email):
    return User.objects.filter(email=email).first()


def get_users_by_phone(phone, *, limit=2):
    if not phone:
        return []
    return list(User.objects.filter(phone=phone)[:limit])


def get_user_by_email_for_update(email):
    return User.objects.select_for_update().filter(email=email).first()


def user_exists_with_email(email):
    return User.objects.filter(email=email).exists()


__all__ = [
    "get_user_by_email",
    "get_user_by_email_for_update",
    "get_users_by_phone",
    "user_exists_with_email",
]
