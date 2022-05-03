import json
import os
from pathlib import Path

from get_slack_team_members import SlackTeamMembers


class TeamRoles:
    def __init__(self):
        # Instatiate the SlackTeamMembers class
        self.slack_team_members = SlackTeamMembers()

        # Read in who is serving in which role from a JSON file
        project_path = Path(__file__).parent.parent
        self.roles_path = project_path.joinpath("team-roles.json")

        # Check the file exists before reading
        if not os.path.exists(self.roles_path):
            raise FileNotFoundError(f"File must exist to continue! {self.roles_path}")

        with open(self.roles_path) as stream:
            self.team_roles = json.load(stream)

    def _find_next_team_member(self, current_member):
        team_members_dict = self.slack_team_members.get_users_in_team()

        index = next(
            idx
            for (idx, team_member) in enumerate(team_members_dict.keys())
            if team_member == current_member
        )

        # If we reach the end of the list, we want to wrap around and start again
        if len(team_members_dict) == (index + 1):
            index = -1

        return list(team_members_dict.keys())[index + 1]

    def _update_meeting_facilitator_role(self):
        self.team_roles["meeting_facilitator"]["outgoing"] = self.team_roles[
            "meeting_facilitator"
        ]["incoming"]
        self.team_roles["meeting_facilitator"][
            "incoming"
        ] = self._find_next_team_member(
            self.team_roles["meeting_facilitator"]["outgoing"]
        )

    def _update_support_steward_role(self):
        self.team_roles["support_steward"]["outgoing"] = self.team_roles[
            "support_steward"
        ]["current"]
        self.team_roles["support_steward"]["current"] = self.team_roles[
            "support_steward"
        ]["incoming"]
        self.team_roles["support_steward"]["incoming"] = self._find_next_team_member(
            self.team_roles["support_steward"]["current"]
        )

    def update_roles(
        self, update_meeting_facilitator=False, update_support_steward=False
    ):
        if update_meeting_facilitator:
            self._update_meeting_facilitator_role()

        if update_support_steward:
            self._update_support_steward_role()

        with open(self.roles_path, "w") as f:
            json.dump(self.team_roles, f)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--update-meeting-facilitator", action="store_true")
    parser.add_argument("--update-support-steward", action="store_true")

    args = parser.parse_args()

    roles = TeamRoles()
    roles.update_roles(
        update_meeting_facilitator=args.update_meeting_facilitator,
        update_support_steward=args.update_support_steward,
    )
