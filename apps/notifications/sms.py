"""
SMS service abstraction for Kenya-friendly providers.
Supports Africa's Talking and Twilio with Kenya-specific enhancements.

MVP Features:
- Smart message templating with Swahili/English support
- Kenyan phone number validation and formatting
- Cost estimation before sending
- Delivery status tracking
- Business hours awareness (EAT timezone)
- Bulk SMS with rate limiting
- SMS analytics and reporting
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Optional, Tuple, List, Dict, Any
from django.conf import settings
from django.utils import timezone
import pytz

logger = logging.getLogger(__name__)

# Kenya timezone
KENYA_TZ = pytz.timezone('Africa/Nairobi')


class MessageLanguage(Enum):
    """Supported message languages."""
    ENGLISH = 'en'
    SWAHILI = 'sw'
    SHENG = 'sheng'  # Kenyan slang - urban youth


class SMSPriority(Enum):
    """SMS priority levels."""
    LOW = 'low'           # Can be delayed, batch sent
    NORMAL = 'normal'     # Standard delivery
    HIGH = 'high'         # Immediate delivery (reminders)
    CRITICAL = 'critical' # Urgent (cancellations)


@dataclass
class SMSCost:
    """SMS cost estimation."""
    segments: int
    cost_per_segment: float
    total_cost: float
    currency: str = 'KES'
    
    def __str__(self):
        return f"{self.currency} {self.total_cost:.2f} ({self.segments} segment(s))"


@dataclass
class SMSResult:
    """Enhanced SMS delivery result."""
    success: bool
    message: str
    external_id: Optional[str] = None
    provider: str = ''
    cost: Optional[SMSCost] = None
    sent_at: Optional[datetime] = None
    recipient: str = ''
    segments: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'external_id': self.external_id,
            'provider': self.provider,
            'cost': str(self.cost) if self.cost else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'recipient': self.recipient,
            'segments': self.segments
        }


class KenyanPhoneValidator:
    """
    Validates and formats Kenyan phone numbers.
    Supports Safaricom, Airtel, Telkom Kenya, and Faiba.
    """
    
    # Kenyan mobile prefixes by carrier
    CARRIER_PREFIXES = {
        'safaricom': ['701', '702', '703', '704', '705', '706', '707', '708', '709',
                      '710', '711', '712', '713', '714', '715', '716', '717', '718', '719',
                      '720', '721', '722', '723', '724', '725', '726', '727', '728', '729',
                      '740', '741', '742', '743', '745', '746', '748', '757', '758', '759',
                      '768', '769', '790', '791', '792', '793', '794', '795', '796', '797', '798', '799'],
        'airtel': ['730', '731', '732', '733', '734', '735', '736', '737', '738', '739',
                   '750', '751', '752', '753', '754', '755', '756', '762', '780', '781', '782', '783', '784', '785', '786', '787', '788', '789'],
        'telkom': ['770', '771', '772', '773', '774', '775', '776', '777', '778', '779'],
        'faiba': ['747'],
    }
    
    @classmethod
    def validate(cls, phone: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a Kenyan phone number.
        
        Returns:
            Tuple of (is_valid, formatted_number or error_message, carrier)
        """
        if not phone:
            return False, "Phone number is required", None
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Handle different formats
        if cleaned.startswith('+254'):
            number = cleaned[4:]
        elif cleaned.startswith('254'):
            number = cleaned[3:]
        elif cleaned.startswith('0'):
            number = cleaned[1:]
        elif cleaned.startswith('7') or cleaned.startswith('1'):
            number = cleaned
        else:
            return False, f"Invalid Kenyan number format: {phone}", None
        
        # Validate length (9 digits after country code)
        if len(number) != 9:
            return False, f"Invalid number length: expected 9 digits, got {len(number)}", None
        
        # Check if it's a valid mobile number
        prefix = number[:3]
        carrier = None
        
        for carrier_name, prefixes in cls.CARRIER_PREFIXES.items():
            if prefix in prefixes:
                carrier = carrier_name
                break
        
        if not carrier:
            return False, f"Unknown carrier for prefix: {prefix}", None
        
        formatted = f"+254{number}"
        return True, formatted, carrier
    
    @classmethod
    def get_carrier(cls, phone: str) -> Optional[str]:
        """Get the carrier name for a phone number."""
        is_valid, _, carrier = cls.validate(phone)
        return carrier if is_valid else None
    
    @classmethod
    def format_display(cls, phone: str) -> str:
        """Format phone for display: +254 712 345 678"""
        is_valid, formatted, _ = cls.validate(phone)
        if is_valid:
            # Format: +254 7XX XXX XXX
            num = formatted[4:]  # Remove +254
            return f"+254 {num[:3]} {num[3:6]} {num[6:]}"
        return phone


