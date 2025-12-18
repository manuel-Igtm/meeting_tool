"""
Meeting and Availability models for the Meeting Scheduling Tool.
"""

from datetime import timedelta
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, SoftDeleteModel


class Meeting(SoftDeleteModel):
    """
    Meeting model with support for physical/virtual locations,
    recurring meetings, and Kenya-specific features.
    """
    
    # Meeting status choices
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    # Location type choices
    class LocationType(models.TextChoices):
        PHYSICAL = 'physical', 'Physical Location'
        VIRTUAL = 'virtual', 'Virtual Meeting'
        HYBRID = 'hybrid', 'Hybrid (Physical + Virtual)'
    
    # Virtual platform choices
    class VirtualPlatform(models.TextChoices):
        ZOOM = 'zoom', 'Zoom'
        GOOGLE_MEET = 'google_meet', 'Google Meet'
        MS_TEAMS = 'ms_teams', 'Microsoft Teams'
        OTHER = 'other', 'Other'
    
    # Recurrence pattern choices
    class RecurrencePattern(models.TextChoices):
        NONE = 'none', 'No Recurrence'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        BIWEEKLY = 'biweekly', 'Every Two Weeks'
        MONTHLY = 'monthly', 'Monthly'
        CUSTOM = 'custom', 'Custom'
    
    # Basic meeting information
    title = models.CharField(
        max_length=255,
        help_text='Meeting title'
    )
    description = models.TextField(
        blank=True,
        help_text='Meeting description or agenda'
    )
    
    # Organizer and participants
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organized_meetings',
        help_text='Meeting organizer'
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='MeetingParticipant',
        related_name='meetings',
        help_text='Meeting participants'
    )
    
    # Date and time (timezone-aware)
    start_time = models.DateTimeField(
        help_text='Meeting start time (timezone-aware)'
    )
    end_time = models.DateTimeField(
        help_text='Meeting end time (timezone-aware)'
    )
    duration_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(480)],
        help_text='Meeting duration in minutes (5-480)'
    )
    
    # Location information
    location_type = models.CharField(
        max_length=20,
        choices=LocationType.choices,
        default=LocationType.VIRTUAL,
        help_text='Type of meeting location'
    )
    
    # Physical location (Kenya-specific)
    physical_address = models.CharField(
        max_length=500,
        blank=True,
        help_text='Physical address (e.g., Westlands, Nairobi)'
    )
    physical_landmark = models.CharField(
        max_length=255,
        blank=True,
        help_text='Nearby landmark for directions'
    )
    
    # Virtual meeting details
    virtual_platform = models.CharField(
        max_length=20,
        choices=VirtualPlatform.choices,
        blank=True,
        help_text='Virtual meeting platform'
    )
    virtual_link = models.URLField(
        blank=True,
        help_text='Virtual meeting link'
    )
    virtual_meeting_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Meeting ID (for Zoom, Teams, etc.)'
    )
    virtual_passcode = models.CharField(
        max_length=50,
        blank=True,
        help_text='Meeting passcode if required'
    )
    
    # Meeting status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        help_text='Current meeting status'
    )
    
    # Recurrence settings
    recurrence_pattern = models.CharField(
        max_length=20,
        choices=RecurrencePattern.choices,
        default=RecurrencePattern.NONE,
        help_text='Recurrence pattern'
    )
    recurrence_end_date = models.DateField(
        null=True,
        blank=True,
        help_text='End date for recurring meetings'
    )
    parent_meeting = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurring_instances',
        help_text='Parent meeting for recurring instances'
    )
    
    # Additional settings
    is_private = models.BooleanField(
        default=False,
        help_text='Private meeting (hidden from search)'
    )
    allow_guest_participants = models.BooleanField(
        default=False,
        help_text='Allow non-registered users to join'
    )
    notes = models.TextField(
        blank=True,
        help_text='Meeting notes or minutes'
    )
    
    # Reminder settings
    reminder_sent = models.BooleanField(
        default=False,
        help_text='Whether reminder has been sent'
    )
    
    class Meta:
        verbose_name = 'Meeting'
        verbose_name_plural = 'Meetings'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['organizer', 'start_time']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Calculate end_time from start_time and duration if not set
        if not self.end_time and self.start_time and self.duration_minutes:
            self.end_time = self.start_time + timedelta(minutes=self.duration_minutes)
        super().save(*args, **kwargs)
    
    @property
    def is_upcoming(self):
        """Check if meeting is in the future."""
        return self.start_time > timezone.now()
    
    @property
    def is_past(self):
        """Check if meeting has ended."""
        return self.end_time < timezone.now()
    
    @property
    def is_in_progress(self):
        """Check if meeting is currently in progress."""
        now = timezone.now()
        return self.start_time <= now <= self.end_time
    
    @property
    def location_display(self):
        """Human-readable location string."""
        if self.location_type == self.LocationType.PHYSICAL:
            return self.physical_address or 'Physical location TBD'
        elif self.location_type == self.LocationType.VIRTUAL:
            return f"{self.get_virtual_platform_display()} Meeting"
        else:
            return f"Hybrid: {self.physical_address} + {self.get_virtual_platform_display()}"
    
    def get_participant_count(self):
        """Return total participant count including organizer."""
        return self.participants.count() + 1


