"""
Create the next event in a series based on the data for the last event in a calendar
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dateutil.relativedelta import relativedelta
from googleapiclient.errors import HttpError
from loguru import logger
from rich.prompt import Confirm

from ..encryption.sops import get_decrypted_file
from ..geekbot.get_slack_usergroup_members import SlackUsergroupMembers


class CreateNextEvent:
    """
    Create the next Team Role event in a series given the last known event in a Calendar
    """

    def __init__(self):
        usergroup_name = os.environ["USERGROUP_NAME"]

    def create_next_event(self, role):
        """Create the next event in a series in a Google Calendar for a given role

        Args:
            role (str): The role to create an event for. Either 'meeting-facilitator' or
                'support-steward'.
        """
        # Determine if we are working in a CI environment or not
        ci = os.environ.get("CI", False)

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

        print(body["start"]["date"], "->", body["end"]["date"], ":", body["summary"])

        if not ci:
            confirm = Confirm.ask("Create the above event?", default=False)

        if ci or confirm:
            try:
                logger.info("Creating event...")

                # Create the event
                self.gcal_api.events().insert(
                    calendarId=self.calendar_id, body=body
                ).execute()
            except HttpError as error:
                logger.error(f"An error occured: {error}")
        elif not ci and not confirm:
            logger.info("Ok! Exiting without creating an event")


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