class MessageTemplates:
    """
    Pre-defined SMS templates with Swahili/English support.
    Optimized for 160-character SMS limit.
    """
    
    TEMPLATES = {
        'meeting_invitation': {
            'en': "📅 {organizer} invited you to '{title}' on {date} at {time}. Reply YES to accept or NO to decline.",
            'sw': "📅 {organizer} amekualika mkutano '{title}' tarehe {date} saa {time}. Jibu NDIO kukubali au HAPANA kukataa.",
        },
        'meeting_reminder': {
            'en': "⏰ Reminder: '{title}' starts in {minutes} min. {location}",
            'sw': "⏰ Kumbusho: '{title}' inaanza dakika {minutes}. {location}",
        },
        'meeting_cancelled': {
            'en': "❌ Meeting cancelled: '{title}' scheduled for {date} has been cancelled by {organizer}.",
            'sw': "❌ Mkutano umefutwa: '{title}' wa tarehe {date} umefutwa na {organizer}.",
        },
        'meeting_updated': {
            'en': "🔄 Meeting updated: '{title}' - new time: {date} {time}. Check email for details.",
            'sw': "🔄 Mkutano umebadilishwa: '{title}' - saa mpya: {date} {time}.",
        },
        'meeting_starting': {
            'en': "🚀 '{title}' is starting now! {join_info}",
            'sw': "🚀 '{title}' inaanza sasa! {join_info}",
        },
        'welcome': {
            'en': "Karibu! Welcome to MeetingTool Kenya. Your account is ready. Start scheduling at {url}",
            'sw': "Karibu MeetingTool Kenya! Akaunti yako iko tayari. Anza kupanga mikutano.",
        },
        'otp': {
            'en': "Your MeetingTool verification code is: {code}. Valid for {minutes} minutes. Do not share.",
            'sw': "Nambari yako ya uthibitisho ni: {code}. Inatumika dakika {minutes}. Usishiriki.",
        },
    }
    
    # Greeting based on time of day (Kenya time)
    GREETINGS = {
        'en': {
            'morning': 'Good morning',      # 5am - 12pm
            'afternoon': 'Good afternoon',  # 12pm - 5pm
            'evening': 'Good evening',      # 5pm - 9pm
            'night': 'Hello',               # 9pm - 5am
        },
        'sw': {
            'morning': 'Habari ya asubuhi',
            'afternoon': 'Habari ya mchana',
            'evening': 'Habari ya jioni',
            'night': 'Habari',
        }
    }
    
    @classmethod
    def get_template(
        cls,
        template_name: str,
        language: MessageLanguage = MessageLanguage.ENGLISH,
        **kwargs
    ) -> str:
        """
        Get a formatted template.
        
        Args:
            template_name: Name of the template
            language: Message language
            **kwargs: Template variables
        
        Returns:
            Formatted message string
        """
        templates = cls.TEMPLATES.get(template_name)
        if not templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        template = templates.get(language.value, templates['en'])
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            raise ValueError(f"Missing template variable: {e}")
    
    @classmethod
    def get_greeting(cls, language: MessageLanguage = MessageLanguage.ENGLISH) -> str:
        """Get appropriate greeting based on current Kenya time."""
        kenya_now = datetime.now(KENYA_TZ)
        hour = kenya_now.hour
        
        if 5 <= hour < 12:
            period = 'morning'
        elif 12 <= hour < 17:
            period = 'afternoon'
        elif 17 <= hour < 21:
            period = 'evening'
        else:
            period = 'night'
        
        greetings = cls.GREETINGS.get(language.value, cls.GREETINGS['en'])
        return greetings[period]
    
    @classmethod
    def personalize(
        cls,
        message: str,
        recipient_name: Optional[str] = None,
        language: MessageLanguage = MessageLanguage.ENGLISH
    ) -> str:
        """Add personalized greeting to message."""
        greeting = cls.get_greeting(language)
        
        if recipient_name:
            # Use first name only
            first_name = recipient_name.split()[0]
            return f"{greeting} {first_name}, {message}"
        
        return f"{greeting}, {message}"


