"""
Delete Team Role Events in a Calendar in bulk
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from loguru import logger
from rich.progress import track
from rich.prompt import Confirm

from ..encryption.sops import get_decrypted_file
from ..geekbot.get_slack_usergroup_members import SlackUsergroupMembers
from .gcal_api_auth import GoogleCalendarAPI


class DeleteBulkEvents:
    """Delete Team Role events in a Calendar in Bulk from a given reference date"""

    def __init__(self, date=None):
        self._generate_reference_date(date=date)
        usergroup_name = os.environ["USERGROUP_NAME"]
        self.user_group_members = (
            SlackUsergroupMembers().get_users_in_usergroup(usergroup_name).keys()
        )

        # Set filepaths
        project_path = Path(__file__).parent.parent.parent
        secrets_path = project_path.joinpath("secrets")

        # Read in the calendar ID and authenticate GCal API
        with get_decrypted_file(
            secrets_path.joinpath("calendar_id.json")
        ) as calendar_id_path:
            with open(calendar_id_path) as f:
                contents = json.load(f)

        self.calendar_id = contents["calendar_id"]
        self.gcal_api = GoogleCalendarAPI().authenticate()

    def _generate_reference_date(self, date=None):
        """Generate a reference date from when to begin listing and deleting events.
        Defaults to the 1st of the next month from which the program is run.

        Args:
            date (str, optional): A chosen reference date as a string in the format
                'YYYY-MM-DD'. Defaults to None.
        """
        if date is None:
            next_month = datetime.today() + relativedelta(months=1)
            self.reference_date = datetime(next_month.year, next_month.month, 1)
        else:
            self.reference_date = datetime.strptime(date, "%Y-%m-%d")

        logger.info(
            "Reference date to calculate events from: {}",
            self.reference_date.strftime("%Y-%m-%d"),
        )

    def _delete_an_event(self, event_id):
        """Delete an event from a Google Calendar

        Args:
            event_id (str): The ID of the event to be deleted
        """
        self.gcal_api.events().delete(
            calendarId=self.calendar_id,
            eventId=event_id,
            sendUpdates=None,
        ).execute()

    def _list_all_events(self, role):
        """List all the upcoming events for a specific role

        Args:
            role (str): The role to list events for

        Returns:
            list[dict]: A list of dictionaries containing metadata about the upcoming
                events for the specified role
        """
        # Retrieve all events after the given reference date
        events = (
            self.gcal_api.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=self.reference_date.isoformat() + "Z",  # 'Z' indicates UTC time
                singleEvents=True,
                orderBy="startTime",
                # The calendar is kept populated ~1 year in advance. 52 weeks per year.
                # Support Steward is fortnightly, so that's 26 events per year. Hence
                # setting maxResults to 30 is more than enough to cover all upcoming
                # events.
                maxResults=30,
            )
            .execute()
        )
        events = events.get("items", None)

        # Filter events for the specified role
        events = [event for event in events if role in event["summary"].lower()]

        return events

    def delete_all_future_role_events(self, role):
        """Retreive, list and confirm the deletion of the upcoming events for a
        specified role in a Google Calendar

        Args:
            role (str): The role to retreive, list, and delete events for
        """
        role = role.replace("-", " ")
        events = self._list_all_events(role)

        if not events:
            logger.info("No upcoming events found")
            sys.exit()

        logger.info(f"{len(events)} events for {role.title()} found")

        for event in events:
            print(
                event["start"]["date"],
                "->",
                event["end"]["date"],
                ":",
                event["summary"],
            )

        confirm = Confirm.ask("Delete all these events?", default=False)

        if confirm:
            for event in track(
                events, description=f"Deleting {role.title()} events..."
            ):
                self._delete_an_event(event["id"])
            logger.info("Event deletion completed")
        else:
            logger.info("Ok! Exiting without deleting anything")
            sys.exit()


def main():
    parser = argparse.ArgumentParser(
        description="Bulk delete all upcoming Team Role events in a Google Calendar",
    )

    parser.add_argument(
        "role",
        choices=["meeting-facilitator", "support-steward"],
        help="The role to delete events for",
    )
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        default=None,
        help="A reference date to begin creating events from. Defaults to the 1st of the next month.",
    )

    args = parser.parse_args()

    DeleteBulkEvents(date=args.date).delete_all_future_role_events(role=args.role)


if __name__ == "__main__":
    main()
