"""
Function to populate team-roles.json with the current team members serving in our Team Roles
"""
import json
import os
from pathlib import Path

from .get_slack_team_members import SlackTeamMembers


def main():
    # Set paths
    project_path = Path(__file__).parent.parent.parent
    roles_path = project_path.joinpath("team-roles.json")

    # Check the file exists before continuing
    if not os.path.exists(roles_path):
        raise FileNotFoundError(f"File must exist to continue! {roles_path}")

    # Set environment variables
    current_meeting_facilitator = os.environ["CURRENT_MEETING_FACILITATOR"]
    current_support_steward = os.environ["CURRENT_SUPPORT_STEWARD"]
    incoming_support_steward = os.environ["INCOMING_SUPPORT_STEWARD"]
    standup_manager = os.environ["STANDUP_MANAGER"]

    # Instantiate SlackTeamMembers class
    slack = SlackTeamMembers()
    members = slack.get_users_in_team()

    # Write team roles dict
    team_roles = {
        "standup_manager": {
            "name": standup_manager,
            "id": members[standup_manager],
        },
        "meeting_facilitator": {
            "name": current_meeting_facilitator,
            "id": members[current_meeting_facilitator],
        },
        "support_steward": {
            "incoming": {
                "name": incoming_support_steward,
                "id": members[incoming_support_steward],
            },
            "current": {
                "name": current_support_steward,
                "id": members[current_support_steward],
            },
        },
    }

    with open(roles_path, "w") as f:
        json.dump(team_roles, f, indent=4, sort_keys=False)