class SMSAnalytics:
    """
    Track SMS usage and costs for analytics.
    """
    
    @staticmethod
    def calculate_segments(message: str) -> int:
        """
        Calculate number of SMS segments.
        
        GSM-7: 160 chars (1 segment), 153 chars (multi-segment)
        Unicode: 70 chars (1 segment), 67 chars (multi-segment)
        """
        # Check if message contains non-GSM characters
        gsm_chars = set('@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà')
        
        is_gsm = all(c in gsm_chars for c in message)
        
        length = len(message)
        
        if is_gsm:
            if length <= 160:
                return 1
            return (length + 152) // 153  # Ceiling division
        else:
            # Unicode message
            if length <= 70:
                return 1
            return (length + 66) // 67
    
    @staticmethod
    def estimate_cost(
        message: str,
        recipient_count: int = 1,
        provider: str = 'africastalking'
    ) -> SMSCost:
        """
        Estimate SMS cost before sending.
        
        Approximate rates (KES):
        - Africa's Talking: ~0.80 KES/segment (local)
        - Twilio: ~3.50 KES/segment (international rates)
        """
        segments = SMSAnalytics.calculate_segments(message)
        
        # Cost per segment by provider (approximate)
        rates = {
            'africastalking': 0.80,  # KES
            'twilio': 3.50,          # KES (converted from USD)
            'mock': 0.00,
        }
        
        cost_per_segment = rates.get(provider, 1.00)
        total_cost = segments * cost_per_segment * recipient_count
        
        return SMSCost(
            segments=segments,
            cost_per_segment=cost_per_segment,
            total_cost=total_cost
        )


