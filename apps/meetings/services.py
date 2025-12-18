"""
Conflict detection and availability checking services.
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Tuple
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
import pytz

from .models import Meeting, Availability, BlockedTime, MeetingParticipant


class ConflictDetector:
    """
    Service for detecting meeting conflicts and checking availability.
    """
    
    def __init__(self, user, timezone_str='Africa/Nairobi'):
        self.user = user
        self.tz = pytz.timezone(timezone_str)
    
    def check_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
        exclude_meeting_id: Optional[str] = None
    ) -> List[Meeting]:
        """
        Check for conflicting meetings for the user.
        
        Returns list of conflicting meetings.
        """
        # Base query for user's meetings (as organizer or participant)
        conflicts = Meeting.objects.filter(
            Q(organizer=self.user) | Q(participants=self.user),
            is_deleted=False,
            status__in=['scheduled', 'in_progress']
        ).filter(
            # Overlapping time check
            Q(start_time__lt=end_time, end_time__gt=start_time)
        ).distinct()
        
        # Exclude the meeting being edited
        if exclude_meeting_id:
            conflicts = conflicts.exclude(id=exclude_meeting_id)
        
        return list(conflicts)
    
    def check_blocked_times(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[BlockedTime]:
        """
        Check for blocked time slots.
        
        Returns list of blocked times that conflict.
        """
        blocked = BlockedTime.objects.filter(
            user=self.user,
            start_datetime__lt=end_time,
            end_datetime__gt=start_time
        )
        return list(blocked)
    
    def check_availability_window(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> bool:
        """
        Check if the requested time falls within user's availability windows.
        
        Returns True if within availability, False otherwise.
        """
        # Get day of week (0 = Monday, 6 = Sunday)
        day_of_week = start_time.weekday()
        
        # Convert to local time for comparison
        local_start = start_time.astimezone(self.tz)
        local_end = end_time.astimezone(self.tz)
        
        # Check if meeting spans multiple days
        if local_start.date() != local_end.date():
            # For multi-day meetings, check each day
            current_date = local_start.date()
            while current_date <= local_end.date():
                if not self._is_day_available(current_date, local_start, local_end):
                    return False
                current_date += timedelta(days=1)
            return True
        
        # Single day meeting - check availability
        return self._is_time_within_availability(
            day_of_week,
            local_start.time(),
            local_end.time()
        )
    
    def _is_day_available(
        self,
        date: datetime.date,
        start_dt: datetime,
        end_dt: datetime
    ) -> bool:
        """Check if a specific day is available."""
        day_of_week = date.weekday()
        
        # Determine time range for this day
        if date == start_dt.date():
            day_start = start_dt.time()
        else:
            day_start = time(0, 0)
        
        if date == end_dt.date():
            day_end = end_dt.time()
        else:
            day_end = time(23, 59)
        
        return self._is_time_within_availability(day_of_week, day_start, day_end)
    
    def _is_time_within_availability(
        self,
        day_of_week: int,
        start_time: time,
        end_time: time
    ) -> bool:
        """Check if time range is within availability window."""
        today = timezone.now().date()
        
        availabilities = Availability.objects.filter(
            user=self.user,
            day_of_week=day_of_week,
            is_active=True
        ).filter(
            Q(effective_from__isnull=True) | Q(effective_from__lte=today),
            Q(effective_until__isnull=True) | Q(effective_until__gte=today)
        )
        
        if not availabilities.exists():
            # No availability defined - use default business hours
            default_start = time(8, 0)  # 8 AM
            default_end = time(18, 0)   # 6 PM
            return start_time >= default_start and end_time <= default_end
        
        # Check if time fits within any availability window
        for avail in availabilities:
            if start_time >= avail.start_time and end_time <= avail.end_time:
                return True
        
        return False
    
    def get_all_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
        exclude_meeting_id: Optional[str] = None
    ) -> dict:
        """
        Get comprehensive conflict report.
        
        Returns dict with meetings, blocked_times, and availability status.
        """
        return {
            'conflicting_meetings': self.check_conflicts(
                start_time, end_time, exclude_meeting_id
            ),
            'blocked_times': self.check_blocked_times(start_time, end_time),
            'within_availability': self.check_availability_window(start_time, end_time),
            'has_conflicts': bool(
                self.check_conflicts(start_time, end_time, exclude_meeting_id) or
                self.check_blocked_times(start_time, end_time)
            )
        }


class SlotSuggester:
    """
    Service for suggesting alternative meeting time slots.
    """
    
    def __init__(
        self,
        users: list,
        duration_minutes: int = 30,
        timezone_str: str = 'Africa/Nairobi'
    ):
        self.users = users
        self.duration = timedelta(minutes=duration_minutes)
        self.tz = pytz.timezone(timezone_str)
        
        # Default business hours (Kenya time)
        self.business_start = time(8, 0)
        self.business_end = time(18, 0)
    
    def suggest_slots(
        self,
        preferred_date: datetime.date,
        num_suggestions: int = 5,
        days_to_search: int = 7
    ) -> List[dict]:
        """
        Suggest available time slots for all participants.
        
        Returns list of suggested slots with availability info.
        """
        suggestions = []
        current_date = preferred_date
        end_date = preferred_date + timedelta(days=days_to_search)
        
        while current_date <= end_date and len(suggestions) < num_suggestions:
            # Skip weekends by default
            if current_date.weekday() < 5:  # Monday to Friday
                day_slots = self._get_available_slots_for_day(current_date)
                suggestions.extend(day_slots)
            
            current_date += timedelta(days=1)
        
        return suggestions[:num_suggestions]
    
    def _get_available_slots_for_day(self, date: datetime.date) -> List[dict]:
        """Get available slots for a specific day."""
        slots = []
        
        # Generate potential time slots (every 30 minutes)
        current_time = datetime.combine(date, self.business_start)
        current_time = self.tz.localize(current_time)
        
        end_time = datetime.combine(date, self.business_end)
        end_time = self.tz.localize(end_time)
        
        while current_time + self.duration <= end_time:
            slot_end = current_time + self.duration
            
            # Check if slot is available for all users
            is_available, unavailable_users = self._check_slot_for_all_users(
                current_time, slot_end
            )
            
            if is_available:
                slots.append({
                    'start_time': current_time,
                    'end_time': slot_end,
                    'duration_minutes': int(self.duration.total_seconds() / 60),
                    'all_available': True,
                    'date': date.isoformat(),
                    'time_display': current_time.strftime('%H:%M') + ' - ' + slot_end.strftime('%H:%M')
                })
            
            # Move to next slot (30-minute increments)
            current_time += timedelta(minutes=30)
        
        return slots
    
    def _check_slot_for_all_users(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Tuple[bool, List]:
        """Check if a slot is available for all users."""
        unavailable_users = []
        
        for user in self.users:
            detector = ConflictDetector(user, str(self.tz))
            conflicts = detector.get_all_conflicts(start_time, end_time)
            
            if conflicts['has_conflicts'] or not conflicts['within_availability']:
                unavailable_users.append(user)
        
        return len(unavailable_users) == 0, unavailable_users
    
    def find_next_available_slot(
        self,
        after_time: datetime,
        max_days: int = 14
    ) -> Optional[dict]:
        """
        Find the next available slot for all users.
        
        Returns the first available slot or None if not found.
        """
        current_time = after_time
        end_search = after_time + timedelta(days=max_days)
        
        while current_time < end_search:
            # Round to next 30-minute slot
            minutes = current_time.minute
            if minutes % 30 != 0:
                current_time = current_time.replace(
                    minute=(minutes // 30 + 1) * 30 % 60,
                    second=0,
                    microsecond=0
                )
                if minutes >= 30:
                    current_time += timedelta(hours=1)
            
            # Check if within business hours
            local_time = current_time.astimezone(self.tz)
            if local_time.time() < self.business_start:
                current_time = current_time.replace(
                    hour=self.business_start.hour,
                    minute=self.business_start.minute
                )
            elif local_time.time() >= self.business_end:
                # Move to next day
                current_time = current_time + timedelta(days=1)
                current_time = current_time.replace(
                    hour=self.business_start.hour,
                    minute=self.business_start.minute
                )
                continue
            
            # Skip weekends
            if current_time.weekday() >= 5:
                days_until_monday = (7 - current_time.weekday()) % 7 or 7
                current_time = current_time + timedelta(days=days_until_monday)
                current_time = current_time.replace(
                    hour=self.business_start.hour,
                    minute=self.business_start.minute
                )
                continue
            
            slot_end = current_time + self.duration
            is_available, _ = self._check_slot_for_all_users(current_time, slot_end)
            
            if is_available:
                return {
                    'start_time': current_time,
                    'end_time': slot_end,
                    'duration_minutes': int(self.duration.total_seconds() / 60),
                    'all_available': True
                }
            
            # Move to next slot
            current_time += timedelta(minutes=30)
        
        return None


def check_meeting_conflicts(meeting_data: dict, user) -> dict:
    """
    Convenience function to check conflicts for a meeting.
    
    Args:
        meeting_data: Dict with start_time, end_time, participants
        user: The organizer
    
    Returns:
        Dict with conflict information and suggestions
    """
    from apps.users.models import User
    
    start_time = meeting_data['start_time']
    end_time = meeting_data.get('end_time') or (
        start_time + timedelta(minutes=meeting_data.get('duration_minutes', 30))
    )
    exclude_id = meeting_data.get('exclude_meeting_id')
    
    # Check organizer conflicts
    organizer_detector = ConflictDetector(user, user.timezone)
    organizer_conflicts = organizer_detector.get_all_conflicts(
        start_time, end_time, exclude_id
    )
    
    # Check participant conflicts
    participant_conflicts = {}
    participant_ids = meeting_data.get('participants', [])
    
    for participant_id in participant_ids:
        try:
            participant = User.objects.get(id=participant_id)
            detector = ConflictDetector(participant, participant.timezone)
            conflicts = detector.get_all_conflicts(start_time, end_time, exclude_id)
            if conflicts['has_conflicts']:
                participant_conflicts[str(participant.id)] = {
                    'user': participant.full_name,
                    'conflicts': conflicts
                }
        except User.DoesNotExist:
            pass
    
    # Get suggestions if there are conflicts
    suggestions = []
    if organizer_conflicts['has_conflicts'] or participant_conflicts:
        all_users = [user] + list(User.objects.filter(id__in=participant_ids))
        suggester = SlotSuggester(
            all_users,
            duration_minutes=meeting_data.get('duration_minutes', 30),
            timezone_str=user.timezone
        )
        suggestions = suggester.suggest_slots(start_time.date())
    
    return {
        'organizer_conflicts': organizer_conflicts,
        'participant_conflicts': participant_conflicts,
        'has_any_conflicts': (
            organizer_conflicts['has_conflicts'] or bool(participant_conflicts)
        ),
        'suggested_alternatives': suggestions
    }
