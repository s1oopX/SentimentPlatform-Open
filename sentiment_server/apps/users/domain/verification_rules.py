from django.conf import settings


def get_max_verification_attempts():
    return int(getattr(settings, "MAX_VERIFICATION_ATTEMPTS", 3))


def is_verification_code_exhausted(verification_code):
    return verification_code.failed_attempts >= get_max_verification_attempts()


__all__ = ["get_max_verification_attempts", "is_verification_code_exhausted"]
