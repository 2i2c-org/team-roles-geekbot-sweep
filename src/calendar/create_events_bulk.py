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
from loguru import logger
from rich.progress import track
from rich.prompt import Confirm

from ..encryption.sops import get_decrypted_file
from ..geekbot.get_slack_usergroup_members import SlackUsergroupMembers
from .gcal_api_auth import GoogleCalendarAPI


class CreateBulkEvents:
    """Create Team Role events in a Calendar in Bulk"""

    def __init__(self, date=None):
        self._generate_reference_date(date=date)
        usergroup_name = os.environ["USERGROUP_NAME"]
        self.usergroup_members = (
            SlackUsergroupMembers().get_users_in_usergroup(usergroup_name).keys()
        )

        # Set filepaths
        project_path = Path(__file__).parent.parent.parent
        roles_path = project_path.joinpath("team-roles.json")
        secrets_path = project_path.joinpath("secrets")

        # Check the team roles file exists before reading
        if not os.path.exists(roles_path):
            raise FileNotFoundError(f"File must exist to continue! {roles_path}")

        with open(roles_path) as stream:
            self.team_roles = json.load(stream)

        # Read in the calendar ID and authenticate GCal API
        with get_decrypted_file(
            secrets_path.joinpath("calendar_id.json")
        ) as calendar_id_path:
            with open(calendar_id_path) as f:
                contents = json.load(f)

        self.calendar_id = contents["calendar_id"]
        self.gcal_api = GoogleCalendarAPI().authenticate()

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

        logger.info(
            "Reference date to calculate events from: {}",
            self.reference_date.strftime("%Y-%m-D"),
        )

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

        logger.info(
            "Reference date adjusted to: {}", self.reference_date.strftime("%Y-%m-%d")
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

    def _generate_event_metadata(self, role, name, offset):
        """Generate metadata for an event to be created in a Google Calendar

        Args:
            role (str): The role to create an event for. Either 'meeting-facilitator'
                or 'support-steward'.
            name (str): The name of the team member who will serve in this role for
                this event
            offset (int): The offset from the reference date. The units of this value
                is described by ROLE_CYCLES[role]["units"].

        Returns:
            dict: A dictionary of calendar event metadata. Items include the start and
                end times of the event, and a summary.
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

        return body

    def _create_event(self, event_info):
        """Create an event in a Google Calendar

        Args:
            event_info (dict): Metadata describing the event to create. Must include
                start and end dates, and a summary.
        """
        try:
            # Create the event
            self.gcal_api.events().insert(
                calendarId=self.calendar_id, body=event_info
            ).execute()

        except HttpError as error:
            logger.error(f"An error occured: {error}")

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
        current_member_index = next(
            (
                i
                for (i, name) in enumerate(self.usergroup_members)
                if current_member.lower() in name.lower()
            ),
            None,
        )

        # Set the number of events to create if not specified
        if n_events is None:
            n_events = ROLE_CYCLES[role]["n_events"]

        # Create a repeating list of team members (in order) long enough to index for
        # the number of events we will create
        members = list(
            islice(
                cycle(self.usergroup_members),
                current_member_index + 1,
                n_events + current_member_index + 1,
            )
        )

        logger.info("Generating upcoming events...")

        # Generate the events
        events = []
        for i in range(n_events):
            next_member = members[i]
            event = self._generate_event_metadata(role, next_member, i)
            print(
                event["start"]["date"],
                "->",
                event["end"]["date"],
                ":",
                event["summary"],
            )
            events.append(event)

        confirm = Confirm.ask("Create these events?", default=False)

        if confirm:
            for event in track(events, description="Creating calendar events..."):
                self._create_event(event)
        else:
            logger.info("Ok! Exiting with out creating any events")


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

    CreateBulkEvents(date=args.date).create_bulk_events(
        args.role, name=args.team_member, n_events=args.n_events
    )


if __name__ == "__main__":
    main()
