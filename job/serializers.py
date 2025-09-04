from rest_framework import serializers
from scraper.models import Job

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = "__all__" 
        