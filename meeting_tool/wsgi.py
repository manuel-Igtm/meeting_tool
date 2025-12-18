"""
WSGI config for meeting_tool project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meeting_tool.settings')

application = get_wsgi_application()
