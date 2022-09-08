from datetime import datetime

from .gcal_api_auth import GoogleCalendarAPI

# Some information about how often each of our team roles is transferred
ROLE_CYCLES = {
    "meeting-facilitator": {
        "unit": "months",
        "frequency": 1,  # Monthly
        "period": 1,
        "n_events": 12,  # Equates to 1 year
    },
    "support-steward": {
        "unit": "days",
        "frequency": 14,  # Fortnightly
        "period": 28,  # 4 weeks
        "n_events": 26,  # Equates to 1 year
    },
}


class CalendarEventHandler:
    def __init__(self):
        self.gcal_api = GoogleCalendarAPI.athentticate()
        self.today = datetime.today()
