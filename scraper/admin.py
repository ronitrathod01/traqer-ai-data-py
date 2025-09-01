from django.contrib import admin
from .models import Job, Result


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'type', 'status', 'tool_type', 'priority',
        'progress', 'user_id', 'created_at', 'updated_at','estimated_duration'
    )
    list_filter = ('type', 'status', 'tool_type', 'priority', 'created_at')
    search_fields = ('user_id',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'actual_duration', 'duration')


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'keyword', 'method', 'job', 'user_id',
        'quality_score', 'created_at'
    )
    list_filter = ('method', 'created_at')
    search_fields = ('keyword', 'user_id')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'quality_score', 'quality_factors')