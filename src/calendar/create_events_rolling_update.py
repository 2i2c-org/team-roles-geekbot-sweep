import argparse
import os
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from googleapiclient.errors import HttpError

from ..geekbot.get_slack_team_members import SlackTeamMembers
from .gcal_api_auth import GoogleCalendarAPI

ROLE_CYCLES = {
    "meeting-facilitator": {
        "unit": "months",
        "frequency": 1,  # Monthly
        "period": 1,
        "n_cycles": 12,  # Equates to 1 year
    },
    "support-steward": {
        "unit": "days",
        "frequency": 14,  # Fortnightly
        "period": 28,  # 4 weeks
        "n_cycles": 26,  # Equates to 1 year
    },
}


class CreateNextEvent:
    def __init__(self):
        self.calendar_id = os.environ["CALENDAR_ID"]
        self.gcal_api = GoogleCalendarAPI().authenticate()
        self.team_members = SlackTeamMembers().get_users_in_team().keys()

        self._get_todays_date()

    def _get_todays_date(self):
        self.today = datetime.utcnow()

    def _get_upcoming_events(self, role):
        events_results = (
            self.gcal_api.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=self.today.isoformat() + "Z",
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_results.get("items", [])
        events = [
            event
            for event in events
            if " ".join(role.split("-")).title() in event["summary"]
        ]

        return events

    def _calculate_next_event_data(self, role):
        events = self._get_upcoming_events(role)

        if role == "meeting-facilitator":
            last_event = events[-1]
        elif role == "support-steward":
            last_event = events[-2]

        last_event_end_date = last_event.get("dateTime", last_event["end"].get("date"))
        last_event_end_date = datetime.strptime(last_event_end_date, "%Y-%m-%d")
        last_team_member = last_event.get("summary", "").split(":")[-1].strip()

        last_team_member_index = next(
            (
                i
                for (i, name) in enumerate(self.team_members)
                if last_team_member in name
            ),
            None,
        )
        next_team_member_index = last_team_member_index + 1

        if next_team_member_index >= len(self.team_members):
            next_team_member_index = 0

        next_team_member = list(self.team_members)[next_team_member_index]

        next_event_start_date = last_event_end_date

        if role == "meeting-facilitator":
            next_event_end_date = next_event_start_date + relativedelta(
                months=ROLE_CYCLES[role]["period"]
            )
        elif role == "support-steward":
            next_event_end_date = next_event_start_date + timedelta(
                days=ROLE_CYCLES[role]["period"]
            )

        return next_event_start_date, next_event_end_date, next_team_member

    def create_next_event(self, role):
        start_date, end_date, name = self._calculate_next_event_data(role)

        body = {
            "summary": f"{' '.join(role.split('-')).title()}: {name}",
            "start": {
                "date": start_date.strftime("%Y-%m-%d"),
                "timeZone": "Etc/UTC",
            },
            "end": {
                "date": end_date.strftime("%Y-%m-%d"),
                "timeZone": "Etc/UTC",
            },
        }

        try:
            self.gcal_api.events().insert(
                calendarId=self.calendar_id, body=body
            ).execute()
        except HttpError as error:
            print(f"An error occured: {error}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "role",
        choices=["meeting-facilitator", "support-steward"],
        help="",
    )

    args = parser.parse_args()

    CreateNextEvent().create_next_event(role=args.role)


if __name__ == "__main__":
    main()
