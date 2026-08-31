from django.db import models

class Review(models.Model):
    url = models.URLField(db_index=True)
    reviewer = models.CharField(max_length=255)
    rating = models.IntegerField()          # 1-5
    content = models.TextField()
    date = models.DateTimeField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('url', 'reviewer', 'date')  # avoid duplicates

    def __str__(self):
        return f"{self.reviewer} - {self.rating}★"