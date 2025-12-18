"""
Admin configuration for Meetings app.
"""

from django.contrib import admin
from .models import Meeting, MeetingParticipant, Availability, BlockedTime


class MeetingParticipantInline(admin.TabularInline):
    model = MeetingParticipant
    extra = 0
    readonly_fields = ['responded_at']


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'organizer', 'start_time', 'duration_minutes',
        'location_type', 'status', 'created_at'
    ]
    list_filter = ['status', 'location_type', 'recurrence_pattern', 'created_at']
    search_fields = ['title', 'description', 'organizer__full_name', 'organizer__email']
    date_hierarchy = 'start_time'
    readonly_fields = ['created_at', 'updated_at']
    inlines = [MeetingParticipantInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'description', 'organizer', 'status')
        }),
        ('Schedule', {
            'fields': ('start_time', 'end_time', 'duration_minutes')
        }),
        ('Location', {
            'fields': (
                'location_type', 'physical_address', 'physical_landmark',
                'virtual_platform', 'virtual_link', 'virtual_meeting_id', 'virtual_passcode'
            )
        }),
        ('Recurrence', {
            'fields': ('recurrence_pattern', 'recurrence_end_date', 'parent_meeting'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_private', 'allow_guest_participants', 'notes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MeetingParticipant)
class MeetingParticipantAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'user', 'response_status', 'responded_at', 'attended']
    list_filter = ['response_status', 'attended']
    search_fields = ['meeting__title', 'user__full_name', 'user__email']


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ['user', 'day_of_week', 'start_time', 'end_time', 'is_active']
    list_filter = ['day_of_week', 'is_active']
    search_fields = ['user__full_name', 'user__email']


@admin.register(BlockedTime)
class BlockedTimeAdmin(admin.ModelAdmin):
    list_display = ['user', 'start_datetime', 'end_datetime', 'reason', 'is_all_day']
    list_filter = ['reason', 'is_all_day']
    search_fields = ['user__full_name', 'user__email', 'description']
    date_hierarchy = 'start_datetime'
