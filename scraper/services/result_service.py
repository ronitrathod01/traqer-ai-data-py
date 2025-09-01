import logging
from django.utils import timezone
from scraper.models import Result, Job

logger = logging.getLogger(__name__)

class ResultService:
    def save_result(self, *, keyword, method, data, job_id=None, created_at=None, user_id=None):
        job = None
        if job_id:
            try:
                job = Job.objects.get(pk=job_id)
            except Job.DoesNotExist:
                logger.warning(f"Job {job_id} not found for result creation")

        # Map to your Result model shape. If your model has the granular fields like aiOverview,
        # you can transform accordingly. Below we store the payload in data JSONField.
        result = Result.objects.create(
            keyword=keyword,
            method=method,
            data=data,  # JSONField
            job=job,
            user_id=user_id,
            created_at=created_at or timezone.now(),
        )
        return result