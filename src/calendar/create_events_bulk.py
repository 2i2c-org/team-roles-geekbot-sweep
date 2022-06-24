"""
Create Team Role Events in a Calendar in bulk
"""
import argparse
import json
import os
from datetime import datetime, timedelta
from itertools import cycle, islice
from pathlib import Path

from dateutil.relativedelta import relativedelta
from googleapiclient.errors import HttpError

from ..geekbot.get_slack_team_members import SlackTeamMembers
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


class CreateBulkEvents:
    """Create Team Role events in a Calendar in Bulk"""

    def __init__(self, date=None):
        self.calendar_id = os.environ["CALENDAR_ID"]
        self._generate_reference_date(date=date)
        self.team_members = SlackTeamMembers().get_users_in_team().keys()
        self.gcal_api = GoogleCalendarAPI().authenticate()

        project_path = Path(__file__).parent.parent.parent
        team_roles_path = project_path.joinpath("team-roles.json")
        with open(team_roles_path) as stream:
            self.team_roles = json.load(stream)

    def _generate_reference_date(self, date=None):
        """Generate a reference date to calculate start and end dates for role events
        from. Defaults to the on which the program is run.

        Args:
            date (str, optional): A chosen reference date as a string in the format
                'YYYY-MM-DD'. Defaults to None.
        """
        if date is None:
            self.reference_date = datetime.today()
        else:
            self.reference_date = datetime.strptime(date, "%Y-%m-%d")

    def _adjust_reference_date(self):
        """
        The Support Steward Role is transferred on Wednesdays. We adjust the reference
        date to be the next Wednesday from the given date for the calculations.
        """
        # isoweekday() returns an integer representation of the day of the week where
        # MONDAY is 1 and SUNDAY is 7. Hence, WEDNESDAY is 3.
        weekday_num = self.reference_date.isoweekday()

        if weekday_num < 3:
            self.reference_date = self.reference_date + timedelta(
                days=(3 - weekday_num)
            )
        elif weekday_num > 3:
            self.reference_date = self.reference_date + timedelta(
                days=(7 + (3 - weekday_num))
            )

    def _calculate_event_dates_meeting_facilitator(self, offset):
        """Calculate the start and end dates for a Meeting Facilitator calendar event

        Args:
            offset (int): The offset from the current date in months

        Returns:
            datetime objs: The start and end dates for a Meeting Facilitator event
        """
        # Always calculate the start date for the next month from the reference date
        # given. Hence if offset = 0, we don't create a Meeting Facilitator event for
        # the month we are currently in.
        start_date = self.reference_date + relativedelta(
            months=ROLE_CYCLES["meeting-facilitator"]["frequency"] * offset + 1
        )
        end_date = start_date + relativedelta(
            months=ROLE_CYCLES["meeting-facilitator"]["period"]
        )

        # Meeting Facilitator events last the whole month, so ensure the day attribute
        # is set to the first day of the month. End date is exclusive, so this will
        # always run the end of the month, no matter how many days it contains.
        start_date = start_date.replace(day=1)
        end_date = end_date.replace(day=1)

        return start_date, end_date

    def _calculate_event_dates_support_steward(self, offset):
        """Calculate the start and end dates for a Support Steward calendar event

        Args:
            offset (int): The offset from the current date in fortnights (2 weeks)

        Returns:
            datetime objs: The start and end dates for a Support Steward event
        """
        start_date = self.reference_date + timedelta(
            days=(ROLE_CYCLES["support-steward"]["frequency"] * offset)
        )
        end_date = start_date + timedelta(
            days=(ROLE_CYCLES["support-steward"]["period"])
        )

        return start_date, end_date

    def _create_event(self, role, name, offset):
        """Create an event in a Google Calendar

        Args:
            role (str): The role to create an event for. Either 'meeting-facilitator'
                or 'support-steward'.
            name (str): The name of the team member who will serve in this role for
                this event
            offset (int): The offset from the reference date. The units of this value
                is described by ROLE_CYCLES[role]["units"].
        """
        if role == "meeting-facilitator":
            start_date, end_date = self._calculate_event_dates_meeting_facilitator(
                offset
            )
        elif role == "support-steward":
            start_date, end_date = self._calculate_event_dates_support_steward(offset)

        # This represents the minimum amount of information to POST to the Google
        # Calendar API to create an event in a given calendar.
        body = {
            "summary": f"{' '.join(role.split('-')).title()}: {name.split()[0]}",
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
            # Create the event
            self.gcal_api.events().insert(
                calendarId=self.calendar_id, body=body
            ).execute()

        except HttpError as error:
            print(f"An error occured: {error}")

    def create_bulk_events(self, role, name=None, n_events=None):
        """Bulk create Team Role events in a Google Calendar

        Args:
            role (str): The role to create events for. Either 'meeting-facilitator' or
                'support-steward'.
            name (str, optional): The name of the current team member serving in the
                role. Defaults to None, and will be pulled from team-roles.json.
            n_events (int, optional): The number of events to create for the specified
                role. Defaults to ROLE_CYCLES[role]["n_events"].
        """
        # Find the name of the person currently serving in this role from
        # team-roles.json or use a provided 'name' variable
        if role == "meeting-facilitator":
            current_member = (
                self.team_roles[role.replace("-", "_")]["name"]
                if name is None
                else name
            )
        elif role == "support-steward":
            self._adjust_reference_date()
            current_member = (
                self.team_roles[role.replace("-", "_")]["current"]["name"]
                if name is None
                else name
            )

        # Find the index of the current team member in the ordered list
        current_member_index = list(self.team_members).index(current_member)

        # Set the number of events to create if not specified
        if n_events is None:
            n_events = ROLE_CYCLES[role]["n_events"]

        # Create a repeating list of team members (in order) long enough to index for
        # the number of events we will create
        team_members = list(
            islice(
                cycle(self.team_members),
                current_member_index + 1,
                n_events + current_member_index + 1,
            )
        )

        # Create the events
        for i in range(n_events):
            next_team_member = team_members[i]
            self._create_event(role, next_team_member, i)


def main():
    parser = argparse.ArgumentParser(
        description="Bulk create a series of Team Role events in a Google Calendar"
    )

    parser.add_argument(
        "role",
        choices=["meeting-facilitator", "support-steward"],
        help="The role to create events for",
    )
    parser.add_argument(
        "-m",
        "--team-member",
        type=str,
        default=None,
        help="The name of the team member currently serving in the role. Will be pulled from team-roles.json if not provided.",
    )
    parser.add_argument(
        "-n",
        "--n-events",
        type=int,
        default=None,
        help="The number of role events to create. Defaults to 12 for Meeting Facilitator and 26 for Support Steward (both 1 year's worth).",
    )
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        default=None,
        help="A reference date to begin creating events from. Defaults to today. WARNING: EXPERIMENTAL FEATURE.",
    )

    args = parser.parse_args()

    create_bulk_events = CreateBulkEvents(date=args.date)
    create_bulk_events.create_bulk_events(args.role, n_events=args.n_events)


if __name__ == "__main__":
    main()
