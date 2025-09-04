from django.urls import path
from . import views   

urlpatterns = [
    path("<int:id>/", views.GetJobView.as_view(), name="list_jobs"),
    path("delete/<int:id>/", views.DeleteJobView.as_view(), name="delete-job"),
    path("<int:id>/cancel/", views.CancelJobView.as_view(), name="cancel-job"),
]