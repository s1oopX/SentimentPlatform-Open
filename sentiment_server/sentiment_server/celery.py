from celery import Celery
from celery.schedules import crontab

from sentiment_server.runtime_settings import require_settings_module

require_settings_module()

app = Celery('sentiment_server')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'admin-panel-cleanup-stale-running-training-runs': {
        'task': 'apps.admin_panel.training_tasks.cleanup_stale_running_training_runs_task',
        'schedule': crontab(minute='*/5'),
    },
    'admin-panel-cleanup-operation-logs': {
        'task': 'apps.admin_panel.tasks.cleanup_operation_logs_task',
        'schedule': crontab(minute=10, hour='*/6'),
    },
    'admin-panel-check-auto-retrain-threshold': {
        'task': 'apps.admin_panel.training_tasks.check_auto_retrain_threshold_task',
        'schedule': crontab(minute=15),
    },
    'auth-cleanup-expired-verification-codes': {
        'task': 'apps.admin_panel.tasks.cleanup_expired_verification_codes_task',
        'schedule': crontab(minute=30, hour=3),
    },
}
