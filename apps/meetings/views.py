"""
API Views for Meeting scheduling.
"""

from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.permissions import IsOrganizer, IsOrganizerOrParticipant
from apps.users.models import User
from .models import Meeting, MeetingParticipant, Availability, BlockedTime
from .serializers import (
    MeetingSerializer,
    MeetingCreateSerializer,
    MeetingListSerializer,
    ParticipantResponseSerializer,
    AvailabilitySerializer,
    BlockedTimeSerializer,
    SlotSuggestionRequestSerializer,
    ConflictCheckSerializer,
)
from .services import check_meeting_conflicts, SlotSuggester, ConflictDetector


class MeetingViewSet(ModelViewSet):
    """
    ViewSet for meeting CRUD operations.
    
    Supports:
    - List all meetings (user is organizer or participant)
    - Create new meetings with conflict detection
    - Retrieve meeting details
    - Update meetings (organizer only)
    - Delete/cancel meetings (organizer only)
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'location_type']
    
    def get_queryset(self):
        """
        Return meetings where user is organizer or participant.
        """
        user = self.request.user
        return Meeting.objects.filter(
            Q(organizer=user) | Q(participants=user),
            is_deleted=False
        ).distinct().select_related('organizer').prefetch_related(
            'participant_responses__user'
        )
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MeetingListSerializer
        elif self.action == 'create':
            return MeetingCreateSerializer
        return MeetingSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsOrganizer()]
        return super().get_permissions()
    
    @extend_schema(
        summary="List meetings",
        description="Get all meetings where you are organizer or participant",
        parameters=[
            OpenApiParameter(
                name='upcoming',
                type=bool,
                description='Filter for upcoming meetings only'
            ),
            OpenApiParameter(
                name='date_from',
                type=str,
                description='Filter meetings from this date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='date_to',
                type=str,
                description='Filter meetings until this date (YYYY-MM-DD)'
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filter for upcoming meetings
        if request.query_params.get('upcoming') == 'true':
            queryset = queryset.filter(start_time__gte=timezone.now())
        
        # Date range filtering
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(start_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(start_time__date__lte=date_to)
        
        # Ordering
        queryset = queryset.order_by('start_time')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @extend_schema(
        summary="Create meeting",
        description="Create a new meeting with optional conflict detection"
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        meeting = serializer.save(organizer=request.user)
        
        # Trigger notifications (async)
        from apps.notifications.tasks import send_meeting_invitation
        send_meeting_invitation.delay(str(meeting.id))
        
        return Response({
            'success': True,
            'message': 'Meeting created successfully.',
            'data': MeetingSerializer(meeting).data
        }, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Get meeting details",
        description="Retrieve full details of a meeting"
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = MeetingSerializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @extend_schema(
        summary="Update meeting",
        description="Update meeting details (organizer only)"
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = MeetingSerializer(
            instance,
            data=request.data,
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        meeting = serializer.save()
        
        # Notify participants of update
        from apps.notifications.tasks import send_meeting_update
        send_meeting_update.delay(str(meeting.id))
        
        return Response({
            'success': True,
            'message': 'Meeting updated successfully.',
            'data': MeetingSerializer(meeting).data
        })
    
    @extend_schema(
        summary="Cancel meeting",
        description="Cancel/soft-delete a meeting (organizer only)"
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = Meeting.Status.CANCELLED
        instance.soft_delete()
        
        # Notify participants of cancellation
        from apps.notifications.tasks import send_meeting_cancellation
        send_meeting_cancellation.delay(str(instance.id))
        
        return Response({
            'success': True,
            'message': 'Meeting cancelled successfully.'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    @extend_schema(
        summary="Respond to meeting",
        description="Accept, decline, or mark as tentative"
    )
    def respond(self, request, pk=None):
        """
        Respond to a meeting invitation.
        """
        meeting = self.get_object()
        serializer = ParticipantResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            participant = MeetingParticipant.objects.get(
                meeting=meeting,
                user=request.user
            )
        except MeetingParticipant.DoesNotExist:
            return Response({
                'success': False,
                'message': 'You are not a participant of this meeting.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        participant.respond(
            status=serializer.validated_data['response_status'],
            message=serializer.validated_data.get('response_message', '')
        )
        
        return Response({
            'success': True,
            'message': f"Response recorded: {participant.get_response_status_display()}"
        })
    
    @action(detail=False, methods=['get'])
    @extend_schema(
        summary="Get today's meetings",
        description="Get all meetings scheduled for today (Kenya time)"
    )
    def today(self, request):
        """
        Get meetings scheduled for today.
        """
        import pytz
        kenya_tz = pytz.timezone('Africa/Nairobi')
        today = timezone.now().astimezone(kenya_tz).date()
        
        queryset = self.get_queryset().filter(
            start_time__date=today
        ).order_by('start_time')
        
        serializer = MeetingListSerializer(queryset, many=True)
        return Response({
            'success': True,
            'date': today.isoformat(),
            'data': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    @extend_schema(
        summary="Get this week's meetings",
        description="Get all meetings for the current week"
    )
    def this_week(self, request):
        """
        Get meetings for the current week.
        """
        import pytz
        kenya_tz = pytz.timezone('Africa/Nairobi')
        now = timezone.now().astimezone(kenya_tz)
        
        # Get Monday of current week
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0)
        
        # Get Sunday of current week
        end_of_week = start_of_week + timedelta(days=6)
        end_of_week = end_of_week.replace(hour=23, minute=59, second=59)
        
        queryset = self.get_queryset().filter(
            start_time__gte=start_of_week,
            start_time__lte=end_of_week
        ).order_by('start_time')
        
        serializer = MeetingListSerializer(queryset, many=True)
        return Response({
            'success': True,
            'week_start': start_of_week.date().isoformat(),
            'week_end': end_of_week.date().isoformat(),
            'data': serializer.data
        })


class AvailabilityViewSet(ModelViewSet):
    """
    ViewSet for managing user availability windows.
    """
    serializer_class = AvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Availability.objects.filter(user=self.request.user)
    
    @extend_schema(summary="List availability", description="Get your availability windows")
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @extend_schema(summary="Create availability", description="Add a new availability window")
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'success': True,
            'message': 'Availability added successfully.',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    @extend_schema(
        summary="Set business hours",
        description="Set standard business hours for weekdays (8am-6pm Kenya time by default)"
    )
    def set_business_hours(self, request):
        """
        Set standard business hours for weekdays.
        """
        start_time = request.data.get('start_time', '08:00')
        end_time = request.data.get('end_time', '18:00')
        
        # Clear existing weekday availability
        Availability.objects.filter(
            user=request.user,
            day_of_week__lt=5  # Monday to Friday
        ).delete()
        
        # Create new availability for weekdays
        for day in range(5):  # Monday to Friday
            Availability.objects.create(
                user=request.user,
                day_of_week=day,
                start_time=start_time,
                end_time=end_time
            )
        
        return Response({
            'success': True,
            'message': f'Business hours set: {start_time} - {end_time} (Monday-Friday)'
        })


class BlockedTimeViewSet(ModelViewSet):
    """
    ViewSet for managing blocked time slots.
    """
    serializer_class = BlockedTimeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return BlockedTime.objects.filter(user=self.request.user)
    
    @extend_schema(summary="List blocked times", description="Get your blocked time slots")
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().filter(
            end_datetime__gte=timezone.now()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @extend_schema(summary="Block time", description="Add a new blocked time slot")
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'success': True,
            'message': 'Time blocked successfully.',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)


class ConflictCheckView(APIView):
    """
    Check for scheduling conflicts.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Check conflicts",
        description="Check for meeting conflicts at a specific time",
        request=ConflictCheckSerializer
    )
    def post(self, request):
        serializer = ConflictCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        conflicts = check_meeting_conflicts(data, request.user)
        
        return Response({
            'success': True,
            'has_conflicts': conflicts['has_any_conflicts'],
            'data': conflicts
        })


