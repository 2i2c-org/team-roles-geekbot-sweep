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

        # Populate team members
        self.team_members = SlackTeamMembers().get_users_in_team()

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

        # Check the info for the standup manager is complete
        self._check_managers_id_is_set()

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

    def _find_next_team_member(self, current_member):
        """Based on who is currently serving in a role, work out who is next in line

        Args:
            current_member (str): Current team member in a role

        Returns:
            str: The next team member to serve in the role
        """
        index = next(
            (
                i
                for (i, name) in enumerate(self.team_members.keys())
                if current_member in name
            ),
            None,
        )

        # If we reach the end of the list, we want to wrap around and start again
        if len(self.team_members) == (index + 1):
            index = -1

        return list(self.team_members.keys())[index + 1]

    def _ensure_team_members_are_not_none(self, role, current_member, next_member):
        """If there are no events in the Google Calendar, _find_team_members will set
        current_member and/or next_member to None. If that is the case, this function
        will get those names from the team-roles.json file.

        Args:
            role (str): The role we are inspecting. Either 'meeting-facilitator' or
                'support-steward'.
            current_member (str): Either the name of the current team member serving in
                the specified role, or None.
            next_member (_type_):Either the name of the next team member serving in
                the specified role, or None.

        Returns:
            tuple(str, str): The names of the current and next team members to serve in
                the specified role, as extracted from the team-roles.json file
        """
        if current_member is None:
            if role == "meeting-facilitator":
                current_member = self.team_roles["meeting_facilitator"]["name"]
            elif role == "support-steward":
                current_member = self.team_roles["support_steward"]["incoming"]["name"]

        if next_member is None:
            next_member = self._find_next_team_member(current_member)[0]

        return current_member, next_member

    def _find_team_members(self, role):
        """Find the current and next team members serving in a role by inspecting the
        events in a Google Calendar.

        Args:
            role (str): The role to find the team members for. Either
                'meeting-facilitator' or 'support-steward'.

        Returns:
            tuple(str, str): The names of the current and next team members to serve in
                the specified role
        """
        # Find the  upcoming events on a calendar. We use 7 here since we want at least 2 Meeting Facilitator events
        # and 3 Support Steward events. So 7 gives us some leeway.
        events_results = (
            self.gcal_api.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=datetime.datetime.utcnow().isoformat() + "Z",
                maxResults=7,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_results.get("items", [])

        # Filter the events for those that match the specified role
        formatted_role = " ".join(role.split("-")).title()
        events = [event for event in events if formatted_role in event["summary"]]

        # Extract team members names from the event summary. If an event doesn't exist,
        # set variables to None.
        if role == "meeting-facilitator":
            try:
                current_member = events[0]["summary"].split(":")[-1].strip()
            except IndexError:
                current_member = None

            try:
                next_member = events[1]["summary"].split(":")[-1].strip()
            except IndexError:
                next_member = None

        elif role == "support-steward":
            # For the Support Steward, we use the 1 and 2 indexed events, instead of 0 and 1, since
            # team members in this role overlap with one another
            try:
                current_member = events[1]["summary"].split(":")[-1].strip()
            except IndexError:
                current_member = None

            try:
                next_member = events[2]["summary"].split(":")[-1].strip()
            except IndexError:
                next_member = None

        # We don't want these variables to be set to None. If not extracted from the
        # calendar, extract them from the team-roles.json file.
        current_member, next_member = self._ensure_team_members_are_not_none(
            role, current_member, next_member
        )

        return current_member, next_member

    def _update_meeting_facilitator_role(self, next_member_name):
        """Update the Meeting Facilitator role metadata"""
        # Find the ID of the next Meeting Facilitator
        next_member_id = next(
            (
                id
                for (name, id) in self.team_members.items()
                if next_member_name in name
            ),
            None,
        )

        # Overwrite the meeting facilitator with the next team member
        self.team_roles["meeting_facilitator"]["name"] = next_member_name
        self.team_roles["meeting_facilitator"]["id"] = next_member_id

    def _update_support_steward_role(self, next_member_name):
        """Update the Support Steward role metadata"""
        # The incoming team member becomes the current team member
        self.team_roles["support_steward"]["current"]["name"] = self.team_roles[
            "support_steward"
        ]["incoming"]["name"]
        self.team_roles["support_steward"]["current"]["id"] = self.team_roles[
            "support_steward"
        ]["incoming"]["id"]

        # Find the ID of the next Support Steward
        next_member_id = next(
            (
                id
                for (name, id) in self.team_members.items()
                if next_member_name in name
            ),
            None,
        )

        # The next team member is assigned to "incoming"
        self.team_roles["support_steward"]["incoming"]["name"] = next_member_name
        self.team_roles["support_steward"]["incoming"]["id"] = next_member_id

    def update_roles(self, role):
        """Update our Team Roles by inspecting a Google Calendar and/or iterating
        through members of the Tech Team

        Args:
            role (str): The role to update. Either 'meeting-facilitator' or
                'support-steward'.
        """
        # Find the current team member and next team member to serve in a role
        current_member, next_member = self._find_team_members(role)
        logger.info(
            f"\nCurrent {' '.join(role.split('-')).title()}: {current_member}"
            + f"\nNext {' '.join(role.split('-')).title()}: {next_member}"
        )

        if role == "meeting-facilitator":
            logger.info("Updating the Meeting Facilitator role")
            self._update_meeting_facilitator_role(next_member)
        elif role == "support-steward":
            logger.info("Updating the Support Steward role")
            self._update_support_steward_role(next_member)

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
