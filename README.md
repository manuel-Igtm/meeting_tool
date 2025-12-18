# Meeting Tool Kenya 🇰🇪

A modern, minimal, and scalable backend system for meeting scheduling, designed specifically for **Kenyan professionals, startups, universities, and SMEs**.

Built with Django, Django REST Framework, and PostgreSQL.

## Features ✨

### User Management
- **Flexible Authentication**: Register and login with email or phone number (+254...)
- **JWT-Based Security**: Secure token-based authentication
- **Role-Based Access**: Organizer, Participant, and Admin roles
- **Kenya-First Defaults**: Africa/Nairobi timezone, Kenyan phone number validation

### Meeting Scheduling
- **Comprehensive Meetings**: Create, update, delete meetings with full details
- **Flexible Locations**: Physical (Nairobi CBD, Westlands, Karen...) or Virtual (Zoom, Google Meet, Teams)
- **Recurring Meetings**: Daily, weekly, biweekly, monthly, or custom patterns
- **Participant Management**: Invite participants, track responses (Accept/Decline/Tentative)

### Smart Scheduling
- **Availability Windows**: Define your available hours per day
- **Conflict Detection**: Automatic detection of double-bookings
- **Alternative Suggestions**: Smart suggestions for conflict-free time slots
- **Blocked Time**: Mark vacation, busy time, or holidays

### Notifications
- **Email Notifications**: Beautiful HTML emails for invitations, updates, reminders
- **SMS Support**: Integration with Africa's Talking (Kenya-optimized) or Twilio
- **Reminder System**: Automated reminders 30, 15, and 5 minutes before meetings
- **Preference Control**: Users control what notifications they receive

## Tech Stack 🛠️

- **Framework**: Django 4.2 + Django REST Framework
- **Database**: PostgreSQL
- **Authentication**: JWT (Simple JWT)
- **Task Queue**: Celery + Redis
- **SMS**: Africa's Talking / Twilio
- **API Docs**: drf-spectacular (OpenAPI/Swagger)
- **Timezone**: pytz with Africa/Nairobi default

## Project Structure 📁

```
meeting_tool/
├── manage.py
├── requirements.txt
├── .env.example
├── meeting_tool/           # Project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
└── apps/
    ├── core/               # Shared utilities
    │   ├── models.py       # Base models (TimeStamped, SoftDelete)
    │   ├── permissions.py  # Custom permissions
    │   └── exceptions.py   # Custom exceptions
    ├── users/              # User management
    │   ├── models.py       # Custom User model
    │   ├── serializers.py
    │   ├── views.py
    │   └── urls.py
    ├── meetings/           # Meeting scheduling
    │   ├── models.py       # Meeting, Availability, BlockedTime
    │   ├── services.py     # Conflict detection, slot suggestions
    │   ├── serializers.py
    │   ├── views.py
    │   └── urls.py
    └── notifications/      # Email & SMS notifications
        ├── models.py       # Notification tracking
        ├── email.py        # Email service
        ├── sms.py          # SMS providers (Africa's Talking, Twilio)
        ├── tasks.py        # Celery tasks
        └── views.py
```

## Quick Start 🚀

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis (for Celery)

### Installation

1. **Clone and setup environment**
   ```bash
   cd meeting_tool
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Setup database**
   ```bash
   # Create PostgreSQL database
   createdb meeting_tool_db
   
   # Run migrations
   python manage.py migrate
   ```

4. **Create admin user**
   ```bash
   python manage.py createsuperuser
   ```

5. **Create logs directory**
   ```bash
   mkdir logs
   ```

6. **Run the server**
   ```bash
   python manage.py runserver
   ```

7. **Start Celery (for notifications)**
   ```bash
   # In a separate terminal
   celery -A meeting_tool worker -l info
   
   # For scheduled tasks
   celery -A meeting_tool beat -l info
   ```

## API Endpoints 📡

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/users/register/` | Register new user |
| POST | `/api/v1/users/login/` | Login (get JWT tokens) |
| POST | `/api/v1/users/logout/` | Logout (blacklist token) |
| POST | `/api/v1/users/token/refresh/` | Refresh access token |

