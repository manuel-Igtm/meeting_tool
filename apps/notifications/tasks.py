"""
Celery tasks for sending notifications asynchronously.
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_meeting_invitation(self, meeting_id: str):
    """
    Send meeting invitation to all participants.
    """
    from apps.meetings.models import Meeting
    from apps.notifications.models import Notification, NotificationPreference
    from apps.notifications.email import EmailService
    from apps.notifications.sms import send_sms
    
    try:
        meeting = Meeting.objects.select_related('organizer').prefetch_related(
            'participant_responses__user'
        ).get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.error(f"Meeting not found: {meeting_id}")
        return
    
    for participant_response in meeting.participant_responses.all():
        user = participant_response.user
        
        # Get notification preferences
        try:
            prefs = user.notification_preferences
        except NotificationPreference.DoesNotExist:
            prefs = None
        
        # Send email notification
        if user.email and user.email_notifications:
            if not prefs or prefs.should_send_email('invitation'):
                try:
                    success = EmailService.send_meeting_invitation(meeting, user)
                    
                    # Log notification
                    Notification.objects.create(
                        user=user,
                        meeting=meeting,
                        notification_type=Notification.NotificationType.MEETING_INVITATION,
                        channel=Notification.Channel.EMAIL,
                        subject=f"Meeting Invitation: {meeting.title}",
                        message=f"Invitation to {meeting.title}",
                        status=Notification.Status.SENT if success else Notification.Status.FAILED
                    )
                except Exception as e:
                    logger.error(f"Email notification failed for {user.email}: {str(e)}")
        
        # Send SMS notification
        if user.phone_number and user.sms_notifications:
            if not prefs or prefs.should_send_sms('invitation'):
                try:
                    import pytz
                    kenya_tz = pytz.timezone('Africa/Nairobi')
                    local_time = meeting.start_time.astimezone(kenya_tz)
                    
                    message = (
                        f"MeetingTool: {meeting.organizer.full_name} invited you to "
                        f"'{meeting.title}' on {local_time.strftime('%b %d at %I:%M%p')} EAT."
                    )
                    
                    success, status_msg, external_id = send_sms(user.phone_number, message)
                    
                    notification = Notification.objects.create(
                        user=user,
                        meeting=meeting,
                        notification_type=Notification.NotificationType.MEETING_INVITATION,
                        channel=Notification.Channel.SMS,
                        subject=f"Meeting Invitation",
                        message=message,
                        status=Notification.Status.SENT if success else Notification.Status.FAILED,
                        external_id=external_id or ''
                    )
                    if not success:
                        notification.error_message = status_msg
                        notification.save()
                        
                except Exception as e:
                    logger.error(f"SMS notification failed for {user.phone_number}: {str(e)}")
    
    logger.info(f"Invitations sent for meeting: {meeting.title}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_meeting_update(self, meeting_id: str, changes: list = None):
    """
    Send meeting update notifications to all participants.
    """
    from apps.meetings.models import Meeting
    from apps.notifications.models import Notification, NotificationPreference
    from apps.notifications.email import EmailService
    from apps.notifications.sms import send_sms
    
    try:
        meeting = Meeting.objects.select_related('organizer').prefetch_related(
            'participant_responses__user'
        ).get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.error(f"Meeting not found: {meeting_id}")
        return
    
    changes = changes or ['Meeting details have been updated']
    
    for participant_response in meeting.participant_responses.all():
        user = participant_response.user
        
        try:
            prefs = user.notification_preferences
        except:
            prefs = None
        
        # Email notification
        if user.email and user.email_notifications:
            if not prefs or prefs.should_send_email('update'):
                try:
                    EmailService.send_meeting_update(meeting, user, changes)
                    Notification.objects.create(
                        user=user,
                        meeting=meeting,
                        notification_type=Notification.NotificationType.MEETING_UPDATE,
                        channel=Notification.Channel.EMAIL,
                        subject=f"Meeting Updated: {meeting.title}",
                        message=f"Changes: {', '.join(changes)}",
                        status=Notification.Status.SENT
                    )
                except Exception as e:
                    logger.error(f"Update email failed: {str(e)}")
        
        # SMS notification
        if user.phone_number and user.sms_notifications:
            if not prefs or prefs.should_send_sms('update'):
                try:
                    message = f"MeetingTool: '{meeting.title}' has been updated. Check your email for details."
                    send_sms(user.phone_number, message)
                except Exception as e:
                    logger.error(f"Update SMS failed: {str(e)}")
    
    logger.info(f"Update notifications sent for meeting: {meeting.title}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_meeting_cancellation(self, meeting_id: str):
    """
    Send meeting cancellation notifications.
    """
    from apps.meetings.models import Meeting
    from apps.notifications.models import Notification, NotificationPreference
    from apps.notifications.email import EmailService
    from apps.notifications.sms import send_sms
    
    try:
        meeting = Meeting.objects.select_related('organizer').prefetch_related(
            'participant_responses__user'
        ).get(id=meeting_id)
    except Meeting.DoesNotExist:
        logger.error(f"Meeting not found: {meeting_id}")
        return
    
    for participant_response in meeting.participant_responses.all():
        user = participant_response.user
        
        try:
            prefs = user.notification_preferences
        except:
            prefs = None
        
        # Email notification
        if user.email and user.email_notifications:
            if not prefs or prefs.should_send_email('cancellation'):
                try:
                    EmailService.send_meeting_cancellation(meeting, user)
                    Notification.objects.create(
                        user=user,
                        meeting=meeting,
                        notification_type=Notification.NotificationType.MEETING_CANCELLATION,
                        channel=Notification.Channel.EMAIL,
                        subject=f"Meeting Cancelled: {meeting.title}",
                        message=f"Meeting cancelled by {meeting.organizer.full_name}",
                        status=Notification.Status.SENT
                    )
                except Exception as e:
                    logger.error(f"Cancellation email failed: {str(e)}")
        
        # SMS notification (cancellations are usually sent via SMS too)
        if user.phone_number and user.sms_notifications:
            if not prefs or prefs.should_send_sms('cancellation'):
                try:
                    message = f"MeetingTool: '{meeting.title}' has been CANCELLED by {meeting.organizer.full_name}."
                    send_sms(user.phone_number, message)
                except Exception as e:
                    logger.error(f"Cancellation SMS failed: {str(e)}")
    
    logger.info(f"Cancellation notifications sent for meeting: {meeting.title}")


@shared_task
def send_scheduled_reminders():
    """
    Send reminders for upcoming meetings.
    This task should run every 5 minutes.
    """
    from apps.meetings.models import Meeting, MeetingParticipant
    from apps.notifications.models import Notification, NotificationPreference
    from apps.notifications.email import EmailService
    from apps.notifications.sms import send_sms
    
    now = timezone.now()
    
    # Default reminder times: 30 minutes, 15 minutes, 5 minutes before
    reminder_windows = [
        (30, 35),  # 30-35 minutes before
        (15, 20),  # 15-20 minutes before
        (5, 10),   # 5-10 minutes before
    ]
    
    for min_minutes, max_minutes in reminder_windows:
        window_start = now + timedelta(minutes=min_minutes)
        window_end = now + timedelta(minutes=max_minutes)
        
        # Find meetings starting in this window
        meetings = Meeting.objects.filter(
            start_time__gte=window_start,
            start_time__lt=window_end,
            status=Meeting.Status.SCHEDULED,
            is_deleted=False
        ).select_related('organizer').prefetch_related('participant_responses__user')
        
        for meeting in meetings:
            minutes_until = int((meeting.start_time - now).total_seconds() / 60)
            
            # Send reminder to organizer
            _send_reminder_to_user(meeting, meeting.organizer, minutes_until)
            
            # Send reminder to participants
            for participant_response in meeting.participant_responses.filter(
                response_status=MeetingParticipant.ResponseStatus.ACCEPTED
            ):
                _send_reminder_to_user(meeting, participant_response.user, minutes_until)
    
    logger.info("Reminder task completed")


def _send_reminder_to_user(meeting, user, minutes_until):
    """Helper function to send reminder to a specific user."""
    from apps.notifications.models import Notification, NotificationPreference
    from apps.notifications.email import EmailService
    from apps.notifications.sms import send_sms
    
    # Check if reminder already sent
    existing = Notification.objects.filter(
        user=user,
        meeting=meeting,
        notification_type=Notification.NotificationType.MEETING_REMINDER,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).exists()
    
    if existing:
        return
    
    try:
        prefs = user.notification_preferences
    except:
        prefs = None
    
    # Email reminder
    if user.email and user.email_notifications:
        if not prefs or prefs.should_send_email('reminder'):
            try:
                EmailService.send_meeting_reminder(meeting, user, minutes_until)
                Notification.objects.create(
                    user=user,
                    meeting=meeting,
                    notification_type=Notification.NotificationType.MEETING_REMINDER,
                    channel=Notification.Channel.EMAIL,
                    subject=f"Reminder: {meeting.title}",
                    message=f"Meeting starts in {minutes_until} minutes",
                    status=Notification.Status.SENT
                )
            except Exception as e:
                logger.error(f"Reminder email failed: {str(e)}")
    
    # SMS reminder
    if user.phone_number and user.sms_notifications:
        if not prefs or prefs.should_send_sms('reminder'):
            try:
                message = f"MeetingTool REMINDER: '{meeting.title}' starts in {minutes_until} min."
                if meeting.virtual_link:
                    message += f" Join: {meeting.virtual_link}"
                send_sms(user.phone_number, message)
            except Exception as e:
                logger.error(f"Reminder SMS failed: {str(e)}")


@shared_task
def cleanup_old_notifications():
    """
    Clean up old notifications (older than 90 days).
    Runs daily at midnight Kenya time.
    """
    from apps.notifications.models import Notification
    
    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count, _ = Notification.objects.filter(
        created_at__lt=cutoff_date
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old notifications")
