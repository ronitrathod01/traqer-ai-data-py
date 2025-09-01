from django.urls import path
from . import views

urlpatterns = [
    path('', views.ListJobView.as_view(), name="list_jobs"),
]