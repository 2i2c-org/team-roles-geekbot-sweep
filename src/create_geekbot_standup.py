import os
import json
import argparse
from requests import Session
from pathlib import Path
from rich import print_json


class GeekbotStandup:
    def __init__(self):
        # Set variables
        self.geekbot_api_url = "https://api.geekbot.io"
        self.geekbot_api_key = os.environ["GEEKBOT_API_KEY"]

        # Open a Geekbot session
        self.geekbot_session = self._create_geekbot_session()

        # Set paths
        project_path = Path(__file__).parent.parent
        roles_path = project_path.joinpath("team-roles.json")

        # Check file exists before reading it
        if not os.path.exists(roles_path):
            raise FileNotFoundError(
                f"File must exist to continue! {roles_path}"
            )

        # Read in team-roles.json
        with open(roles_path, "r") as stream:
            self.roles = json.load(stream)

    def _create_geekbot_session(self):
        geekbot_session = Session()
        geekbot_session.headers.update({"Authorization": self.geekbot_api_key})
        return geekbot_session

    def _get_standup(self):
        response = self.geekbot_session.get("/".join([self.geekbot_api_url, "v1", "standups"]))
        response.raise_for_status()
        return next(x for x in response.json() if x["name"] == self.standup_name)

    def _delete_previous_standup(self):
        standup = self._get_standup()
        response = self.geekbot_session.delete("/".join([self.geekbot_api_url, "v1", "standups", standup["id"]]))
        print_json(data=response.json())
        response.raise_for_status()

    def _generate_standup_metadata(self):
        metadata = {
            "name": self.standup_name,
            "channel": self.broadcast_channel,
            "time": "10:00:00",
            "timezone": "",  # By leaving this blank it will trigger in user's timezone
            "wait_time": 10,
            "days": [self.standup_day],
            "users": [self.roles["incoming"]["id"]],
            "sync_channel_members": False,
            "personalized": False,
        }
        return metadata

    def _generate_question_meeting_facilitator(self):
        question = """
        It is your turn to facilitate this month's team meeting! You can check the team
        calendar for when this month's meeting is scheduled for here:
        https://calendar.google.com/calendar/embed?src=c_4hjjouojd8psql9i1a8nd1uff4%%40group.calendar.google.com
        Reply 'ok' to this message to acknowledge your role. If you are not able to
        fulfil this role at this time, please arrange cover with a member of the Tech Team.
        """
        return question

    def _generate_question_support_steward(self):
        question = """
        It is your turn to be the support steward! Please make sure to watch fir any
        incoming tickets at https://2i2c.freshdesk.com/a/tickets/filters/all_tickets
        If you are going to be away for a large part or your stewardship, please
        arrange cover with a member of the Tech Team.
        Reply 'ok' to this message to acknowledge your role.
        """
        return question

    def create_meeting_facilitator_standup(self):
        # Set variables
        self.standup_name = "MeetingFacilitatorStandup"
        self.standup_day = "Mon"
        self.broadcast_channel = "#team-updates"
        self.roles = self.roles["meeting_facilitator"]

        # First, delete previous standup
        self._delete_previous_standup()

        # Generate metadata for the standup
        metadata = self._generate_standup_metadata()

        # Generate the standup question
        question = self._generate_question_meeting_facilitator()
        metadata["questions"] = [{"question": question}]

        # Create the standup
        response = self.geekbot_session.post(
            "/".join([self.geekbot_api_url, "v1", "standups"]), json=metadata
        )
        print_json(data=response.json())
        response.raise_for_status()

    def create_support_steward_standup(self):
        # Set variables
        self.standup_name = "SupportStewardStandup"
        self.standup_day = "Wed"
        self.broadcast_channel = "#support-freshdesk"
        self.roles = self.roles["support_steward"]

        # First, delete previous standup
        self._delete_previous_standup()

        # Generate metadata for the standup
        metadata = self._generate_standup_metadata()

        # Generate the standup question
        question = self._generate_question_support_steward()
        metadata["questions"] = [{"question": question}]

        # Create the standup
        response = self.geekbot_session.post(
            "/".join([self.geekbot_api_url, "v1", "standups"]), json=metadata
        )
        print_json(data=response.json())
        response.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(required=True, dest="command")

    meeting_facilitator_parser = subparser.add_parser("create-meeting-facilitator-standup")
    support_steward_parser = subparser.add_parser("create-support-steward-standup")

    args = parser.parse_args()

    standup = GeekbotStandup()

    if args.command == "create-meeting-facilitator-standup":
        standup.create_meeting_facilitator_standup()
    elif args.command == "create-support-steward-standup":
        standup.create_support_steward_standup()


if __name__ == "__main__":
    main()
