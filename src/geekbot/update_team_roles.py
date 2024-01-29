"""
Functions that iterate through a list of team members in order to transition our roles
"""

import argparse
import json
import os
from pathlib import Path

from loguru import logger

from ..calendar.event_handling import CalendarEventHandler


class TeamRoles:
    """Iterate our Team Roles through 2i2c team members"""

    def __init__(self, role):
        self.role = role
        usergroup_name = os.environ["USERGROUP_NAME"]

        # Read in who is serving in which role from a JSON file
        project_path = Path(__file__).parent.parent.parent
        self.roles_path = project_path.joinpath("team-roles.json")

        # Check the team roles file exists before reading
        if not os.path.exists(self.roles_path):
            raise FileNotFoundError(f"File must exist to continue! {self.roles_path}")

        with open(self.roles_path) as stream:
            self.team_roles = json.load(stream)

        # Instatiate the event handler
        self.event_handler = CalendarEventHandler(role, usergroup_name)

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
            self.team_roles["standup_manager"]["id"] = (
                self.event_handler.usergroup_dict[
                    self.team_roles["standup_manager"]["name"]
                ]
            )

    def _update_meeting_facilitator_role(self, next_member_name):
        """Update the Meeting Facilitator role metadata"""
        # Find the ID of the next Meeting Facilitator
        next_member_id = next(
            (
                id
                for (name, id) in self.event_handler.usergroup_dict.items()
                if next_member_name.lower() in name.lower()
            ),
            None,
        )

        # Overwrite the meeting facilitator with the next team member
        self.team_roles["meeting_facilitator"]["name"] = next_member_name.split(" ")[0]
        self.team_roles["meeting_facilitator"]["id"] = next_member_id

    def _update_support_triager_role(self, next_member_name):
        """Update the Support Triager role metadata"""
        # The incoming team member becomes the current team member
        self.team_roles["support_triager"]["current"]["name"] = self.team_roles[
            "support_triager"
        ]["incoming"]["name"]
        self.team_roles["support_triager"]["current"]["id"] = self.team_roles[
            "support_triager"
        ]["incoming"]["id"]

        # Find the ID of the next Support Triager
        next_member_id = next(
            (
                id
                for (name, id) in self.event_handler.usergroup_dict.items()
                if next_member_name.lower() in name.lower()
            ),
            None,
        )

        # The next team member is assigned to "incoming"
        self.team_roles["support_triager"]["incoming"]["name"] = next_member_name.split(
            " "
        )[0]
        self.team_roles["support_triager"]["incoming"]["id"] = next_member_id

    def update_roles(self):
        """Update our Team Roles by inspecting a Google Calendar and/or iterating
        through 2i2c team members
        """
        # Find the current team member and next team member to serve in a role
        next_member = self.event_handler.find_next_team_member_from_calendar()

        if next_member is None:
            logger.warning(
                "Couldn't extract the next team member from the calendar. "
                "Falling back onto iteration."
            )
            _, current_member = self.event_handler.get_first_event()
            next_member = self.event_handler._find_next_team_member_manually(
                current_member
            )

        logger.info(f"Next {' '.join(self.role.split('-')).title()}: {next_member}")

        if self.role == "meeting-facilitator":
            logger.info("Updating the Meeting Facilitator role")
            self._update_meeting_facilitator_role(next_member)
        elif self.role == "support-triager":
            logger.info("Updating the Support Triager role")
            self._update_support_triager_role(next_member)

        # Write the updated roles to a JSON file
        logger.info("Writing roles to team-roles.json")
        with open(self.roles_path, "w") as f:
            json.dump(self.team_roles, f, indent=4, sort_keys=False)


def main():
    # Construct a command line parser
    parser = argparse.ArgumentParser(
        description="Update our Team Roles by iterating through 2i2c team members"
    )
    parser.add_argument(
        "role",
        choices=["meeting-facilitator", "support-triager"],
        help="The role to update",
    )
    args = parser.parse_args()

    TeamRoles(role=args.role).update_roles()


if __name__ == "__main__":
    main()