### Profile
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/profile/` | Get current user profile |
| PATCH | `/api/v1/users/profile/` | Update profile |
| POST | `/api/v1/users/password/change/` | Change password |

### Meetings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/meetings/` | List all meetings |
| POST | `/api/v1/meetings/` | Create meeting |
| GET | `/api/v1/meetings/{id}/` | Get meeting details |
| PUT/PATCH | `/api/v1/meetings/{id}/` | Update meeting |
| DELETE | `/api/v1/meetings/{id}/` | Cancel meeting |
| POST | `/api/v1/meetings/{id}/respond/` | Respond to invitation |
| GET | `/api/v1/meetings/today/` | Today's meetings |
| GET | `/api/v1/meetings/this_week/` | This week's meetings |

### Scheduling
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/meetings/check-conflicts/` | Check for conflicts |
| POST | `/api/v1/meetings/suggest-slots/` | Get available slots |
| GET | `/api/v1/meetings/availability/` | List availability windows |
| POST | `/api/v1/meetings/availability/` | Add availability |
| POST | `/api/v1/meetings/availability/set_business_hours/` | Set business hours |
| GET | `/api/v1/meetings/blocked-time/` | List blocked times |
| POST | `/api/v1/meetings/blocked-time/` | Block time |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/notifications/` | List notifications |
| GET | `/api/v1/notifications/preferences/` | Get preferences |
| PATCH | `/api/v1/notifications/preferences/` | Update preferences |
| GET | `/api/v1/notifications/count/` | Get notification count |

## Example Requests 📝

### Register User
```bash
curl -X POST http://localhost:8000/api/v1/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.co.ke",
    "full_name": "John Kamau",
    "organization": "Tech Startup Nairobi",
    "password": "securepass123",
    "password_confirm": "securepass123"
  }'
```

### Register with Phone (Kenya)
```bash
curl -X POST http://localhost:8000/api/v1/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "0712345678",
    "full_name": "Jane Wanjiku",
    "password": "securepass123",
    "password_confirm": "securepass123"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/v1/users/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "john@example.co.ke",
    "password": "securepass123"
  }'
```

### Create Meeting
```bash
curl -X POST http://localhost:8000/api/v1/meetings/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "title": "Project Kickoff",
    "description": "Initial planning session for the new project",
    "start_time": "2024-01-15T09:00:00+03:00",
    "duration_minutes": 60,
    "location_type": "virtual",
    "virtual_platform": "google_meet",
    "virtual_link": "https://meet.google.com/abc-defg-hij",
    "participant_ids": ["<user-uuid-1>", "<user-uuid-2>"]
  }'
```

### Check Conflicts
```bash
curl -X POST http://localhost:8000/api/v1/meetings/check-conflicts/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "start_time": "2024-01-15T09:00:00+03:00",
    "duration_minutes": 60,
    "participant_ids": ["<user-uuid>"]
  }'
```

### Get Slot Suggestions
```bash
curl -X POST http://localhost:8000/api/v1/meetings/suggest-slots/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "preferred_date": "2024-01-15",
    "duration_minutes": 30,
    "participant_ids": ["<user-uuid>"],
    "num_suggestions": 5
  }'
```

## API Documentation 📚

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema**: http://localhost:8000/api/schema/

## Environment Variables 🔐

Key environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Debug mode | `False` |
| `SECRET_KEY` | Django secret key | - |
| `DATABASE_URL` | PostgreSQL URL | - |
| `DEFAULT_TIMEZONE` | Default timezone | `Africa/Nairobi` |
| `SMS_PROVIDER` | SMS provider | `africastalking` |
| `AFRICASTALKING_API_KEY` | Africa's Talking API key | - |

## Future Enhancements 🔮

This system is designed to support:

- **MPesa Integration**: Paid meeting bookings via MPesa
- **Calendar Sync**: Google Calendar and Outlook integration
- **Multi-Organization**: Support for multiple organizations/tenants
- **Video Integration**: Built-in video conferencing
- **Mobile App**: React Native / Flutter companion app

## Contributing 🤝

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License 📄

MIT License - feel free to use this project for your own applications.

## Support 💬

For questions or support, please open an issue on GitHub.

---

**Built with ❤️ for Kenya and Africa** 🌍
