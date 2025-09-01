import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "traqer_ai_data.settings")

app = Celery("traqer_ai_data")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()