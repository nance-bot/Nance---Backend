from django.db import models
from django.conf import settings


class GmailEmail(models.Model):
    """Model to store financial emails from Gmail."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    message_id = models.CharField(max_length=100, unique=True)
    thread_id = models.CharField(max_length=100)
    subject = models.TextField()
    sender = models.EmailField()
    email_date = models.DateTimeField()
    body_text = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-email_date']
        indexes = [
            models.Index(fields=['sender', 'email_date']),
            models.Index(fields=['email_date']),
        ]
    
    def __str__(self):
        return f"{self.sender} - {self.subject[:50]}..."


class GmailToken(models.Model):
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    token_expiry = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