class BusinessHoursChecker:
    """
    Check if current time is within business hours.
    Helps avoid sending SMS during inappropriate times.
    """
    
    # Default Kenya business hours
    DEFAULT_START = time(8, 0)   # 8:00 AM EAT
    DEFAULT_END = time(20, 0)    # 8:00 PM EAT
    
    # Weekend handling
    WEEKEND_START = time(9, 0)   # 9:00 AM EAT
    WEEKEND_END = time(18, 0)    # 6:00 PM EAT
    
    @classmethod
    def is_business_hours(cls, priority: SMSPriority = SMSPriority.NORMAL) -> bool:
        """
        Check if current Kenya time is within business hours.
        
        Critical and high priority messages bypass this check.
        """
        if priority in [SMSPriority.CRITICAL, SMSPriority.HIGH]:
            return True
        
        kenya_now = datetime.now(KENYA_TZ)
        current_time = kenya_now.time()
        weekday = kenya_now.weekday()
        
        # Weekend (Saturday=5, Sunday=6)
        if weekday >= 5:
            return cls.WEEKEND_START <= current_time <= cls.WEEKEND_END
        
        # Weekday
        return cls.DEFAULT_START <= current_time <= cls.DEFAULT_END
    
    @classmethod
    def get_next_business_hour(cls) -> datetime:
        """Get the next business hour start time."""
        kenya_now = datetime.now(KENYA_TZ)
        
        if cls.is_business_hours():
            return kenya_now
        
        # Calculate next business hour
        current_time = kenya_now.time()
        weekday = kenya_now.weekday()
        
        if weekday >= 5:  # Weekend
            if current_time < cls.WEEKEND_START:
                return kenya_now.replace(
                    hour=cls.WEEKEND_START.hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
            # After weekend hours, go to Monday
            days_until_monday = (7 - weekday) % 7 or 7
            next_day = kenya_now + timedelta(days=days_until_monday)
            return next_day.replace(
                hour=cls.DEFAULT_START.hour,
                minute=0,
                second=0,
                microsecond=0
            )
        else:
            if current_time < cls.DEFAULT_START:
                return kenya_now.replace(
                    hour=cls.DEFAULT_START.hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
            # After business hours, go to next day
            next_day = kenya_now + timedelta(days=1)
            if next_day.weekday() >= 5:  # Weekend
                return next_day.replace(
                    hour=cls.WEEKEND_START.hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
            return next_day.replace(
                hour=cls.DEFAULT_START.hour,
                minute=0,
                second=0,
                microsecond=0
            )


class SMSProvider(ABC):
    """
    Abstract base class for SMS providers.
    """
    
    @abstractmethod
    def send_sms(
        self,
        phone_number: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send an SMS message.
        
        Args:
            phone_number: Recipient phone number in E.164 format (+254...)
            message: Message content
            sender_id: Optional sender ID
        
        Returns:
            Tuple of (success, message, external_id)
        """
        pass
    
    @abstractmethod
    def check_balance(self) -> Optional[float]:
        """Check account balance."""
        pass


class AfricasTalkingProvider(SMSProvider):
    """
    Africa's Talking SMS provider implementation.
    Popular choice for Kenyan and East African markets.
    
    Documentation: https://developers.africastalking.com/
    """
    
    def __init__(self):
        self.username = settings.AFRICASTALKING_USERNAME
        self.api_key = settings.AFRICASTALKING_API_KEY
        self.sender_id = settings.AFRICASTALKING_SENDER_ID
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Africa's Talking client."""
        if self._client is None:
            try:
                import africastalking
                africastalking.initialize(self.username, self.api_key)
                self._client = africastalking.SMS
            except ImportError:
                logger.error("Africa's Talking SDK not installed. Run: pip install africastalking")
                raise
        return self._client
    
    def send_sms(
        self,
        phone_number: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send SMS via Africa's Talking.
        
        Optimized for Kenyan phone numbers (+254...).
        """
        try:
            sender = sender_id or self.sender_id
            
            response = self.client.send(
                message=message,
                recipients=[phone_number],
                sender_id=sender
            )
            
            # Parse response
            if response.get('SMSMessageData', {}).get('Recipients'):
                recipient = response['SMSMessageData']['Recipients'][0]
                status = recipient.get('status', '')
                message_id = recipient.get('messageId', '')
                
                if status == 'Success':
                    logger.info(f"SMS sent successfully to {phone_number}: {message_id}")
                    return True, "SMS sent successfully", message_id
                else:
                    logger.warning(f"SMS failed to {phone_number}: {status}")
                    return False, status, None
            
            return False, "Unknown error", None
            
        except Exception as e:
            logger.error(f"Africa's Talking SMS error: {str(e)}")
            return False, str(e), None
    
    def check_balance(self) -> Optional[float]:
        """Check Africa's Talking account balance."""
        try:
            import africastalking
            africastalking.initialize(self.username, self.api_key)
            application = africastalking.Application
            response = application.fetch_application_data()
            
            balance = response.get('UserData', {}).get('balance', '0')
            # Parse balance string (e.g., "KES 100.00")
            amount = float(balance.replace('KES', '').replace('USD', '').strip())
            return amount
        except Exception as e:
            logger.error(f"Failed to check Africa's Talking balance: {str(e)}")
            return None


class TwilioProvider(SMSProvider):
    """
    Twilio SMS provider implementation.
    Alternative provider with global coverage.
    
    Documentation: https://www.twilio.com/docs/sms
    """
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Twilio client."""
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.error("Twilio SDK not installed. Run: pip install twilio")
                raise
        return self._client
    
    def send_sms(
        self,
        phone_number: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Send SMS via Twilio.
        """
        try:
            from_number = sender_id or self.from_number
            
            tw_message = self.client.messages.create(
                body=message,
                from_=from_number,
                to=phone_number
            )
            
            logger.info(f"Twilio SMS sent to {phone_number}: {tw_message.sid}")
            return True, "SMS sent successfully", tw_message.sid
            
        except Exception as e:
            logger.error(f"Twilio SMS error: {str(e)}")
            return False, str(e), None
    
    def check_balance(self) -> Optional[float]:
        """Check Twilio account balance."""
        try:
            balance = self.client.api.v2010.accounts(self.account_sid).balance.fetch()
            return float(balance.balance)
        except Exception as e:
            logger.error(f"Failed to check Twilio balance: {str(e)}")
            return None


class MockSMSProvider(SMSProvider):
    """
    Mock SMS provider for development and testing.
    """
    
    def send_sms(
        self,
        phone_number: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Log SMS instead of sending (for development).
        """
        logger.info(f"[MOCK SMS] To: {phone_number}")
        logger.info(f"[MOCK SMS] From: {sender_id or 'MeetingTool'}")
        logger.info(f"[MOCK SMS] Message: {message}")
        
        return True, "SMS logged (mock)", f"mock-{phone_number}"
    
    def check_balance(self) -> Optional[float]:
        return 9999.99


def get_sms_provider() -> SMSProvider:
    """
    Factory function to get the configured SMS provider.
    """
    provider_name = getattr(settings, 'SMS_PROVIDER', 'africastalking').lower()
    
    if settings.DEBUG and provider_name != 'mock':
        # Use mock provider in debug mode unless explicitly configured
        api_key = getattr(settings, 'AFRICASTALKING_API_KEY', '')
        if not api_key or api_key == 'sandbox':
            logger.info("Using mock SMS provider in debug mode")
            return MockSMSProvider()
    
    providers = {
        'africastalking': AfricasTalkingProvider,
        'twilio': TwilioProvider,
        'mock': MockSMSProvider,
    }
    
    provider_class = providers.get(provider_name, MockSMSProvider)
    return provider_class()


def send_sms(phone_number: str, message: str) -> Tuple[bool, str, Optional[str]]:
    """
    Convenience function to send SMS using configured provider.
    
    Args:
        phone_number: Kenyan phone number (+254...)
        message: SMS message (max 160 chars for single SMS)
    
    Returns:
        Tuple of (success, status_message, external_id)
    """
    provider = get_sms_provider()
    return provider.send_sms(phone_number, message)
