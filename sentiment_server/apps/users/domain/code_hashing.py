import hashlib
import hmac

from django.conf import settings
from django.core.cache import cache

_CACHE_KEY_PREFIX = "vc_plain:"
_CACHE_TTL = 300  # 5 minutes — matches verification code validity

_DOMAIN_SEPARATION_PREFIX = b"verification-code-hmac:"


def _resolve_hmac_key() -> bytes:
    """Return the HMAC key for verification code hashing.

    Prefers the dedicated ``VERIFICATION_CODE_HMAC_KEY`` setting.  When that
    is not configured, derives a domain-separated key from ``SECRET_KEY``
    so that a raw SECRET_KEY leak does not directly compromise code hashes.
    """
    dedicated = getattr(settings, "VERIFICATION_CODE_HMAC_KEY", "")
    if dedicated:
        return dedicated.encode()
    return hashlib.sha256(
        _DOMAIN_SEPARATION_PREFIX + settings.SECRET_KEY.encode()
    ).digest()


def hash_verification_code(code: str) -> str:
    """Hash a verification code using HMAC-SHA256.

    The hash is what gets stored in the database instead of the plaintext
    code, so that a database compromise does not reveal usable codes.
    """
    return hmac.new(
        _resolve_hmac_key(),
        code.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_code_hash(code: str, stored_hash: str) -> bool:
    """Constant-time comparison of a code against its stored hash."""
    return hmac.compare_digest(
        hash_verification_code(code),
        stored_hash,
    )


def cache_verification_code_plaintext(verification_code_id: int, code: str) -> None:
    """Temporarily cache the plaintext code so that email delivery retries
    can access it without persisting it to the database.

    TTL matches the 5-minute verification code validity window.
    """
    cache.set(f"{_CACHE_KEY_PREFIX}{verification_code_id}", code, _CACHE_TTL)


def get_cached_verification_code_plaintext(verification_code_id: int) -> str:
    """Retrieve the cached plaintext code for delivery purposes.

    Returns an empty string if the key has expired (code is stale).
    """
    return cache.get(f"{_CACHE_KEY_PREFIX}{verification_code_id}", "")


def delete_cached_verification_code_plaintext(verification_code_id: int) -> None:
    """Remove the cached plaintext when the code is consumed or invalidated."""
    cache.delete(f"{_CACHE_KEY_PREFIX}{verification_code_id}")


__all__ = [
    "hash_verification_code",
    "verify_code_hash",
    "cache_verification_code_plaintext",
    "get_cached_verification_code_plaintext",
    "delete_cached_verification_code_plaintext",
]
