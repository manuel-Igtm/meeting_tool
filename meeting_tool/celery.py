"""
Celery configuration for meeting_tool project.
Handles async tasks like notifications and reminders.
"""

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meeting_tool.settings')

app = Celery('meeting_tool')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    # Send meeting reminders every 5 minutes
    'send-meeting-reminders': {
        'task': 'apps.notifications.tasks.send_scheduled_reminders',
        'schedule': crontab(minute='*/5'),
    },
    # Clean up old notifications daily at midnight Kenya time
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=0, minute=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
