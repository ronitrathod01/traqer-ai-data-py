from django.urls import path, include
from . import views

urlpatterns = [
    path('scrape/', views.ScraperView.as_view(), name='srape_keyword'),
    path('status/<int:job_id>/', views.JobStautsView.as_view(), name='job_status'),
]