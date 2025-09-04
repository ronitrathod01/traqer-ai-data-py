import logging
from django.utils import timezone
from scraper.models import Job
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)

class JobService:
    def __init__(self):
        self.active_jobs = {}

    def _estimate_job_duration(self, job_data: dict) -> int:
        """
        Estimate job duration based on type and payload.
        Mirrors Node.js logic.
        """
        job_type = job_data.get("type")
        payload = job_data.get("payload", {}) or {}

        if job_type == Job.JobType.SINGLE_SCRAPE:
            return 60  # 1 minute per keyword

        elif job_type == Job.JobType.BATCH_SCRAPE:
            keywords = payload.get("keywords") or []
            delay = payload.get("options", {}).get("delay", 30000)  # ms
            concurrent = payload.get("options", {}).get("maxConcurrent", 1)

            # (number of keywords / concurrent) * (60s + delay in seconds)
            return int(
                (len(keywords) / concurrent) * (60 + delay / 1000)
            )

        else:
            return 60

    def create_job(self, job_data: dict) -> Job:
        try:
            job = Job.objects.create(
                **job_data,
                created_at=timezone.now(),
                estimated_duration=self._estimate_job_duration(job_data)
            )
            logger.info(f"Job created: {job.id} (type: {job.type})")
            return job

        except Exception as e:
            logger.error(f"Failed to create job: {e}", exc_info=True)
            raise
        
    def get_job(self, job_id):
        try:
            job = Job.objects.get(id=job_id)
            return job
        except ObjectDoesNotExist:
            return None
        except Exception as e:
            logger.error("Failed to get job: %s", str(e), exc_info=True)
            raise
            
    
    def update_job(self, job_id, updates: dict):
        try:
            # Always update "updated_at" timestamp
            updates["updated_at"] = timezone.now()

            # Get and update job
            job = Job.objects.filter(id=job_id).update(**updates)

            if not job:  # update() returns number of rows updated
                raise ValueError(f"Job not found: {job_id}")

            # Fetch updated job object
            job_obj = Job.objects.get(id=job_id)

            # Track active jobs
            if updates.get("status") == "running":
                self.active_jobs[str(job_id)] = job_obj
            elif updates.get("status") in ["completed", "failed", "cancelled"]:
                self.active_jobs.pop(str(job_id), None)
                
            print(f"-------------------------Job updated: {job_obj.id} (status: {job_obj.status})--------------------------")

            return job_obj

        except Exception as e:
            logger.error(f"Failed to update job: {e}")
            raise
        
    def delete_job(self, job_id):
        try:
            job = Job.objects.filter(id=job_id).first()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            # Delete job
            job.delete()

            # Remove from active jobs if present
            self.active_jobs.pop(str(job_id), None)

            logger.info(f"Job deleted: {job_id}")
            return job

        except Exception as e:
            logger.error(f"Failed to delete job: {e}", exc_info=True)
            raise e