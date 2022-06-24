"""
Functions that iterate through a list of team members in order to transition our roles
"""
import argparse
import json
import os
from pathlib import Path

from loguru import logger

from .get_slack_team_members import SlackTeamMembers


class TeamRoles:
    """
    Iterate our Team Roles through the Tech Team
    """

    def __init__(self):
        # Instatiate the SlackTeamMembers class
        self.slack = SlackTeamMembers()

        # Read in who is serving in which role from a JSON file
        project_path = Path(__file__).parent.parent
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

    def _find_next_team_member(self, current_member):
        """Based on who is currently serving in a role, work out who is next in line

        Args:
            current_member (str): Current team member in a role

        Returns:
            tuple(str, str): The next team member to serve in the role. Returns a tuple
                of (users_name, users_id)
        """
        index = next(
            idx
            for (idx, team_member) in enumerate(self.team_members.keys())
            if team_member == current_member
        )

        # If we reach the end of the list, we want to wrap around and start again
        if len(self.team_members) == (index + 1):
            index = -1

        return list(self.team_members.items())[index + 1]

    def _update_meeting_facilitator_role(self):
        """
        Iterate the Meeting Facilitator role through the team
        """
        logger.info("Finding the next team member in the meeting facilitator role")

        # Work out who is next
        next_member_name, next_member_id = self._find_next_team_member(
            self.team_roles["meeting_facilitator"]["name"]
        )

        # Overwrite the meeting facilitator with the next team member
        self.team_roles["meeting_facilitator"]["name"] = next_member_name
        self.team_roles["meeting_facilitator"]["id"] = next_member_id

    def _update_support_steward_role(self):
        """
        Iterate the Support Steward role through the team
        """
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
            self.team_roles["support_steward"]["current"]["name"]
        )

        # The next team member is assigned to "incoming"
        self.team_roles["support_steward"]["incoming"]["name"] = next_member_name
        self.team_roles["support_steward"]["incoming"]["id"] = next_member_id

    def update_roles(
        self, update_meeting_facilitator=False, update_support_steward=False
    ):
        """Update our Team Roles by iterating through members of the Tech Team

        Args:
            update_meeting_facilitator (bool, optional): If True, the Meeting Facilitator
                role will be updated. Defaults to False.
            update_support_steward (bool, optional): If True, the Support Steward role
                will be updated. Defaults to False.
        """
        # Populate team members
        self.team_members = self.slack.get_users_in_team()

        # Check the info for the standup manager is complete
        self._check_managers_id_is_set()

        if update_meeting_facilitator:
            logger.info("Updating the Meeting Facilitator role")
            self._update_meeting_facilitator_role()

        if update_support_steward:
            logger.info("Updating the Support Steward role")
            self._update_support_steward_role()

        # Write the updated roles to a JSON file
        logger.info("Writing roles to team-roles.json")
        with open(self.roles_path, "w") as f:
            json.dump(self.team_roles, f, indent=4, sort_keys=False)


def main():
    # Construct a command line parser
    parser = argparse.ArgumentParser(
        description="Update our Team Roles by iterating through members of the Tech Team"
    )
    subparser = parser.add_subparsers(
        required=True, dest="command", help="Available commands"
    )

    meeting_facilitator_parser = subparser.add_parser(
        "meeting-facilitator",
        help="Update the Meeting Facilitator role",
    )
    support_steward_parser = subparser.add_parser(
        "support-steward",
        help="Update the Support Steward role",
    )

    args = parser.parse_args()

    # Instantiate the TeamRoles class
    roles = TeamRoles()

    # Update the Team Roles
    if args.command == "meeting-facilitator":
        roles.update_roles(update_meeting_facilitator=True)
    elif args.command == "support-steward":
        roles.update_roles(update_support_steward=True)


if __name__ == "__main__":
    main()