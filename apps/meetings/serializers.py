"""
Serializers for Meeting scheduling.
"""

from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers

from apps.users.serializers import UserListSerializer
from .models import Meeting, MeetingParticipant, Availability, BlockedTime
from .services import check_meeting_conflicts


class MeetingParticipantSerializer(serializers.ModelSerializer):
    """
    Serializer for meeting participants with response status.
    """
    user = UserListSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = MeetingParticipant
        fields = [
            'id', 'user', 'user_id', 'response_status',
            'response_message', 'responded_at', 'attended'
        ]
        read_only_fields = ['id', 'responded_at']


class MeetingSerializer(serializers.ModelSerializer):
    """
    Full serializer for meeting details.
    """
    organizer = UserListSerializer(read_only=True)
    participant_responses = MeetingParticipantSerializer(many=True, read_only=True)
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text='List of participant user IDs'
    )
    participant_count = serializers.SerializerMethodField()
    is_upcoming = serializers.BooleanField(read_only=True)
    location_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'organizer',
            'participant_responses', 'participant_ids', 'participant_count',
            'start_time', 'end_time', 'duration_minutes',
            'location_type', 'physical_address', 'physical_landmark',
            'virtual_platform', 'virtual_link', 'virtual_meeting_id', 'virtual_passcode',
            'status', 'recurrence_pattern', 'recurrence_end_date',
            'is_private', 'allow_guest_participants', 'notes',
            'is_upcoming', 'location_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'organizer', 'status', 'created_at', 'updated_at'
        ]
    
    def get_participant_count(self, obj):
        return obj.get_participant_count()
    
    def validate(self, attrs):
        """
        Validate meeting data.
        """
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        duration = attrs.get('duration_minutes', 30)
        
        # Ensure start time is in the future for new meetings
        if not self.instance and start_time:
            if start_time <= timezone.now():
                raise serializers.ValidationError({
                    'start_time': 'Meeting start time must be in the future.'
                })
        
        # Calculate end_time if not provided
        if start_time and not end_time:
            attrs['end_time'] = start_time + timedelta(minutes=duration)
        elif start_time and end_time:
            if end_time <= start_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time.'
                })
        
        # Validate location fields
        location_type = attrs.get('location_type', Meeting.LocationType.VIRTUAL)
        
        if location_type in [Meeting.LocationType.PHYSICAL, Meeting.LocationType.HYBRID]:
            if not attrs.get('physical_address'):
                raise serializers.ValidationError({
                    'physical_address': 'Physical address is required for physical/hybrid meetings.'
                })
        
        if location_type in [Meeting.LocationType.VIRTUAL, Meeting.LocationType.HYBRID]:
            if not attrs.get('virtual_link') and not attrs.get('virtual_platform'):
                raise serializers.ValidationError({
                    'virtual_link': 'Virtual meeting link or platform is required for virtual/hybrid meetings.'
                })
        
        return attrs
    
    def create(self, validated_data):
        """
        Create meeting with participants.
        """
        participant_ids = validated_data.pop('participant_ids', [])
        
        meeting = Meeting.objects.create(**validated_data)
        
        # Add participants
        for user_id in participant_ids:
            MeetingParticipant.objects.create(
                meeting=meeting,
                user_id=user_id
            )
        
        return meeting
    
    def update(self, instance, validated_data):
        """
        Update meeting and participants.
        """
        participant_ids = validated_data.pop('participant_ids', None)
        
        # Update meeting fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update participants if provided
        if participant_ids is not None:
            # Remove old participants
            instance.participant_responses.exclude(
                user_id__in=participant_ids
            ).delete()
            
            # Add new participants
            existing_ids = set(
                instance.participant_responses.values_list('user_id', flat=True)
            )
            for user_id in participant_ids:
                if user_id not in existing_ids:
                    MeetingParticipant.objects.create(
                        meeting=instance,
                        user_id=user_id
                    )
        
        return instance


class MeetingCreateSerializer(MeetingSerializer):
    """
    Serializer for creating meetings with conflict checking.
    """
    check_conflicts = serializers.BooleanField(
        write_only=True,
        default=True,
        help_text='Check for scheduling conflicts'
    )
    force_create = serializers.BooleanField(
        write_only=True,
        default=False,
        help_text='Create meeting even with conflicts'
    )
    
    class Meta(MeetingSerializer.Meta):
        fields = MeetingSerializer.Meta.fields + ['check_conflicts', 'force_create']
    
    def validate(self, attrs):
        attrs = super().validate(attrs)
        
        check_conflicts = attrs.pop('check_conflicts', True)
        force_create = attrs.pop('force_create', False)
        
        if check_conflicts and not force_create:
            user = self.context['request'].user
            conflict_data = {
                'start_time': attrs['start_time'],
                'end_time': attrs['end_time'],
                'duration_minutes': attrs.get('duration_minutes', 30),
                'participants': attrs.get('participant_ids', [])
            }
            
            conflicts = check_meeting_conflicts(conflict_data, user)
            
            if conflicts['has_any_conflicts']:
                raise serializers.ValidationError({
                    'conflicts': {
                        'message': 'Scheduling conflicts detected.',
                        'details': {
                            'organizer': conflicts['organizer_conflicts'],
                            'participants': conflicts['participant_conflicts']
                        },
                        'suggestions': conflicts['suggested_alternatives'][:3]
                    }
                })
        
        return attrs


class MeetingListSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for meeting lists.
    """
    organizer_name = serializers.CharField(source='organizer.full_name', read_only=True)
    participant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'start_time', 'end_time', 'duration_minutes',
            'location_type', 'status', 'organizer_name', 'participant_count'
        ]
    
    def get_participant_count(self, obj):
        return obj.get_participant_count()


class ParticipantResponseSerializer(serializers.Serializer):
    """
    Serializer for participant meeting response.
    """
    response_status = serializers.ChoiceField(
        choices=MeetingParticipant.ResponseStatus.choices
    )
    response_message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500
    )


class AvailabilitySerializer(serializers.ModelSerializer):
    """
    Serializer for user availability windows.
    """
    day_name = serializers.CharField(
        source='get_day_of_week_display',
        read_only=True
    )
    
    class Meta:
        model = Availability
        fields = [
            'id', 'day_of_week', 'day_name', 'start_time', 'end_time',
            'effective_from', 'effective_until', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time.'
            })
        return attrs
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class BlockedTimeSerializer(serializers.ModelSerializer):
    """
    Serializer for blocked time slots.
    """
    reason_display = serializers.CharField(
        source='get_reason_display',
        read_only=True
    )
    
    class Meta:
        model = BlockedTime
        fields = [
            'id', 'start_datetime', 'end_datetime', 'reason',
            'reason_display', 'description', 'is_all_day', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate(self, attrs):
        if attrs['start_datetime'] >= attrs['end_datetime']:
            raise serializers.ValidationError({
                'end_datetime': 'End time must be after start time.'
            })
        return attrs
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SlotSuggestionRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting slot suggestions.
    """
    preferred_date = serializers.DateField()
    duration_minutes = serializers.IntegerField(
        default=30,
        min_value=5,
        max_value=480
    )
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )
    num_suggestions = serializers.IntegerField(
        default=5,
        min_value=1,
        max_value=20
    )


class ConflictCheckSerializer(serializers.Serializer):
    """
    Serializer for conflict checking requests.
    """
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField(required=False)
    duration_minutes = serializers.IntegerField(
        default=30,
        min_value=5,
        max_value=480
    )
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )
    exclude_meeting_id = serializers.UUIDField(required=False)
