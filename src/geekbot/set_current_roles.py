"""
Function to populate team-roles.json with the current team members serving in our Team Roles
"""
import json
import os
from pathlib import Path

from .get_slack_usergroup_members import SlackUsergroupMembers


def split_string_by_char(str_to_split, char_to_split_by=","):
    """Split a long string into a list of strings on a specified character.

    Args:
        str_to_split (str): The long string to split into a list of strings
        char_to_split_by (str, optional): The character to split str_to_split by.
            Defaults to "," (comma).
    """
    list_of_strs = str_to_split.split(char_to_split_by)

    # Ensure leading/trailing whitespace is
    for i, item in enumerate(list_of_strs):
        list_of_strs[i] = item.strip()

    return list_of_strs


def main():
    # Set paths
    project_path = Path(__file__).parent.parent.parent
    roles_path = project_path.joinpath("team-roles.json")

    # Check the file exists before continuing
    if not os.path.exists(roles_path):
        raise FileNotFoundError(f"File must exist to continue! {roles_path}")

    # Set environment variables
    current_support_steward = os.environ["CURRENT_SUPPORT_STEWARD"]
    incoming_support_steward = os.environ["INCOMING_SUPPORT_STEWARD"]
    standup_manager = os.environ["STANDUP_MANAGER"]
    current_meeting_facilitator = os.environ.get("CURRENT_MEETING_FACILITATOR", None)

    usergroups = os.environ["USERGROUP_NAMES"]
    usergroups = split_string_by_char(usergroups)

    # Instantiate SlackUsergroupMembers class
    slack = SlackUsergroupMembers()

    # Create an empty dictionary to store members of various teams in
    members = {}

    # Add the team members for each team to the dictionary
    for usergroup in usergroups:
        users = slack.get_users_in_usergroup(usergroup)
        members[usergroup] = users

    # Write team roles dict
    team_roles = {
        "standup_manager": {
            "name": standup_manager,
            "id": members["meeting-facilitators"][standup_manager],
        },
        "meeting_facilitator": {
            "name": current_meeting_facilitator,
            "id": None
            if current_meeting_facilitator is None
            else members["meeting-facilitators"][current_meeting_facilitator],
        },
        "support_steward": {
            "incoming": {
                "name": incoming_support_steward,
                "id": members["support-stewards"][incoming_support_steward],
            },
            "current": {
                "name": current_support_steward,
                "id": members["support-stewards"][current_support_steward],
            },
        },
    }

    with open(roles_path, "w") as f:
        json.dump(team_roles, f, indent=4, sort_keys=False)
