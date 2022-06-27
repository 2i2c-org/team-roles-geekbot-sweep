"""
Functions that iterate through a list of team members in order to transition our roles
"""
import argparse
import datetime
import json
import os
from pathlib import Path

from loguru import logger

from ..calendar.gcal_api_auth import GoogleCalendarAPI
from .get_slack_team_members import SlackTeamMembers


class TeamRoles:
    """Iterate our Team Roles through the Tech Team"""

    def __init__(self):
        self.calendar_id = os.environ["CALENDAR_ID"]

        # Instatiate the SlackTeamMembers class
        self.slack = SlackTeamMembers()

        # Instatiate the GoogleCalendarAPI class
        self.gcal_api = GoogleCalendarAPI().authenticate()

        # Read in who is serving in which role from a JSON file
        project_path = Path(__file__).parent.parent.parent
        self.roles_path = project_path.joinpath("team-roles.json")

        # Check the file exists before reading
        if not os.path.exists(self.roles_path):
            raise FileNotFoundError(f"File must exist to continue! {self.roles_path}")

        with open(self.roles_path) as stream:
            self.team_roles = json.load(stream)

    def _check_managers_id_is_set(self):
        """
        Check that the team member allocated as the standup manager has an ID set
        """
        logger.info("Checking the standup manager has an ID set")

        if (self.team_roles["standup_manager"].get("id") is None) or (
            self.team_roles["standup_manager"]["id"] == ""
        ):
            self.team_roles["standup_manager"]["id"] = self.team_members[
                self.team_roles["standup_manager"]["name"]
            ]

    def _find_current_team_member(self, role):
        """Find the current team member serving in a role. Pull the upcoming events from
        the calendar and scrape the current team member serving in that role from
        the title. Fall back onto the entries in team-roles.json if no calendar
        events are available.

        Args:
            role (str): The role to find the current team member for. Either
                'meeting-facilitator' or 'support-steward'.

        Returns:
            current_team_member (str): The name of the team member currently
                serving in the defined role
        """
        # Format the role to match an event title
        formatted_role = " ".join(role.split("-")).title()

        # Find the current datetime
        now = datetime.datetime.utcnow().isoformat() + "Z"

        # Find the 5 upcoming events on a calendar
        events_results = (
            self.gcal_api.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=now,
                maxResults=5,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_results.get("items", [])

        # Filter the events for those that match the specified role
        events = [event for event in events if formatted_role in event["summary"]]

        # Return the current event <- definition of 'current' depends on which role
        # is specified ;-)
        if role == "meeting-facilitator":
            try:
                current_event = events[0]
            except IndexError:
                current_event = None

        elif role == "support-steward":
            try:
                current_event = events[1]
            except IndexError:
                current_event = None

        if current_event is None:
            # If no current event is found, fallback onto what is set in team-roles.json
            if role == "meeting-facilitator":
                current_team_member = self.team_roles["meeting_facilitator"]["name"]
            elif role == "support_steward":
                current_team_member = self.team_roles["support_steward"]["current"][
                    "name"
                ]

        else:
            # Extract the current team member from the event title
            current_team_member = current_event["summary"].split(":")[-1].strip()

        return current_team_member

    def _find_next_team_member(self, current_team_member):
        """Based on who is currently serving in a role, work out who is next in line

        Args:
            current_team_member (str): Current team member in a role

        Returns:
            tuple(str, str): The next team member to serve in the role. Returns a tuple
                of (users_name, users_id)
        """
        index = next(
            (
                i
                for (i, name) in enumerate(self.team_members.keys())
                if current_team_member in name
            ),
            None,
        )

        # If we reach the end of the list, we want to wrap around and start again
        if len(self.team_members) == (index + 1):
            index = -1

        return list(self.team_members.items())[index + 1]

    def _update_meeting_facilitator_role(self, current_team_member):
        """Iterate the Meeting Facilitator role through the team"""
        logger.info("Finding the next team member in the meeting facilitator role")

        # Work out who is next
        next_member_name, next_member_id = self._find_next_team_member(
            current_team_member
        )

        # Overwrite the meeting facilitator with the next team member
        self.team_roles["meeting_facilitator"]["name"] = next_member_name
        self.team_roles["meeting_facilitator"]["id"] = next_member_id

    def _update_support_steward_role(self, current_team_member):
        """Iterate the Support Steward role through the team"""
        logger.info("Finding the next team member in the support steward role")

        # The incoming team member becomes the current team member
        self.team_roles["support_steward"]["current"]["name"] = self.team_roles[
            "support_steward"
        ]["incoming"]["name"]
        self.team_roles["support_steward"]["current"]["id"] = self.team_roles[
            "support_steward"
        ]["incoming"]["id"]

        # Work out who is next
        next_member_name, next_member_id = self._find_next_team_member(
            current_team_member
        )

        # The next team member is assigned to "incoming"
        self.team_roles["support_steward"]["incoming"]["name"] = next_member_name
        self.team_roles["support_steward"]["incoming"]["id"] = next_member_id

    def update_roles(self, role):
        """Update our Team Roles by iterating through members of the Tech Team

        Args:
            role (str): The role to update. Either 'meeting-facilitator' or
                'support-steward'.
        """
        # Populate team members
        self.team_members = self.slack.get_users_in_team()

        # Check the info for the standup manager is complete
        self._check_managers_id_is_set()

        # Find the team member currently serving in a role
        current_team_member = self._find_current_team_member(role)

        if role == "meeting-facilitator":
            logger.info("Updating the Meeting Facilitator role")
            self._update_meeting_facilitator_role(current_team_member)
        elif role == "support-steward":
            logger.info("Updating the Support Steward role")
            self._update_support_steward_role(current_team_member)

        # Write the updated roles to a JSON file
        logger.info("Writing roles to team-roles.json")
        with open(self.roles_path, "w") as f:
            json.dump(self.team_roles, f, indent=4, sort_keys=False)


def main():
    # Construct a command line parser
    parser = argparse.ArgumentParser(
        description="Update our Team Roles by iterating through members of the Tech Team"
    )
    parser.add_argument(
        "role",
        choices=["meeting-facilitator", "support-steward"],
        help="The role to update",
    )
    args = parser.parse_args()

    TeamRoles().update_roles(role=args.role)


if __name__ == "__main__":
    main()
