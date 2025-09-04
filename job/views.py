import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from scraper.services.scraper_service import ScraperService
from scraper.services.job_service import JobService
from rest_framework import status
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
from .serializers import JobSerializer

logger = logging.getLogger(__name__)

class GetJobView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scraper_service = ScraperService()
        self.job_service = JobService()
        
    def get(self, request, id):
        try:
            job = self.job_service.get_job(id)
            
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
            
class DeleteJobView(APIView):
    permission_classes = [IsAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.job_service = JobService()
        
    def delete(self, request, id):
        try:
            job = self.job_service.get_job(id)
            
            if not job:
                return Response({
                    "success": False,
                    "message": "Job not found",
                }, status=status.HTTP_404_NOT_FOUND)
                
            if str(job.user_id) != str(request.user.id):
                return Response(
                    {"message": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN
                )
                
            self.job_service.delete_job(id)
            
            serializer = JobSerializer(job)
            
            return Response(
                {"data": serializer.data,
                 "message": "Job deleted successfully"},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error("Delete job error: %s", str(e), exc_info=True)
            return Response(
                {"message": "Failed to delete job"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class CancelJobView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.job_service = JobService()

    def post(self, request, id):
        try:
            job = self.job_service.get_job(id)

            if not job:
                return Response(
                    {"message": "Job not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check ownership
            if str(job.user_id) != str(request.user.id):
                return Response(
                    {"message": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Only allow cancelling if status is pending or running
            if job.status not in ["pending", "running"]:
                return Response(
                    {"message": "Job cannot be cancelled"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update job
            updated_job = self.job_service.update_job(
                job_id=id,
                updates={
                    "status": "cancelled",
                    "completed_at": now()
                }
            )

            serialier = JobSerializer(updated_job)
            
            return Response(
                {
                    "data": serialier.data,
                    "message": "Job cancelled successfully"
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error("Cancel job error: %s", e, exc_info=True)
            return Response(
                {"message": "Failed to cancel job"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )