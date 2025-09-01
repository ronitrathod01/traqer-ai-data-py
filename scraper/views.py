import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from scraper.models import Job
from scraper.services.scraper_service import ScraperService
from scraper.services.job_service import JobService
from django.conf import settings
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)

class ScraperView(APIView):
    permission_classes = [IsAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scraper_service = ScraperService()
        self.job_service = JobService()

    def post(self, request):
        keyword = request.data.get("keyword")
        method = request.data.get("method", "auto")
        tool_type = request.data.get("tool_type")
        options = request.data.get("options", {})

        if not keyword or not tool_type:
            return Response({
                "success": False,
                "message": "Keyword and tool_type are required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # logger.info(f"Scrape request received for keyword: {keyword} tool_type: {tool_type}")
            print(f"Scrape request received for keyword: {keyword} tool_type: {tool_type}")

            # Create job record
            job = self.job_service.create_job({
                "type": "single_scrape",
                "tool_type": tool_type,
                "payload": {
                    "keyword": keyword,
                    "method": method,
                    "tool_type": tool_type,
                    "options": options
                },
                "user_id": 1,
                "status": "pending",
            })

            # Start scraping (async)
            # In Django, we can use Celery, threading, or asyncio
            # Example using threading for demo:
            import threading
            threading.Thread(
                target=self.scraper_service.scrape_keyword,
                args=(keyword, method, tool_type, options, job.id)
            ).start()

            return Response({
                "success": True,
                "message": "Scraping job started",
                "data": {
                    "jobId": job.id,
                    "keyword": keyword,
                    "method": method,
                    "status": "pending",
                    "estimatedTime": "30-60 seconds",
                }
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.error(f"Scrape single error: {e}")
            return Response({
                "success": False,
                "message": "Failed to start scraping job",
                "error": str(e) if settings.DEBUG else "Internal server error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class JobStautsView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scraper_service = ScraperService()
        self.job_service = JobService()
        
    def get(self, request, job_id):
        try:
            job = self.job_service.get_job(job_id)
            
            if not job:
                return Response({
                    "success": False,
                    "message": "Job not found"
                }, status=status.HTTP_404_NOT_FOUND)
                
            return Response({
                "success": True,
                "data": {
                    "jobId": str(job.id),   
                    "status": job.status,
                    "type": job.type,
                    "progress": getattr(job, "progress", 0),
                    "totalItems": getattr(job, "totalItems", None),
                    "processedItems": getattr(job, "processedItems", 0),
                    "results": getattr(job, "results", None),
                    "error": getattr(job, "error", None),
                    "createdAt": job.created_at,
                    "updatedAt": job.updated_at,
                    "completedAt": job.completed_at,
                }
            })
                        
        except Exception as e:
            logger.error("Get job status error:", exc_info=True)
            return Response({
                "success": False,
                "message": "Failed to get job status",
                "error": str(e) if settings.DEBUG else "Internal server error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)