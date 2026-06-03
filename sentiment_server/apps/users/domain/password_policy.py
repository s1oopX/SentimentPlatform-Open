from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


def build_password_validation_user(*, email="", nickname="", role="user", user=None):
    if user is not None:
        return user
    return User(
        email=email or "",
        nickname=nickname or "",
        role=role or "user",
    )


def validate_user_password(*, password, email="", nickname="", role="user", user=None):
    candidate_user = build_password_validation_user(
        email=email,
        nickname=nickname,
        role=role,
        user=user,
    )
    validate_password(password, user=candidate_user)
