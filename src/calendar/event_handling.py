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
        "index": 1,  # Index to extract next event from
    },
    "support-steward": {
        "unit": "days",
        "frequency": 7,  # Weekly
        "period": 14,  # 2 weeks
        "n_events": 52,  # Equates to 1 year
        "index": 2,  # Index to extract next event from. Allows for overlap of events.
    },
}


class CalendarEventHandler:
    """Handle generating metadata, creating and deleting events in the Team Roles calendar"""

    def __init__(self, role, usergroup_name):
        self.gcal_api = GoogleCalendarAPI().authenticate()
        self.role = role
        self.today = datetime.today()
        self.usergroup_dict = SlackUsergroupMembers().get_users_in_usergroup(
            usergroup_name
        )
        self.usergroup_members = self.usergroup_dict.keys()

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

        # Get list of upcoming events
        self.upcoming_events = self._get_upcoming_events()

    def _get_upcoming_events(self, date=None, nMaxResults=50):
        """Get the upcoming events in a Google calendar for a specific role

        Args:
            date (date obj, optional): The date from which to list events.
                Defaults to TODAY in ISO format.
            nMaxResults (int, optional): The maximum number of future events to
                pull from the calendar. There will be 12 Meeting Facilitator events
                per year and 26 Support Steward events per year - so 50 is enough
                to cover both those event types together, plus some extra.
                Defaults to 50.

        Returns:
            list[dict]: A list of event objects describing all the upcoming events in
                the calendar for the specified role
        """
        # 'Z' indicates UTC timezone
        if date is None:
            date = f"{self.today.isoformat()}Z"
        else:
            date = f"{date.isoformat()}Z"

        try:
            # Get all upcoming events in a calendar
            events_results = (
                self.gcal_api.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=date,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=nMaxResults,
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

    def log_event_metadata(self, event_info):
        """Send metadata for a calendar event to the logger

        Args:
            event_info (dict): An event from the calendar. Must contain the
                following keys: 'summary', 'dateTime' OR both 'start.date',
                'end.date'.
        """
        start_date = event_info.get("dateTime", event_info["start"].get("date"))
        start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")

        end_date = event_info.get("dateTime", event_info["end"].get("date"))
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")

        team_member = event_info["summary"].split(":")[-1].strip()

        # Construct logging message
        log_msg = (
            f"{self.role.replace('-', ' ').title()}: "
            + f"{start_date} -> {end_date}: {team_member}"
        )
        if ((end_date_dt - self.today).days > 0) and (
            (start_date_dt - self.today).days < 0
        ):
            log_msg += " (ongoing)"
        elif ((end_date_dt - self.today).days < 0) and (
            (start_date_dt - self.today).days < 0
        ):
            log_msg += " (past)"
        elif ((end_date_dt - self.today).days > 0) and (
            (start_date_dt - self.today).days > 0
        ):
            log_msg += " (future)"

        logger.info(log_msg)

    def _calculate_next_event_dates(self, event_end_date, offset):
        """Calculate the start and end date of the next event in a series for a role,
        given the end date of the previous event

        Args:
            event_end_date (date obj): The end date of the previous event in the series
            offset (int): An integer multiple of event_end_date to offset the original
                event_end_date by. Used when generating metadata for events in bulk.

        Returns:
            tuple(date obj, date obj): The start and end dates respectively for the next
                event in the series
        """
        # Calculate the end date for the specified role
        if self.role == "meeting-facilitator":
            next_event_start_date = event_end_date + relativedelta(
                months=ROLE_CYCLES[self.role]["frequency"] * offset
            )
            next_event_start_date = next_event_start_date.replace(day=1)

            next_event_end_date = next_event_start_date + relativedelta(
                months=ROLE_CYCLES[self.role]["period"]
            )

        elif self.role == "support-steward":
            next_event_start_date = event_end_date + relativedelta(
                days=ROLE_CYCLES[self.role]["frequency"] * offset
            )
            next_event_end_date = next_event_start_date + relativedelta(
                days=ROLE_CYCLES[self.role]["period"]
            )

        return next_event_start_date, next_event_end_date

    def _find_next_team_member_manually(self, last_member, offset=0):
        """Find the next team member to serve in a given role by iterating
        through a list of team members

        Args:
            last_member (str): The last team member serving in the role
            offset (int, optional): An integer multiple of event_end_date to offset the original
                event_end_date by. Used when generating metadata for events in bulk. Defaults to 0.

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

        next_member_index = last_member_index + 1 + offset
        if next_member_index >= len(self.usergroup_members):
            next_member_index = 0 + (offset % len(self.usergroup_members))

        return list(self.usergroup_members)[next_member_index]

    def find_next_team_member_from_calendar(self):
        """Extract the next team member to serve in a role from a calendar event

        Returns:
            str: The name of the next team member to serve in a role
        """
        logger.info("Extracting next team member from the calendar...")

        for indx in (
            ROLE_CYCLES[self.role]["index"] - 1,
            ROLE_CYCLES[self.role]["index"],
        ):
            try:
                self.log_event_metadata(self.upcoming_events[indx])
            except IndexError:
                pass

        try:
            next_event = self.upcoming_events[ROLE_CYCLES[self.role]["index"]]
            next_member = next_event.get("summary", "").split(":")[-1].strip()
        except IndexError:
            next_member = None

        return next_member

    def get_first_event(self):
        """Extract the metadata of the first event in a series. Metadata extracted are: the
        member who served in the role, and the end date of the event.

        Returns:
            tuple(date obj, str): The end date of the first event in the series, and the team
                member who served in the role during that event
        """
        logger.info("Extracting metadata for first event in the series...")

        # Find the first event in the series
        first_event = self.upcoming_events[0]
        self.log_event_metadata(first_event)

        # Extract the relevant metadata from the first event in the series
        first_event_end_date = first_event.get(
            "dateTime", first_event["end"].get("date")
        )
        first_event_end_date = datetime.strptime(first_event_end_date, "%Y-%m-%d")
        first_member = first_event.get("summary", "").split(":")[-1].strip()

        if self.role == "support-steward":
            # We use [1] here because the support steward role overlaps by 2 two
            # weeks. So for the team member serving in the role, we need to use
            # the next event to calculate where to begin iterating from.
            first_event = self.upcoming_events[1]
            self.log_event_metadata(first_event)

            first_member = first_event.get("summary", "").split(":")[-1].strip()

        return first_event_end_date, first_member

    def _get_last_event(self, suppress_logs=False):
        """Extract the metadata of the last event in a series. Metadata extracted are: the
        member who served in the role, and the end date of the event.

        Args:
            suppress_logs (bool, optional): Don't print out logging statements. USed when generating
                event metadata in bulk and we don't want to clutter the console. Defaults to False.

        Returns:
            tuple(date obj, str): The end date of the last event in the series, and the team
                member who served in the role during that event
        """
        if not suppress_logs:
            logger.info("Extracting metadata for last event in the series...")

        # Find the last event in this series
        last_event = self.upcoming_events[-1]
        if not suppress_logs:
            self.log_event_metadata(last_event)

        # Extract the relevant metadata from the last event in the series
        last_event_end_date = last_event.get("dateTime", last_event["end"].get("date"))
        last_event_end_date = datetime.strptime(last_event_end_date, "%Y-%m-%d")
        last_member = last_event.get("summary", "").split(":")[-1].strip()

        if self.role == "support-steward":
            # We use [-2] here because the support steward role overlaps itself.
            # So for the last event dates, we need the second to last event in
            # the list.
            last_event = self.upcoming_events[-2]
            if not suppress_logs:
                self.log_event_metadata(last_event)

            last_event_end_date = last_event.get(
                "dateTime", last_event["end"].get("date")
            )
            last_event_end_date = datetime.strptime(last_event_end_date, "%Y-%m-%d")

        return last_event_end_date, last_member

    def get_upcoming_events(self, date=None, nMaxResults=50):
        """Get the upcoming events in a Google calendar for a specific role

        Args:
            date (date obj, optional): The date from which to list events.
                Defaults to TODAY in ISO format.
            nMaxResults (int, optional): The maximum number of future events to
                pull from the calendar. There will be 12 Meeting Facilitator events
                per year and 26 Support Steward events per year - so 50 is enough
                to cover both those event types together, plus some extra.
                Defaults to 50.

        Returns:
            list[dict]: A list of event objects describing all the upcoming events in
                the calendar for the specified role
        """
        # 'Z' indicates UTC timezone
        if date is None:
            date = f"{self.today.isoformat()}Z"
            str_date = self.today.strftime("%Y-%m-%d")
        else:
            str_date = date.strftime("%Y-%m-%d")
            date = f"{date.isoformat()}Z"

        logger.info(f"Pulling events starting after: {str_date}")

        try:
            # Get all upcoming events in a calendar
            events_results = (
                self.gcal_api.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=date,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=nMaxResults,
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

    def calculate_next_event_metadata(
        self, ref_date=None, member=None, offset=0, suppress_logs=False
    ):
        """Calculate the metadata for the next event in this role's series. Metadata are:
        - Start date
        - End date
        - Team member serving in that role

        Args:
            ref_date (date obj, optional): A reference date to calculate future event dates from.
                Defaults to None and will pull from the calendar.
            member (str, optional): The team member currently serving in the role. Defaults to None
                and will pull from the calendar.
            offset (int, optional): An integer multiple of event_end_date to offset the original
                event_end_date by. Used when generating metadata for events in bulk. Defaults to 0.
            suppress_logs (bool, optional): Don't print out logging statements. USed when generating
                event metadata in bulk and we don't want to clutter the console. Defaults to False.

        Returns:
            dict: Returns the minimum information for a successful POST to the Google
                Calendar API in order to create an event. Must include a start/end date
                and a summary
        """
        if (ref_date is None) and (member is None):
            last_end_date, last_member = self._get_last_event(suppress_logs)
        else:
            last_member = member
            last_end_date = ref_date

        if not suppress_logs:
            logger.info("Generating metadata for next event...")

        next_member = self._find_next_team_member_manually(last_member, offset)
        start_date, end_date = self._calculate_next_event_dates(last_end_date, offset)

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

    def delete_event(self, event_id):
        """Delete an event from a Google Calendar

        Args:
            event_id (str): The ID of the event to be deleted
        """
        try:
            self.gcal_api.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id,
                sendUpdates=None,
            ).execute()

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
