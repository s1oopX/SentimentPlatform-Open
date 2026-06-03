import hashlib
import threading
import weakref
from contextlib import contextmanager

from django.db import connection

_PROCESS_LOCKS = weakref.WeakValueDictionary()
_PROCESS_LOCKS_GUARD = threading.Lock()


def _build_verification_code_lock_name(*, email, purpose):
    digest = hashlib.sha256(
        f"{purpose}:{email.strip().lower()}".encode("utf-8")
    ).hexdigest()
    return f"users:verification:{digest[:44]}"


def _build_verification_delivery_lock_name(*, verification_code_id):
    return f"users:verification-delivery:{int(verification_code_id)}"


def _get_process_lock(lock_name):
    with _PROCESS_LOCKS_GUARD:
        process_lock = _PROCESS_LOCKS.get(lock_name)
        if process_lock is None:
            process_lock = threading.Lock()
            _PROCESS_LOCKS[lock_name] = process_lock
        return process_lock


@contextmanager
def _advisory_lock(lock_name, timeout_seconds=0):
    timeout_seconds = max(int(timeout_seconds or 0), 0)

    if connection.vendor == "mysql":
        acquired = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, %s)", [lock_name, timeout_seconds])
                row = cursor.fetchone()
            acquired = bool(row and row[0] == 1)
            yield acquired
        finally:
            if acquired:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", [lock_name])
        return

    process_lock = _get_process_lock(lock_name)
    if timeout_seconds == 0:
        acquired = process_lock.acquire(blocking=False)
    else:
        acquired = process_lock.acquire(timeout=timeout_seconds)

    try:
        yield acquired
    finally:
        if acquired:
            process_lock.release()


@contextmanager
def verification_code_lock(email, purpose, timeout_seconds=0):
    lock_name = _build_verification_code_lock_name(email=email, purpose=purpose)
    with _advisory_lock(lock_name, timeout_seconds) as acquired:
        yield acquired


@contextmanager
def verification_delivery_lock(*, verification_code_id, timeout_seconds=0):
    lock_name = _build_verification_delivery_lock_name(
        verification_code_id=verification_code_id
    )
    with _advisory_lock(lock_name, timeout_seconds) as acquired:
        yield acquired
