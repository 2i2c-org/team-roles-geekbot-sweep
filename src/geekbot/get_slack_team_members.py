"""
Functions to get Slack members who are in a given usergroup (or "team")
"""
import os
from collections import OrderedDict

from loguru import logger
from slack_sdk import WebClient


class SlackTeamMembers:
    """
    Find the members of a given Slack usergroup (colloquially known as a "team")
    """

    def __init__(self):
        # Instantiate a SLACK API client
        self.client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

    def _get_team_id(self, team_name):
        """
        Retrieve the ID of a given Slack team
        """
        logger.info(f"Retrieving ID for Slack team: {team_name}")

        # Get all usergroups in workspace
        response = self.client.api_call(api_method="usergroups.list")

        # Find ID for the team_name usergroup
        index = next(
            idx
            for (idx, usergroup) in enumerate(response["usergroups"])
            if usergroup["handle"] == team_name
        )
        self.usergroup_id = response["usergroups"][index]["id"]

    def _get_user_ids(self, team_name):
        """
        Retrieve the user IDs of the members of a given usergroup
        """
        self._get_team_id(team_name=team_name)

        logger.info(f"Retrieving user IDs for members of Slack team: {team_name}")

        # Find all user IDs in the team_name usergroup
        response = self.client.api_call(
            api_method="usergroups.users.list",
            params={"usergroup": self.usergroup_id},
        )
        self.user_ids = response["users"]

    def _convert_user_id_to_handle(self, user_id):
        """For a given user ID, retrieve their 'real name', or display name if available

        Args:
            user_id (str): A Slack user ID

        Returns:
            str: The 'real name' or display name associated with the given user ID
        """
        # Convert user IDs to 'real names', or 'display names' if available
        response = self.client.api_call(
            api_method="users.info",
            params={"user": user_id},
        )

        username = response["user"]["profile"]["display_name_normalized"]
        if username == "":
            username = response["user"]["profile"]["real_name_normalized"]

        return username

    def get_users_in_team(self, team_name):
        """Retrieve the members of a Slack usergroup

        Returns:
            dict: A dictionary of members of a Slack usergroup. Keys are the Slack users'
                'real names', or display names if available, and values are the users'
                IDs.
        """
        self._get_user_ids(team_name=team_name)

        logger.info("Converting user IDs into display names")
        user_handles_and_ids = {}
        for user_id in self.user_ids:
            user_handle = self._convert_user_id_to_handle(user_id)
            user_handles_and_ids[user_handle] = user_id

        # Sort the dictionary alphabetically by key, i.e., display names
        user_handles_and_ids = OrderedDict(sorted(user_handles_and_ids.items()))

        return user_handles_and_ids


def main():
    from rich import print_json

    app = SlackTeamMembers()
    usernames = app.get_users_in_team()
    print_json(data=usernames)


if __name__ == "__main__":
    main()
