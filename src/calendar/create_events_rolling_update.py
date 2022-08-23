"""
Create the next event in a series based on the data for the last event in a calendar
"""
import argparse
import os
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from googleapiclient.errors import HttpError
from loguru import logger

from ..geekbot.get_slack_usergroup_members import SlackUsergroupMembers
from .gcal_api_auth import GoogleCalendarAPI

# Some information about how often each of our team roles is transferred
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
    """
    Create the next Team Role event in a series given the last known event in a Calendar
    """

    def __init__(self):
        self.calendar_id = os.environ["CALENDAR_ID"]
        usergroup_name = os.environ["USERGROUP_NAME"]

        self.gcal_api = GoogleCalendarAPI().authenticate()
        self.usergroup_members = (
            SlackUsergroupMembers().get_users_in_usergroup(usergroup_name).keys()
        )

        self._get_todays_date()

    def _get_todays_date(self):
        self.today = datetime.utcnow()

    def _get_upcoming_events(self, role):
        """Get the upcoming events in a Google calendar

        Args:
            role (str): The role we want to retrieve events for. Either
                'meeting-facilitator' or 'support-steward'.

        Returns:
            list[dict]: A list of event objects describing all the upcoming events in
                the calendar for the specified role
        """
        # Get all upcoming events in a calendar
        events_results = (
            self.gcal_api.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=self.today.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
                # There will be 12 Meeting Facilitator events per year and 26 Support
                # Steward events per year - so 50 is enough to cover both those event
                # types together, plus some extra.
                maxResults=50,
            )
            .execute()
        )
        events = events_results.get("items", [])

        # Filter the events for those that have the specified role in their summary
        events = [
            event
            for event in events
            if " ".join(role.split("-")).title() in event["summary"]
        ]

        return events

    def _calculate_next_event_data(self, role):
        """Calculate the metadata for the next event in this role's series. Metadata are:
        - Start date
        - End date
        - Name of person serving in that role

        Args:
            role (str): The role type to generate metadata for. Either
                'meeting-facilitator' or 'support-steward'.

        Returns:
            tuple(datetime obj, datetime obj, str): Returns the start date, end date and
                name of team member in the role for the next event in the series for a
                given role
        """
        logger.info("Generating metadata for next event...")

        # Get upcoming events for this role
        events = self._get_upcoming_events(role)

        # Find the last event in this series
        if role == "meeting-facilitator":
            last_event = events[-1]
        elif role == "support-steward":
            # We use [-2] here because the support steward role overlaps by 2 two weeks
            last_event = events[-2]

        # Extract the relevant metadata from the last event in the series
        last_event_end_date = last_event.get("dateTime", last_event["end"].get("date"))
        last_event_end_date = datetime.strptime(last_event_end_date, "%Y-%m-%d")
        last_member = last_event.get("summary", "").split(":")[-1].strip()

        # Calculate the next team member to serve in this role
        last_member_index = next(
            (
                i
                for (i, name) in enumerate(self.usergroup_members)
                if last_member in name
            ),
            None,
        )
        next_member_index = last_member_index + 1
        if next_member_index >= len(self.usergroup_members):
            next_member_index = 0
        next_member = list(self.usergroup_members)[next_member_index]

        # Since start dates are inclusive and end dates are exclusive, the end and start
        # dates for two consecutive events are equivalent
        next_event_start_date = last_event_end_date

        # Calculate the end date for the specified role
        if role == "meeting-facilitator":
            next_event_end_date = next_event_start_date + relativedelta(
                months=ROLE_CYCLES[role]["period"]
            )
        elif role == "support-steward":
            next_event_end_date = next_event_start_date + timedelta(
                days=ROLE_CYCLES[role]["period"]
            )

        return next_event_start_date, next_event_end_date, next_member

    def create_next_event(self, role):
        """Create the next event in a series in a Google Calendar for a given role

        Args:
            role (str): The role to create an event for. Either 'meeting-facilitator' or
                'support-steward'.
        """
        # Get the metadata for the next event
        start_date, end_date, name = self._calculate_next_event_data(role)

        # This represents the minimum amount of information to POST to the Google
        # Calendar API to create an event in a given calendar.
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
            logger.info(
                f"Creating event ==> {body['summary']}, Start date: {body['start']['date']}, End date: {body['end']['date']}"
            )

            # Create the event
            self.gcal_api.events().insert(
                calendarId=self.calendar_id, body=body
            ).execute()
        except HttpError as error:
            logger.error(f"An error occured: {error}")


def main():
    parser = argparse.ArgumentParser(
        description="Create the next event in a series for a Team Role in a Google Calendar"
    )
    parser.add_argument(
        "role",
        choices=["meeting-facilitator", "support-steward"],
        help="The role to create an event for",
    )
    args = parser.parse_args()
    CreateNextEvent().create_next_event(role=args.role)


if __name__ == "__main__":
    main()
