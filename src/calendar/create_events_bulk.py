"""
Create Team Role Events in a Calendar in bulk
"""
import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger
from rich.progress import track
from rich.prompt import Confirm

from .event_handling import ROLE_CYCLES, CalendarEventHandler


class MutuallyInclusiveArgumentError(Exception):
    pass


def adjust_reference_date(reference_date):
    """The Support Steward Role is transferred on Wednesdays. We adjust the reference
    date to be the next Wednesday from the given date for the calculations.

    Args:
        reference_date (date obj): The date to be adjusted

    Returns:
        reference_date (date obj): The adjusted date
    """
    # isoweekday() returns an integer representation of the day of the week where
    # MONDAY is 1 and SUNDAY is 7. Hence, WEDNESDAY is 3.
    weekday_num = reference_date.isoweekday()

    if weekday_num < 3:
        reference_date = reference_date + timedelta(days=(3 - weekday_num))
    elif weekday_num > 3:
        reference_date = reference_date + timedelta(days=(7 + (3 - weekday_num)))

    logger.info(
        "Adjusting reference date for Support Steward role to: {}",
        reference_date.strftime("%Y-%m-%d"),
    )

    return reference_date


def read_team_roles_from_file(role):
    """If a team member cannot be read from a calendar event, and one hasn't been
    provided via the command line, we fall back onto reading the team member from
    the team-roles.json file.

    Args:
        role (str): The role we are interested in learning about. Can be either
            'meeting-facilitator' or 'support-steward'.

    Raises:
        FileNotFoundError: If the file does not exist at the expected location,
            immediately exit the script

    Returns:
        str: The team member currently serving in the specified role
    """
    # Set filepaths
    project_path = Path(__file__).parent.parent.parent
    roles_path = project_path.joinpath("team-roles.json")

    # Check the team roles file exists before reading
    if not os.path.exists(roles_path):
        raise FileNotFoundError(f"File must exist to continue! {roles_path}")

    with open(roles_path) as stream:
        team_roles = json.load(stream)

    if role == "meeting-facilitator":
        member = team_roles[role.replace("-", "_")]["name"]
    elif role == "support-steward":
        member = team_roles[role.replace("-", "_")]["current"]["name"]

    return member


def create_bulk_events(role, n_events=None, ref_date=None, member=None):
    """Create role events in bulk in the Team Roles Calendar

    Args:
        role (str): The role we want to create events for
        n_events (int, optional): The number of events to create. Defaults to None
            and extracts a set value from the ROLE_CYCLES dictionary.
        ref_date (date obj, optional): A reference date to begin creating events from.
            Defaults to None.
        member (str, optional): The team member currently serving in the specified role.
            Defaults to None.
    """
    # Set variables from the environment
    usergroup_name = os.environ["USERGROUP_NAME"]

    # Set the number of events to create if not specified
    if n_events is None:
        n_events = ROLE_CYCLES[role]["n_events"]

    if ref_date is not None:
        ref_date = datetime.strptime(ref_date, "%Y-%m-%d")
        if role == "support-steward":
            ref_date = adjust_reference_date(ref_date)

    # Instantiate the event handler
    event_handler = CalendarEventHandler(role, usergroup_name)

    logger.info("Generating new event metadata...")

    # Get existing events from the calendar
    ext_events = []  # event_handler._get_upcoming_events()
    if ext_events:
        events = []
        for i in range(n_events):
            events.append(
                event_handler.calculate_next_event_data(offset=i, suppress_logs=True)
            )
    else:
        if member is None:
            # Read in team-roles.json file
            logger.warning(
                "There are no previous events found in the calendar and a team member has not been provided. "
                "I will pull the name of the current team member from the team-roles.json file. "
                "Double check the generated events before creating them! "
                "If you don't want to create the suggested events, exit the script and rerun setting the --date [-d] and --team-member [-m] flags."
            )
            member = read_team_roles_from_file(role)

            logger.warning(f"Current team member set to: {member}")

        if ref_date is None:
            ref_date = datetime.today()

            if role == "meeting-facilitator":
                ref_date = ref_date.replace(month=ref_date.month + 1)
                ref_date = ref_date.replace(day=1)
            elif role == "support-steward":
                ref_date = adjust_reference_date(ref_date)

            logger.warning(
                "There are no previous events found in the calendar and a reference date has not been provided. "
                f"I will set a reference date of {ref_date.strftime('%Y-%m-%d')}. "
                "Double check the generated events before creating them! "
                "If you don't want to create the suggested events, exit the script and rerun setting the --date [-d] and --team-member [-m] flags."
            )

        events = []
        for i in range(n_events):
            events.append(
                event_handler.calculate_next_event_data(
                    ref_date=ref_date, member=member, offset=i, suppress_logs=True
                )
            )

    for event in events:
        print(f"{event['start']['date']} -> {event['end']['date']}: {event['summary']}")

    confirm = Confirm.ask("Create these events?", default=False)

    if confirm:
        for event in track(events, description="Creating calendar events..."):
            event_handler.create_event(event)
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
        "-n",
        "--n-events",
        type=int,
        default=None,
        help=(
            "The number of role events to create. "
            "Defaults to 12 for Meeting Facilitator and 26 for Support Steward (both 1 year's worth)."
        ),
    )
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        default=None,
        help=(
            "A reference date to begin creating events from. "
            "Defaults to appending events from the last in the series, or TODAY if no events exist. "
            "WARNING: EXPERIMENTAL FEATURE. "
            "This flag is MUTUALLY INCLUSIVE with --team-member [-m]."
        ),
    )
    parser.add_argument(
        "-m",
        "--team-member",
        type=str,
        default=None,
        help=(
            "The name of the team member currently serving in the role. "
            "Defaults to being pulled from either the last calendar event, or team-roles.json if a calendar event doesn't not exist. "
            "This flag is MUTUALLY INCLUSIVE with --date [-d]."
        ),
    )

    args = parser.parse_args()

    if (args.date is not None and args.team_member is None) or (
        args.date is None and args.team_member is not None
    ):
        raise MutuallyInclusiveArgumentError(
            "Both --team-member and --date options must be provided"
        )

    create_bulk_events(
        args.role,
        n_events=args.n_events,
        ref_date=args.date,
        member=args.team_member,
    )


if __name__ == "__main__":
    main()
