import os


def require_settings_module():
    """Return the configured Django settings module or fail fast."""
    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
    if settings_module is None:
        raise RuntimeError('DJANGO_SETTINGS_MODULE 未设置，请先显式设置后再启动 Django/Celery。')
    settings_module = settings_module.strip()
    if not settings_module:
        raise RuntimeError('DJANGO_SETTINGS_MODULE 未设置，请先显式设置后再启动 Django/Celery。')
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
    return settings_module
