from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
# {
#     "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc1NTE3OTM5MSwiaWF0IjoxNzU1MDkyOTkxLCJqdGkiOiI0ZDVhZWExYzYwZWI0MDI3OWFlNDgzNWY0MjhlNGRlYyIsInVzZXJfaWQiOiIxIn0.buPymtUsb0yl0TU8bnWf30X5u0_g1P9lLS1bHgTsp_Y",
#     "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzU1MDkzMjkxLCJpYXQiOjE3NTUwOTI5OTEsImp0aSI6ImFjZDY5NWRjMjM1YTRiZWI4MDZjNDFlYTM3ZmE0MTkyIiwidXNlcl9pZCI6IjEifQ.aKOrTVow9QWT1K9qjXYdIa3sNE-Q-DMWbTt4nA1xNPU"
# }
class CustomUser(AbstractUser):
    mobile = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    
    class Meta:
        db_table = 'sms_customuser'  # Explicit table name to avoid conflicts

class OTPRequest(models.Model):
    mobile = models.CharField(max_length=15)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() - self.created_at > timezone.timedelta(minutes=5)

class AAConsent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    consent_id = models.CharField(max_length=100, unique=True)
    vua = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, default="PENDING")  # PENDING, ACTIVE, REVOKED, etc.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.consent_id} ({self.status})"

class AADataSession(models.Model):
    consent = models.ForeignKey(AAConsent, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, default="PENDING")  # PENDING, COMPLETED,etc
    created_at = models.DateTimeField(auto_now_add=True)

class RawAATransaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    consent = models.ForeignKey(AAConsent, on_delete=models.CASCADE)
    txn_id = models.CharField(max_length=100, unique=True)
    narration = models.TextField()
    parsed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    parsed_date = models.DateTimeField(null=True)
    parsed_merchant_name = models.CharField(max_length=100, null=True)
    parsed_transaction_type = models.CharField(max_length=20, null=True, blank=True)
    parsed_payment_mode = models.CharField(max_length=20, null=True, blank=True)
    parsed_received_content = models.TextField(null=True, blank=True)
    raw_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    main_category = models.CharField(max_length=100, null=True, blank=True)
    sub_category = models.CharField(max_length=100, null=True, blank=True)
    matched_sms_txn = models.ForeignKey("RawSMSTransaction", null=True, blank=True, on_delete=models.SET_NULL)

class RawSMSTransaction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    consent = models.ForeignKey(AAConsent, on_delete=models.CASCADE)
    txn_id = models.CharField(max_length=100, unique=True)
    narration = models.TextField()
    parsed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    parsed_date = models.DateTimeField(null=True)
    parsed_merchant_name = models.CharField(max_length=100, null=True)
    parsed_transaction_type = models.CharField(max_length=20, null=True, blank=True)
    parsed_payment_mode = models.CharField(max_length=20, null=True, blank=True)
    parsed_received_content = models.TextField(null=True, blank=True)
    raw_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    main_category = models.CharField(max_length=100, null=True, blank=True)
    sub_category = models.CharField(max_length=100, null=True, blank=True)
    matched_aa_txn = models.ForeignKey("RawAATransaction", null=True, blank=True, on_delete=models.SET_NULL)



class GmailEmail(models.Model):
    """Model to store financial emails from Gmail - Fold-like categorization."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=100, unique=True)
    thread_id = models.CharField(max_length=100)
    subject = models.TextField()
    sender = models.EmailField()
    email_date = models.DateTimeField()
    body_text = models.TextField()
    
    # Fold-like categorization
    category = models.CharField(max_length=50, default='unknown')  # transaction, statement, notification, financial
    subcategory = models.CharField(max_length=50, default='unknown')  # debit_transaction, monthly_statement, etc.
    confidence = models.IntegerField(default=0)  # 0-100 confidence score
    is_transaction = models.BooleanField(default=False)
    is_statement = models.BooleanField(default=False)
    is_notification = models.BooleanField(default=False)
    
    # Transaction details (if applicable)
    parsed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    parsed_merchant = models.CharField(max_length=200, null=True, blank=True)
    parsed_transaction_type = models.CharField(max_length=20, null=True, blank=True)
    parsed_payment_method = models.CharField(max_length=50, null=True, blank=True)  # UPI, Card, Net Banking, etc.
    
    # Email processing status
    is_processed = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    
    # Gmail labels
    gmail_labels = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-email_date']
        indexes = [
            models.Index(fields=['category', 'subcategory']),
            models.Index(fields=['is_transaction', 'email_date']),
            models.Index(fields=['sender', 'email_date']),
        ]
    
    def __str__(self):
        return f"{self.sender} - {self.category} - {self.subject[:50]}..."


class GmailToken(models.Model):
    # user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    token_expiry = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # def __str__(self):
    #     return f"{self.user.email} Gmail Token"

class SMSMessage(models.Model):
    """Model to store raw SMS messages with timestamp"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    sms_text = models.TextField()
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"SMS at {self.timestamp}: {self.sms_text[:50]}..."