from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class Job(models.Model):
    class JobType(models.TextChoices):
        SINGLE_SCRAPE = 'single_scrape', 'Single Scrape'
        BATCH_SCRAPE = 'batch_scrape', 'Batch Scrape'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    class ToolType(models.TextChoices):
        GOOGLE = 'google', 'Google'
        CHATGPT = 'chatgpt', 'ChatGPT'
        PERPLEXITY = 'perplexity', 'Perplexity'

    type = models.CharField(
        max_length=20,
        choices=JobType.choices,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    tool_type = models.CharField(
        max_length=20,
        choices=ToolType.choices,
        db_index=True
    )

    payload = models.JSONField(blank=True, null=True)

    results = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True, null=True)

    progress = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    total_items = models.PositiveIntegerField(default=1)
    processed_items = models.PositiveIntegerField(default=0)

    user_id = models.CharField(max_length=255, db_index=True)

    priority = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    estimated_duration = models.PositiveIntegerField(blank=True, null=True)  # seconds
    actual_duration = models.PositiveIntegerField(blank=True, null=True)  # seconds

    class Meta:
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['type', 'status']),
        ]
        ordering = ['-created_at']

    @property
    def duration(self):
        """Virtual field like Mongoose virtual."""
        if self.started_at and self.completed_at:
            return round((self.completed_at - self.started_at).total_seconds())
        return None

    def save(self, *args, **kwargs):
        """Override save to mimic pre-save middleware."""
        if self.status == self.Status.COMPLETED and self.started_at and self.completed_at:
            self.actual_duration = round((self.completed_at - self.started_at).total_seconds())
        super().save(*args, **kwargs)

    @classmethod
    def get_active_jobs(cls):
        """Equivalent of Job.getActiveJobs() in Mongoose."""
        return cls.objects.filter(status__in=[cls.Status.PENDING, cls.Status.RUNNING])

    @classmethod
    def get_job_stats(cls):
        """Equivalent of Job.getJobStats() in Mongoose."""
        from django.db.models import Count, Avg
        stats = cls.objects.values('status').annotate(
            count=Count('id'),
            avg_duration=Avg('actual_duration')
        )
        return {
            s['status']: {
                'count': s['count'],
                'avgDuration': s['avg_duration']
            }
            for s in stats
        }

    def __str__(self):
        return f"{self.type} - {self.status}"
    
    
    
class Result(models.Model):
    class Method(models.TextChoices):
        SCRAPING_BROWSER = 'scrapingBrowser', 'Scraping Browser'
        RESIDENTIAL_PROXY = 'residentialProxy', 'Residential Proxy'

    keyword = models.CharField(max_length=255, db_index=True)
    method = models.CharField(
        max_length=50,
        choices=Method.choices
    )

    # Data structure stored as JSON (matches Mongoose nested object)
    data = models.JSONField(blank=True, null=True)

    # Relationship to Job (foreign key)
    job = models.ForeignKey(
        'scraper.Job',
        on_delete=models.CASCADE,
        related_name='job_results',
        db_index=True
    )

    user_id = models.CharField(max_length=255, db_index=True)

    metadata = models.JSONField(blank=True, null=True)

    quality_score = models.PositiveIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    quality_factors = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['keyword', '-created_at']),
            models.Index(fields=['job']),
            models.Index(fields=['-quality_score']),
            models.Index(fields=['method', '-created_at']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """
        Equivalent to Mongoose pre('save') middleware.
        Automatically calculate quality score before saving.
        """
        if self.data and isinstance(self.data, dict) and self.data.get('aiOverview'):
            overview = self.data.get('aiOverview', {})

            # Factors
            text_length = len(overview.get('text', '') or '')
            link_count = len(overview.get('links', []) or [])
            word_count = overview.get('wordCount') or 0
            image_count = len(overview.get('images', '') or '')

            # Score calculation
            score = 0
            score += min(40, text_length / 50)  # Text length factor
            score += min(30, link_count * 5)    # Link count factor
            score += min(30, word_count / 10)   # Word count factor

            self.quality_score = round(score)
            self.quality_factors = {
                'textLength': text_length,
                'linkCount': link_count,
                'imageCount': image_count,
                'relevance': 80 if word_count > 50 else 40
            }

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.keyword} ({self.method})"