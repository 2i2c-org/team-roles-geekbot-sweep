"""
Functions to get Slack members who are in a given usergroup
"""

import json
from collections import OrderedDict
from pathlib import Path

from loguru import logger
from slack_sdk import WebClient

from ..encryption.sops import get_decrypted_file


class SlackUsergroupMembers:
    """Find the members of a given Slack usergroup"""

    def __init__(self):
        # Set filepaths
        project_path = Path(__file__).parent.parent.parent
        secrets_path = project_path.joinpath("secrets")

        # Get Slack bot token
        with get_decrypted_file(secrets_path.joinpath("slack_bot_token.json")) as df:
            with open(df) as f:
                contents = json.load(f)

        # Instantiate a SLACK API client
        self.client = WebClient(token=contents["slack_bot_token"])

    def _get_usergroup_id(self, usergroup_name):
        """Retrieve the ID of a given Slack usergroup"""
        logger.info(f"Retrieving ID for Slack usergroup: {usergroup_name}")

        # Get all usergroups in workspace
        response = self.client.api_call(api_method="usergroups.list")

        # Find ID for the usergroup
        index = next(
            idx
            for (idx, usergroup) in enumerate(response["usergroups"])
            if usergroup["handle"] == usergroup_name
        )
        self.usergroup_id = response["usergroups"][index]["id"]

    def _get_user_ids(self, usergroup_name):
        """
        Retrieve the user IDs of the members of a given usergroup
        """
        self._get_usergroup_id(usergroup_name)

        logger.info(
            f"Retrieving user IDs for members of Slack usergroup: {usergroup_name}"
        )

        # Find all user IDs in the usergroup
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

    def get_users_in_usergroup(self, usergroup_name):
        """Retrieve the members of a Slack usergroup

        Returns:
            dict: A dictionary of members of a Slack usergroup. Keys are the Slack users'
                'real names', or display names if available, and values are the users'
                IDs.
        """
        self._get_user_ids(usergroup_name)

        logger.info("Converting user IDs into display names")
        user_handles_and_ids = {}
        for user_id in self.user_ids:
            user_handle = self._convert_user_id_to_handle(user_id)
            user_handles_and_ids[user_handle] = user_id

        # Sort the dictionary alphabetically by key, i.e., display names
        user_handles_and_ids = OrderedDict(sorted(user_handles_and_ids.items()))

        return user_handles_and_ids


def main():
    import argparse

    from rich import print_json

    parser = argparse.ArgumentParser(
        description="List the members and IDs of a Slack usergroup"
    )

    parser.add_argument(
        "usergroup_name",
        type=str,
        help="The name of the Slack usergroup to list members of",
    )

    args = parser.parse_args()

    app = SlackUsergroupMembers()
    usernames = app.get_users_in_usergroup(args.usergroup_name)
    print_json(data=usernames)


if __name__ == "__main__":
    main()
