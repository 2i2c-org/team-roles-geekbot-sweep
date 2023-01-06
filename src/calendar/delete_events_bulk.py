"""
Delete Team Role Events in a Calendar in bulk
"""
import argparse
import os
import sys
from datetime import datetime

from loguru import logger
from rich.progress import track
from rich.prompt import Confirm

from .event_handling import CalendarEventHandler


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

    if args.date is not None:
        args.date = datetime.strptime(args.date, "%Y-%m-%d")

    # Set variables from environment
    usergroup_name = os.environ["USERGROUP_NAME"]

    # Instatiate the event handler
    event_handler = CalendarEventHandler(args.role, usergroup_name)

    # Retreive upcoming events
    events = event_handler.get_upcoming_events(date=args.date)

    if not events:
        logger.info("No events found")
        sys.exit()

    logger.info(f"{len(events)} events for {args.role.replace('-', ' ').title()} found")

    for event in events:
        event_handler.log_event_metadata(event)

    # Prompt for confirmation
    confirm = Confirm.ask("Delete all these events?", default=False)

    if confirm:
        # Delete the events
        for event in track(
            events,
            description=f"Deleting {args.role.replace('-', ' ').title()} events...",
        ):
            event_handler._delete_event(event["id"])
        logger.info("Event deletion completed")

    else:
        logger.info("Ok! Exiting without deleting anything")
        sys.exit()


if __name__ == "__main__":
    main()
