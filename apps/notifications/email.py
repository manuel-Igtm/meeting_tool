"""
Email service for meeting notifications.
"""

import logging
from typing import List, Optional
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending email notifications.
    """
    
    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (optional)
            from_email: Sender email (defaults to settings)
        
        Returns:
            True if sent successfully
        """
        try:
            from_addr = from_email or settings.DEFAULT_FROM_EMAIL
            
            # Generate plain text if not provided
            if not text_content:
                text_content = strip_tags(html_content)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_addr,
                to=[to_email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_meeting_invitation(meeting, recipient) -> bool:
        """
        Send meeting invitation email.
        """
        context = {
            'meeting': meeting,
            'recipient': recipient,
            'organizer': meeting.organizer,
            'accept_url': f"{settings.FRONTEND_URL}/meetings/{meeting.id}/respond?action=accept" if hasattr(settings, 'FRONTEND_URL') else '#',
            'decline_url': f"{settings.FRONTEND_URL}/meetings/{meeting.id}/respond?action=decline" if hasattr(settings, 'FRONTEND_URL') else '#',
        }
        
        subject = f"Meeting Invitation: {meeting.title}"
        html_content = EmailService._render_meeting_invitation(context)
        
        return EmailService.send_email(
            to_email=recipient.email,
            subject=subject,
            html_content=html_content
        )
    
    @staticmethod
    def send_meeting_update(meeting, recipient, changes: List[str]) -> bool:
        """
        Send meeting update notification.
        """
        context = {
            'meeting': meeting,
            'recipient': recipient,
            'organizer': meeting.organizer,
            'changes': changes,
        }
        
        subject = f"Meeting Updated: {meeting.title}"
        html_content = EmailService._render_meeting_update(context)
        
        return EmailService.send_email(
            to_email=recipient.email,
            subject=subject,
            html_content=html_content
        )
    
    @staticmethod
    def send_meeting_cancellation(meeting, recipient) -> bool:
        """
        Send meeting cancellation notification.
        """
        context = {
            'meeting': meeting,
            'recipient': recipient,
            'organizer': meeting.organizer,
        }
        
        subject = f"Meeting Cancelled: {meeting.title}"
        html_content = EmailService._render_meeting_cancellation(context)
        
        return EmailService.send_email(
            to_email=recipient.email,
            subject=subject,
            html_content=html_content
        )
    
    @staticmethod
    def send_meeting_reminder(meeting, recipient, minutes_until: int) -> bool:
        """
        Send meeting reminder.
        """
        context = {
            'meeting': meeting,
            'recipient': recipient,
            'minutes_until': minutes_until,
        }
        
        subject = f"Reminder: {meeting.title} in {minutes_until} minutes"
        html_content = EmailService._render_meeting_reminder(context)
        
        return EmailService.send_email(
            to_email=recipient.email,
            subject=subject,
            html_content=html_content
        )
    
    @staticmethod
    def _render_meeting_invitation(context: dict) -> str:
        """Render meeting invitation email template."""
        meeting = context['meeting']
        recipient = context['recipient']
        organizer = context['organizer']
        
        # Format time for Kenya timezone
        import pytz
        kenya_tz = pytz.timezone('Africa/Nairobi')
        local_time = meeting.start_time.astimezone(kenya_tz)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .meeting-details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .detail-row {{ margin: 10px 0; }}
                .label {{ font-weight: bold; color: #6b7280; }}
                .buttons {{ margin-top: 20px; text-align: center; }}
                .btn {{ display: inline-block; padding: 12px 24px; margin: 5px; text-decoration: none; border-radius: 6px; }}
                .btn-accept {{ background: #10b981; color: white; }}
                .btn-decline {{ background: #ef4444; color: white; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Meeting Invitation</h1>
                </div>
                <div class="content">
                    <p>Habari {recipient.get_short_name() or recipient.full_name},</p>
                    <p><strong>{organizer.full_name}</strong> has invited you to a meeting:</p>
                    
                    <div class="meeting-details">
                        <h2>{meeting.title}</h2>
                        
                        <div class="detail-row">
                            <span class="label">📅 Date:</span>
                            {local_time.strftime('%A, %B %d, %Y')}
                        </div>
                        
                        <div class="detail-row">
                            <span class="label">🕐 Time:</span>
                            {local_time.strftime('%I:%M %p')} EAT ({meeting.duration_minutes} minutes)
                        </div>
                        
                        <div class="detail-row">
                            <span class="label">📍 Location:</span>
                            {meeting.location_display}
                        </div>
                        
                        {f'<div class="detail-row"><span class="label">🔗 Meeting Link:</span> <a href="{meeting.virtual_link}">{meeting.virtual_link}</a></div>' if meeting.virtual_link else ''}
                        
                        {f'<div class="detail-row"><span class="label">📝 Description:</span><br>{meeting.description}</div>' if meeting.description else ''}
                    </div>
                    
                    <div class="buttons">
                        <a href="{context.get('accept_url', '#')}" class="btn btn-accept">Accept</a>
                        <a href="{context.get('decline_url', '#')}" class="btn btn-decline">Decline</a>
                    </div>
                </div>
                <div class="footer">
                    <p>Meeting Tool Kenya - Scheduling made simple</p>
                    <p>This is an automated message. Please do not reply directly.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def _render_meeting_update(context: dict) -> str:
        """Render meeting update email template."""
        meeting = context['meeting']
        recipient = context['recipient']
        changes = context.get('changes', [])
        
        import pytz
        kenya_tz = pytz.timezone('Africa/Nairobi')
        local_time = meeting.start_time.astimezone(kenya_tz)
        
        changes_html = ''.join([f'<li>{change}</li>' for change in changes])
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f59e0b; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .changes {{ background: #fef3c7; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .meeting-details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Meeting Updated</h1>
                </div>
                <div class="content">
                    <p>Habari {recipient.get_short_name() or recipient.full_name},</p>
                    <p>The following meeting has been updated:</p>
                    
                    <div class="meeting-details">
                        <h2>{meeting.title}</h2>
                        <p><strong>New Time:</strong> {local_time.strftime('%A, %B %d, %Y at %I:%M %p')} EAT</p>
                        <p><strong>Location:</strong> {meeting.location_display}</p>
                    </div>
                    
                    {f'<div class="changes"><h3>What changed:</h3><ul>{changes_html}</ul></div>' if changes else ''}
                </div>
                <div class="footer">
                    <p>Meeting Tool Kenya - Scheduling made simple</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def _render_meeting_cancellation(context: dict) -> str:
        """Render meeting cancellation email template."""
        meeting = context['meeting']
        recipient = context['recipient']
        organizer = context['organizer']
        
        import pytz
        kenya_tz = pytz.timezone('Africa/Nairobi')
        local_time = meeting.start_time.astimezone(kenya_tz)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #ef4444; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .meeting-details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; text-decoration: line-through; opacity: 0.7; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Meeting Cancelled</h1>
                </div>
                <div class="content">
                    <p>Habari {recipient.get_short_name() or recipient.full_name},</p>
                    <p><strong>{organizer.full_name}</strong> has cancelled the following meeting:</p>
                    
                    <div class="meeting-details">
                        <h2>{meeting.title}</h2>
                        <p><strong>Was scheduled for:</strong> {local_time.strftime('%A, %B %d, %Y at %I:%M %p')} EAT</p>
                    </div>
                    
                    <p>This time slot is now available in your calendar.</p>
                </div>
                <div class="footer">
                    <p>Meeting Tool Kenya - Scheduling made simple</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def _render_meeting_reminder(context: dict) -> str:
        """Render meeting reminder email template."""
        meeting = context['meeting']
        recipient = context['recipient']
        minutes_until = context['minutes_until']
        
        import pytz
        kenya_tz = pytz.timezone('Africa/Nairobi')
        local_time = meeting.start_time.astimezone(kenya_tz)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #8b5cf6; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9fafb; }}
                .reminder-badge {{ background: #8b5cf6; color: white; padding: 10px 20px; border-radius: 20px; display: inline-block; }}
                .meeting-details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .join-btn {{ display: inline-block; padding: 15px 30px; background: #10b981; color: white; text-decoration: none; border-radius: 8px; margin-top: 15px; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⏰ Meeting Reminder</h1>
                    <span class="reminder-badge">Starting in {minutes_until} minutes</span>
                </div>
                <div class="content">
                    <p>Habari {recipient.get_short_name() or recipient.full_name},</p>
                    <p>Your meeting is about to start:</p>
                    
                    <div class="meeting-details">
                        <h2>{meeting.title}</h2>
                        <p><strong>🕐 Time:</strong> {local_time.strftime('%I:%M %p')} EAT</p>
                        <p><strong>📍 Location:</strong> {meeting.location_display}</p>
                        
                        {f'<a href="{meeting.virtual_link}" class="join-btn">Join Meeting</a>' if meeting.virtual_link else ''}
                    </div>
                </div>
                <div class="footer">
                    <p>Meeting Tool Kenya - Scheduling made simple</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
