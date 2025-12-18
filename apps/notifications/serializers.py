"""
Serializers for Notifications app.
"""

from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for notification records.
    """
    notification_type_display = serializers.CharField(
        source='get_notification_type_display',
        read_only=True
    )
    channel_display = serializers.CharField(
        source='get_channel_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    meeting_title = serializers.CharField(
        source='meeting.title',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'notification_type_display',
            'channel', 'channel_display', 'subject', 'message',
            'status', 'status_display', 'meeting', 'meeting_title',
            'sent_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'sent_at']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer for notification preferences.
    """
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'email_invitations', 'email_updates',
            'email_cancellations', 'email_reminders',
            'sms_invitations', 'sms_updates',
            'sms_cancellations', 'sms_reminders',
            'reminder_time_minutes', 'quiet_hours_enabled',
            'quiet_hours_start', 'quiet_hours_end',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