class SlotSuggestionView(APIView):
    """
    Get suggested meeting time slots.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Get slot suggestions",
        description="Get suggested available time slots for all participants",
        request=SlotSuggestionRequestSerializer
    )
    def post(self, request):
        serializer = SlotSuggestionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Get all users (organizer + participants)
        users = [request.user]
        if data['participant_ids']:
            participants = User.objects.filter(id__in=data['participant_ids'])
            users.extend(list(participants))
        
        suggester = SlotSuggester(
            users=users,
            duration_minutes=data['duration_minutes'],
            timezone_str=request.user.timezone
        )
        
        suggestions = suggester.suggest_slots(
            preferred_date=data['preferred_date'],
            num_suggestions=data['num_suggestions']
        )
        
        return Response({
            'success': True,
            'duration_minutes': data['duration_minutes'],
            'participants': len(users),
            'suggestions': suggestions
        })


class UserAvailabilityView(APIView):
    """
    Get availability for a specific user (for scheduling).
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Get user availability",
        description="Get another user's availability for scheduling"
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'User not found.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get availability windows
        availabilities = Availability.objects.filter(
            user=user,
            is_active=True
        )
        
        # Get blocked times for the next 30 days
        upcoming_blocked = BlockedTime.objects.filter(
            user=user,
            end_datetime__gte=timezone.now(),
            start_datetime__lte=timezone.now() + timedelta(days=30)
        )
        
        return Response({
            'success': True,
            'user': {
                'id': str(user.id),
                'full_name': user.full_name,
                'timezone': user.timezone
            },
            'availability': AvailabilitySerializer(availabilities, many=True).data,
            'blocked_times': BlockedTimeSerializer(upcoming_blocked, many=True).data
        })
