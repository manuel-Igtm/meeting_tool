"""
Admin configuration for Notifications app.
"""

from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'notification_type', 'channel', 
        'status', 'sent_at', 'created_at'
    ]
    list_filter = ['notification_type', 'channel', 'status', 'created_at']
    search_fields = ['user__full_name', 'user__email', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at', 'sent_at', 'delivered_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Recipient', {'fields': ('user', 'meeting')}),
        ('Content', {'fields': ('notification_type', 'channel', 'subject', 'message')}),
        ('Status', {'fields': ('status', 'sent_at', 'delivered_at', 'error_message', 'retry_count')}),
        ('External', {'fields': ('external_id',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'email_invitations', 'sms_reminders',
        'reminder_time_minutes', 'quiet_hours_enabled'
    ]
    search_fields = ['user__full_name', 'user__email']
    
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Email Preferences', {
            'fields': ('email_invitations', 'email_updates', 'email_cancellations', 'email_reminders')
        }),
        ('SMS Preferences', {
            'fields': ('sms_invitations', 'sms_updates', 'sms_cancellations', 'sms_reminders')
        }),
        ('Reminder Settings', {'fields': ('reminder_time_minutes',)}),
        ('Quiet Hours', {
            'fields': ('quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end'),
            'classes': ('collapse',)
        }),
    )
