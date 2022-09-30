"""
Create the next event in a series based on the data for the last event in a calendar
"""
import argparse
import os

from loguru import logger
from rich.prompt import Confirm

from .event_handling import CalendarEventHandler


def create_next_event(role):
    """Create the next event in a series in a Google Calendar for a given role

    Args:
        role (str): Which role we wish to create a new event for. Can be either
            'meeting-facilitator' or 'support-steward'.
    """
    # Set variables from environment
    ci = os.environ.get("CI", False)
    usergroup_name = os.environ["USERGROUP_NAME"]

    # Instatiate the event handler
    event_handler = CalendarEventHandler(role, usergroup_name)

    next_event_info = event_handler.calculate_next_event_data()
    event_handler.log_event_metadata(next_event_info)

    if not ci:
        confirm = Confirm.ask("Create the above event?", default=False)

    if ci or confirm:
        logger.info("Creating event...")
        event_handler.create_event(next_event_info)
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
    create_next_event(args.role)


if __name__ == "__main__":
    main()
