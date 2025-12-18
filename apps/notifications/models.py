"""
Notification models for tracking sent notifications.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """
    Model to track sent notifications.
    """
    
    class NotificationType(models.TextChoices):
        MEETING_INVITATION = 'invitation', 'Meeting Invitation'
        MEETING_UPDATE = 'update', 'Meeting Update'
        MEETING_CANCELLATION = 'cancellation', 'Meeting Cancellation'
        MEETING_REMINDER = 'reminder', 'Meeting Reminder'
        PARTICIPANT_RESPONSE = 'response', 'Participant Response'
    
    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        PUSH = 'push', 'Push Notification'
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        FAILED = 'failed', 'Failed'
    
    # Recipient
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='Notification recipient'
    )
    
    # Meeting reference (optional - for meeting-related notifications)
    meeting = models.ForeignKey(
        'meetings.Meeting',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text='Related meeting'
    )
    
    # Notification details
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        help_text='Type of notification'
    )
    channel = models.CharField(
        max_length=10,
        choices=Channel.choices,
        help_text='Delivery channel'
    )
    
    # Content
    subject = models.CharField(
        max_length=255,
        help_text='Notification subject'
    )
    message = models.TextField(
        help_text='Notification message body'
    )
    
    # Delivery status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text='Delivery status'
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When notification was sent'
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When notification was delivered'
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text='Error message if delivery failed'
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of delivery attempts'
    )
    
    # External references
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text='External service ID (e.g., Africa\'s Talking message ID)'
    )
    
    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['meeting', 'notification_type']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} to {self.user.full_name}"
    
    def mark_sent(self, external_id=None):
        """Mark notification as sent."""
        from django.utils import timezone
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        if external_id:
            self.external_id = external_id
        self.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])
    
    def mark_failed(self, error_message):
        """Mark notification as failed."""
        self.status = self.Status.FAILED
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])


class NotificationPreference(TimeStampedModel):
    """
    User notification preferences.
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        help_text='User these preferences belong to'
    )
    
    # Email preferences
    email_invitations = models.BooleanField(default=True)
    email_updates = models.BooleanField(default=True)
    email_cancellations = models.BooleanField(default=True)
    email_reminders = models.BooleanField(default=True)
    
    # SMS preferences
    sms_invitations = models.BooleanField(default=False)
    sms_updates = models.BooleanField(default=False)
    sms_cancellations = models.BooleanField(default=True)
    sms_reminders = models.BooleanField(default=True)
    
    # Reminder timing (minutes before meeting)
    reminder_time_minutes = models.PositiveIntegerField(
        default=30,
        help_text='Minutes before meeting to send reminder'
    )
    
    # Quiet hours (no notifications during these hours)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text='Start of quiet hours'
    )
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text='End of quiet hours'
    )
    
    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.full_name}"
    
    def should_send_email(self, notification_type: str) -> bool:
        """Check if email should be sent for this notification type."""
        mapping = {
            'invitation': self.email_invitations,
            'update': self.email_updates,
            'cancellation': self.email_cancellations,
            'reminder': self.email_reminders,
        }
        return mapping.get(notification_type, True)
    
    def should_send_sms(self, notification_type: str) -> bool:
        """Check if SMS should be sent for this notification type."""
        mapping = {
            'invitation': self.sms_invitations,
            'update': self.sms_updates,
            'cancellation': self.sms_cancellations,
            'reminder': self.sms_reminders,
        }
        return mapping.get(notification_type, False)
