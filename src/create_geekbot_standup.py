"""
Functions to create Geekbot Standups in Slack to aid the transition of our Team Roles
through the Tech Team
"""
import argparse
import json
import os
from pathlib import Path

from loguru import logger
from requests import Session
from rich import print_json


class GeekbotStandup:
    """
    Manage Geekbot Standups in Slack for transitioning our Team Roles
    """

    def __init__(self):
        # Set variables
        self.geekbot_api_url = "https://api.geekbot.io"
        self.geekbot_api_key = os.environ["GEEKBOT_API_KEY"]

        try:
            self.CI_env = os.environ["CI"]
        except KeyError:
            self.CI_env = False

        # Open a Geekbot session
        self.geekbot_session = self._create_geekbot_session()

        # Set paths
        project_path = Path(__file__).parent.parent
        roles_path = project_path.joinpath("team-roles.json")

        # Check file exists before reading it
        if not os.path.exists(roles_path):
            raise FileNotFoundError(f"File must exist to continue! {roles_path}")

        # Read in team-roles.json
        with open(roles_path) as stream:
            self.roles = json.load(stream)

    def _create_geekbot_session(self):
        """Create a Session loaded with a Geekbot API key to make requests

        Returns:
            session obj: A session object loaded with an API key in its headers with
                permissions to interact with the Geekbot API
        """
        geekbot_session = Session()
        geekbot_session.headers.update({"Authorization": self.geekbot_api_key})
        return geekbot_session

    def _check_standup_exists(self):
        """Check if the standup already exists. Return it's ID if it does.

        Returns:
            int: ID of the existing standup
        """
        logger.info(f"Checking if standup exists: {self.standup_name}")

        response = self.geekbot_session.get(
            "/".join([self.geekbot_api_url, "v1", "standups"])
        )

        if not self.CI_env:
            print_json(data=response.json())

        response.raise_for_status()

        standup = next(
            (x for x in response.json() if x["name"] == self.standup_name), None
        )
        self.standup_exists = bool(standup)

        if self.standup_exists:
            logger.info("Standup exists!")
            return standup["id"]
        else:
            logger.info("Standup doesn't exist...")
            return None

    def _generate_standup_metadata(self):
        """Generate metadata for a new Geekbot standup. This includes information such as:
        when the standup happens, who will participate in the standup, and which slack
        channel the result will be broadcast to.

        Returns:
            dict: The metadata required to describe a new Geekbot standup
        """
        logger.info(f"Generating metadata for standup: {self.standup_name}")

        metadata = {
            "wait_time": 10,
            "users": [self.roles["id"]]
            if self.roles["id"] == self.standup_manager["id"]
            else [self.roles["id"], self.standup_manager["id"]],
            "sync_channel_members": False,
            "personalized": False,
        }

        if not self.standup_exists:
            metadata["name"] = self.standup_name
            metadata["channel"] = self.broadcast_channel
            metadata["time"] = "10:00:00"
            metadata["timezone"] = "user_local"
            metadata["days"] = [self.standup_day]

        return metadata

    def _generate_question_meeting_facilitator(self):
        """Generate the question that will be asked of the the new Meeting Facilitator
        in the standup. It will be added to the metadata generated in
        _generate_standup_metadata.

        Returns:
            str: The question to be posed to the new Meeting Facilitator
        """
        logger.info(f"Generating question for standup: {self.standup_name}")

        question = (
            f"{self.roles['name'].split()[0]} - it is your turn to facilitate this month's team meeting! "
            + "You can check the team calendar for when this month's meeting is scheduled for here:\n"
            + "https://calendar.google.com/calendar/embed?src=c_4hjjouojd8psql9i1a8nd1uff4%40group.calendar.google.com"
            + "\n\n"
            + "Reply 'ok' to this message to acknowledge your role. "
            + "Or if you are not able to fulfil this role at this time, please arrange cover with another member of the Tech Team."
            + "\n\n"
            + "Here are some actions the meeting facilitator is expected to take:\n"
            + ":white_check_mark: Collect and add agenda items to the meeting hackmd (link is in the calendar event)\n"
            + ":white_check_mark: Facilitate the meeting\n"
            + ":white_check_mark: Open up any follow-up issues or discussions and link to the hackmd\n"
            + ":white_check_mark: Transfer notes from the hackmd into the Team Compass"
        )
        return question

    def _generate_question_support_steward(self):
        """Generate the question that will be asked of the the new Support Steward
        in the standup. It will be added to the metadata generated in
        _generate_standup_metadata.

        Returns:
            str: The question to be posed to the new Support Steward
        """
        logger.info(f"Generating question for standup: {self.standup_name}")

        question = (
            f"{self.roles['name'].split()[0]} - it is your turn to be the support steward! "
            + "Please make sure to watch for any incoming tickets here:\n\n"
            + "https://2i2c.freshdesk.com/a/tickets/filters/all_tickets"
            + "\n\n"
            + "Reply 'ok' to this message to acknowledge your role. "
            + "Or if you are going to be away for a large part of your stewardship, please arrange cover with another member of the Tech Team."
            + "\n\n"
            + f"Your support steward buddy is: {self.steward_buddy.split()[0]}"
        )
        return question

    def create_meeting_facilitator_standup(self):
        """
        Create a Geekbot Standup to transition the Meeting Facilitator role
        """
        # Set variables
        self.standup_name = "MeetingFacilitatorStandup"
        self.standup_day = "Mon"
        self.broadcast_channel = "#team-updates"
        self.standup_manager = self.roles["standup_manager"]
        self.roles = self.roles["meeting_facilitator"]

        # First, check if a standup exists
        standup_id = self._check_standup_exists()

        # Generate metadata for the standup
        metadata = self._generate_standup_metadata()

        # Generate the standup question
        question = self._generate_question_meeting_facilitator()
        metadata["questions"] = [{"question": question}]

        if self.standup_exists:
            # Update the existing standup
            logger.info(f"Updating the existing standup: {self.standup_name}")
            response = self.geekbot_session.patch(
                "/".join([self.geekbot_api_url, "v1", "standups", str(standup_id)]),
                json=metadata,
            )
        else:
            # Create the standup
            logger.info(f"Creating a new standup: {self.standup_name}")
            response = self.geekbot_session.post(
                "/".join([self.geekbot_api_url, "v1", "standups"]), json=metadata
            )
            logger.info(
                f"This standup will be set to run **Weekly** on {self.standup_day}. "
                + "Please edit the standup manually in the dashboard if you require a period other than Weekly."
            )

        if not self.CI_env:
            print_json(data=response.json())

        response.raise_for_status()

    def create_support_steward_standup(self):
        """
        Create a Geekbot standup to transition the Support Steward role
        """
        # Set variables
        self.standup_name = "SupportStewardStandup"
        self.standup_day = "Wed"
        self.broadcast_channel = "#support-freshdesk"
        self.standup_manager = self.roles["standup_manager"]
        self.steward_buddy = self.roles["support_steward"]["current"]["name"]
        self.roles = self.roles["support_steward"]["incoming"]

        # First, check if a standup exists
        standup_id = self._check_standup_exists()

        # Generate metadata for the standup
        metadata = self._generate_standup_metadata()

        # Generate the standup question
        question = self._generate_question_support_steward()
        metadata["questions"] = [{"question": question}]

        if self.standup_exists:
            # Update the existing standup
            logger.info(f"Updating the existing standup: {self.standup_name}")
            response = self.geekbot_session.patch(
                "/".join([self.geekbot_api_url, "v1", "standups", str(standup_id)]),
                json=metadata,
            )
        else:
            # Create the standup
            logger.info(f"Creating a new standup: {self.standup_name}")
            response = self.geekbot_session.post(
                "/".join([self.geekbot_api_url, "v1", "standups"]), json=metadata
            )
            logger.info(
                f"This standup will be set to run **Weekly** on {self.standup_day}. "
                + "Please edit the standup manually in the dashboard if you require a period other than Weekly."
            )

        if not self.CI_env:
            print_json(data=response.json())

        response.raise_for_status()


def main():
    # Create a command line parser
    parser = argparse.ArgumentParser(
        description="""
            Create Geekbot standup apps to manage the transition of Team Roles through the Tech Team
        """
    )
    subparser = parser.add_subparsers(
        required=True, dest="command", help="Available commands"
    )

    meeting_facilitator_parser = subparser.add_parser(
        "meeting-facilitator",
        help="Create a Geekbot standup to transition the Meeting Facilitator role",
    )
    support_steward_parser = subparser.add_parser(
        "support-steward",
        help="Create a Geekbot standup to transition the Support Steward role",
    )

    args = parser.parse_args()

    # Instantiate the Geekbot Standup class
    standup = GeekbotStandup()

    # Create a standup for the chosen role
    if args.command == "meeting-facilitator":
        standup.create_meeting_facilitator_standup()
    elif args.command == "support-steward":
        standup.create_support_steward_standup()


if __name__ == "__main__":
    main()