class MeetingParticipant(TimeStampedModel):
    """
    Through model for meeting participants with response status.
    """
    
    class ResponseStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        TENTATIVE = 'tentative', 'Tentative'
    
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='participant_responses'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meeting_responses'
    )
    
    response_status = models.CharField(
        max_length=20,
        choices=ResponseStatus.choices,
        default=ResponseStatus.PENDING,
        help_text='Participant response status'
    )
    response_message = models.TextField(
        blank=True,
        help_text='Optional message with response'
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When participant responded'
    )
    
    # Attendance tracking
    attended = models.BooleanField(
        null=True,
        blank=True,
        help_text='Whether participant attended the meeting'
    )
    
    class Meta:
        verbose_name = 'Meeting Participant'
        verbose_name_plural = 'Meeting Participants'
        unique_together = ['meeting', 'user']
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.meeting.title}"
    
    def respond(self, status, message=''):
        """Update participant response."""
        self.response_status = status
        self.response_message = message
        self.responded_at = timezone.now()
        self.save()


class Availability(TimeStampedModel):
    """
    User availability windows for scheduling meetings.
    Designed with Kenyan business hours in mind (8am-6pm EAT).
    """
    
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, 'Monday'
        TUESDAY = 1, 'Tuesday'
        WEDNESDAY = 2, 'Wednesday'
        THURSDAY = 3, 'Thursday'
        FRIDAY = 4, 'Friday'
        SATURDAY = 5, 'Saturday'
        SUNDAY = 6, 'Sunday'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='availabilities',
        help_text='User this availability belongs to'
    )
    
    # Day-based recurring availability
    day_of_week = models.IntegerField(
        choices=DayOfWeek.choices,
        help_text='Day of week for recurring availability'
    )
    
    # Time window
    start_time = models.TimeField(
        help_text='Start time of availability window'
    )
    end_time = models.TimeField(
        help_text='End time of availability window'
    )
    
    # Optional date range for temporary availability changes
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text='Start date (optional, for temporary changes)'
    )
    effective_until = models.DateField(
        null=True,
        blank=True,
        help_text='End date (optional, for temporary changes)'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this availability is active'
    )
    
    class Meta:
        verbose_name = 'Availability'
        verbose_name_plural = 'Availabilities'
        ordering = ['day_of_week', 'start_time']
        indexes = [
            models.Index(fields=['user', 'day_of_week']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class BlockedTime(TimeStampedModel):
    """
    Blocked time slots (vacation, busy time, etc.).
    """
    
    class BlockReason(models.TextChoices):
        VACATION = 'vacation', 'Vacation/Leave'
        BUSY = 'busy', 'Busy'
        PERSONAL = 'personal', 'Personal'
        HOLIDAY = 'holiday', 'Public Holiday'
        OTHER = 'other', 'Other'
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_times',
        help_text='User this blocked time belongs to'
    )
    
    start_datetime = models.DateTimeField(
        help_text='Start of blocked period'
    )
    end_datetime = models.DateTimeField(
        help_text='End of blocked period'
    )
    
    reason = models.CharField(
        max_length=20,
        choices=BlockReason.choices,
        default=BlockReason.BUSY,
        help_text='Reason for blocking time'
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text='Optional description'
    )
    
    # All-day events
    is_all_day = models.BooleanField(
        default=False,
        help_text='Block entire day(s)'
    )
    
    class Meta:
        verbose_name = 'Blocked Time'
        verbose_name_plural = 'Blocked Times'
        ordering = ['start_datetime']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_reason_display()} ({self.start_datetime.date()})"
