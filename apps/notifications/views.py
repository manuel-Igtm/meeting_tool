"""
API Views for Notifications app.
"""

from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationListView(generics.ListAPIView):
    """
    List all notifications for the authenticated user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).select_related('meeting').order_by('-created_at')
    
    @extend_schema(
        summary="List notifications",
        description="Get all notifications for the current user"
    )
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by type
        type_filter = request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(notification_type=type_filter)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """
    Get or update notification preferences.
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj
    
    @extend_schema(
        summary="Get notification preferences",
        description="Get current user's notification preferences"
    )
    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @extend_schema(
        summary="Update notification preferences",
        description="Update notification preferences"
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'success': True,
            'message': 'Preferences updated successfully.',
            'data': serializer.data
        })


class NotificationCountView(APIView):
    """
    Get unread/pending notification count.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Get notification count",
        description="Get count of pending notifications"
    )
    def get(self, request):
        total = Notification.objects.filter(user=request.user).count()
        pending = Notification.objects.filter(
            user=request.user,
            status=Notification.Status.PENDING
        ).count()
        
        return Response({
            'success': True,
            'data': {
                'total': total,
                'pending': pending
            }
        })


class TestNotificationView(APIView):
    """
    Send a test notification (development only).
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Send test notification",
        description="Send a test email/SMS notification (development)"
    )
    def post(self, request):
        from django.conf import settings
        
        if not settings.DEBUG:
            return Response({
                'success': False,
                'message': 'Test notifications are only available in debug mode.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        channel = request.data.get('channel', 'email')
        user = request.user
        
        if channel == 'email' and user.email:
            from apps.notifications.email import EmailService
            
            html = """
            <h1>Test Notification</h1>
            <p>Habari! This is a test email from Meeting Tool Kenya.</p>
            <p>If you received this, your email notifications are working correctly.</p>
            """
            
            success = EmailService.send_email(
                to_email=user.email,
                subject="Test Notification - Meeting Tool Kenya",
                html_content=html
            )
            
            return Response({
                'success': success,
                'message': 'Test email sent.' if success else 'Failed to send test email.',
                'channel': 'email',
                'recipient': user.email
            })
        
        elif channel == 'sms' and user.phone_number:
            from apps.notifications.sms import send_sms
            
            message = "MeetingTool Test: Your SMS notifications are working! Karibu."
            success, status_msg, external_id = send_sms(user.phone_number, message)
            
            return Response({
                'success': success,
                'message': status_msg,
                'channel': 'sms',
                'recipient': user.phone_number,
                'external_id': external_id
            })
        
        return Response({
            'success': False,
            'message': f'No {channel} address configured for your account.'
        }, status=status.HTTP_400_BAD_REQUEST)
