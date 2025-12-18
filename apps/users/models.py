"""
Custom User model and Profile for Meeting Tool.
Supports email/phone authentication with Kenya-specific defaults.
"""

import pytz
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Custom User model using email or phone number as primary identifier.
    Designed for Kenyan professionals with Africa/Nairobi timezone default.
    """
    
    # Role choices
    class Role(models.TextChoices):
        ORGANIZER = 'organizer', 'Organizer'
        PARTICIPANT = 'participant', 'Participant'
        ADMIN = 'admin', 'Admin'
    
    # Phone number validator for Kenyan numbers
    phone_regex = RegexValidator(
        regex=r'^\+254[17]\d{8}$',
        message="Phone number must be in format: '+254712345678'. Kenyan numbers only."
    )
    
    # Primary identifier fields
    email = models.EmailField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text='Email address (primary or alternative identifier)'
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        help_text='Kenyan phone number in format +254XXXXXXXXX'
    )
    
    # Profile information
    full_name = models.CharField(max_length=255, help_text='Full name')
    organization = models.CharField(
        max_length=255,
        blank=True,
        help_text='Organization, company, or institution'
    )
    job_title = models.CharField(
        max_length=100,
        blank=True,
        help_text='Job title or position'
    )
    
    # Timezone - Default to Kenya
    TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.common_timezones]
    timezone = models.CharField(
        max_length=50,
        choices=TIMEZONE_CHOICES,
        default='Africa/Nairobi',
        help_text='User timezone for meeting scheduling'
    )
    
    # Role and permissions
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PARTICIPANT,
        help_text='User role in the system'
    )
    
    # Status fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(
        default=False,
        help_text='Whether email/phone has been verified'
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text='Receive email notifications'
    )
    sms_notifications = models.BooleanField(
        default=False,
        help_text='Receive SMS notifications (charges may apply)'
    )
    
    # Profile picture (optional)
    avatar = models.URLField(
        blank=True,
        null=True,
        help_text='URL to profile picture'
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return self.full_name or self.email or self.phone_number
    
    def get_full_name(self):
        return self.full_name
    
    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else ''
    
    @property
    def identifier(self):
        """Return the primary identifier (email or phone)."""
        return self.email or self.phone_number
    
    @property
    def is_organizer(self):
        return self.role in [self.Role.ORGANIZER, self.Role.ADMIN]
    
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN
    
    def get_timezone(self):
        """Return pytz timezone object."""
        return pytz.timezone(self.timezone)
    
    def clean(self):
        """Validate that at least one identifier is provided."""
        from django.core.exceptions import ValidationError
        
        if not self.email and not self.phone_number:
            raise ValidationError(
                'User must have either an email address or phone number.'
            )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
