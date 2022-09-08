"""
Handle the generation, creation and deletion of events in a Google Calendar
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from googleapiclient.errors import HttpError
from loguru import logger

from ..encryption.sops import get_decrypted_file
from ..geekbot.get_slack_usergroup_members import SlackUsergroupMembers
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
    """Handle generating metadata, creating and deleting events in the Team Roles calendar"""

    def __init__(self, role, usergroup_name):
        self.gcal_api = GoogleCalendarAPI().authenticate()
        self.role = role
        self.today = datetime.today()
        self.usergroup_members = (
            SlackUsergroupMembers().get_users_in_usergroup(usergroup_name).keys()
        )

        # Set filepaths
        project_path = Path(__file__).parent.parent.parent
        secrets_path = project_path.joinpath("secrets")

        # Read in calendar ID
        with get_decrypted_file(
            secrets_path.joinpath("calendar_id.json")
        ) as calendar_id_path:
            with open(calendar_id_path) as f:
                contents = json.load(f)

        self.calendar_id = contents["calendar_id"]

    def _calculate_next_event_dates(self, event_end_date):
        """Calculate the start and end date of the next event in a series for a role,
        given the end date of the previous event

        Args:
            event_end_date (date obj): The end date of the previous event in the series

        Returns:
            tuple(date obj, date obj): The start and end dates respectively for the next
                event in the series
        """
        # Since start dates are inclusive and end dates are exclusive, the end and start
        # dates for two consecutive events are equivalent
        next_event_start_date = event_end_date

        # Calculate the end date for the specified role
        if self.role == "meeting-facilitator":
            next_event_end_date = next_event_start_date + relativedelta(
                months=ROLE_CYCLES[self.role]["period"]
            )
        elif self.role == "support-steward":
            next_event_end_date = next_event_start_date + relativedelta(
                days=ROLE_CYCLES[self.role]["period"]
            )

        return next_event_start_date, next_event_end_date

    def _find_next_team_member(self, last_member):
        """Find the next team member to serve in a given role

        Args:
            last_member (str): The last team member serving in the role

        Returns:
            str: The next team member to serve in the role
        """
        # Calculate the next team member to serve in this role
        last_member_index = next(
            (
                i
                for (i, name) in enumerate(self.usergroup_members)
                if last_member.lower() in name.lower()
            ),
            None,
        )

        if last_member_index is None:
            raise ValueError(f"Last team member for {self.role} unknown: {last_member}")

        next_member_index = last_member_index + 1
        if next_member_index >= len(self.usergroup_members):
            next_member_index = 0

        return list(self.usergroup_members)[next_member_index]

    def _get_last_event(self):
        """Extract the metadata of the last event in a series. Metadata extracted are: the
        member who served in the role, and the end date of the event.

        Returns:
            tuple(date obj, str): The end date of the last event in the series, and the team
                member who served in the role during that event
        """
        logger.info("Extracting metadata for last event in the series...")

        # Get upcoming events for this role
        events = self._get_upcoming_events()

        # Find the last event in this series
        last_event = events[-1]

        # Extract the relevant metadata from the last event in the series
        last_event_end_date = last_event.get("dateTime", last_event["end"].get("date"))
        last_event_end_date = datetime.strptime(last_event_end_date, "%Y-%m-%d")
        last_member = last_event.get("summary", "").split(":")[-1].strip()

        if self.role == "support-steward":
            # We use [-2] here because the support steward role overlaps by 2 two weeks. So for the last evet dates,
            # we need the second to last event in the list
            last_event = events[-2]
            last_event_end_date = last_event.get(
                "dateTime", last_event["end"].get("date")
            )
            last_event_end_date = datetime.strptime(last_event_end_date, "%Y-%m-%d")

        logger.info(f"Currently serving team member: {last_member}")

        return last_event_end_date, last_member

    def _get_upcoming_events(self):
        """Get the upcoming events in a Google calendar for a specific role

        Returns:
            list[dict]: A list of event objects describing all the upcoming events in
                the calendar for the specified role
        """
        try:
            # Get all upcoming events in a calendar
            events_results = (
                self.gcal_api.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=self.today.isoformat() + "Z",  # 'Z' indicates UTC timezone
                    singleEvents=True,
                    orderBy="startTime",
                    # There will be 12 Meeting Facilitator events per year and 26 Support
                    # Steward events per year - so 50 is enough to cover both those event
                    # types together, plus some extra.
                    maxResults=50,
                )
                .execute()
            )
        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            sys.exit(1)

        events = events_results.get("items", [])

        # Filter the events for those that have the specified role in their summary
        events = [
            event
            for event in events
            if " ".join(self.role.split("-")).title() in event["summary"]
        ]

        return events

    def calculate_next_event_data(self):
        """Calculate the metadata for the next event in this role's series. Metadata are:
        - Start date
        - End date
        - Team member serving in that role

        Returns:
            dict: Returns the minimum information for a successful POST to the Google
                Calendar API in order to create an event. Must include a start/end date
                and a summary
        """
        last_end_date, last_member = self._get_last_event()

        logger.info("Generating metadata for next event...")

        next_member = self._find_next_team_member(last_member)
        start_date, end_date = self._calculate_next_event_dates(last_end_date)

        # This represents the minimum amount of information to POST to the Google
        # Calendar API to create an event in a given calendar.
        body = {
            "summary": f"{' '.join(self.role.split('-')).title()}: {next_member.split()[0]}",
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

    def create_event(self, event_info):
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