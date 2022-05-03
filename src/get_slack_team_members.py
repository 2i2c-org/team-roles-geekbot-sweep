import os
from collections import OrderedDict

from slack_sdk import WebClient


class SlackTeamMembers:
    def __init__(self):
        # Set variables
        self.team_name = os.environ["TEAM_NAME"]

        # Instantiate a SLACK API client
        self.client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

    def _get_team_id(self):
        # Get all usergroups in workspace
        response = self.client.api_call(
            api_method="usergroups.list",
        )

        # Find ID for the self.team_name usergroup
        index = next(
            idx
            for (idx, usergroup) in enumerate(response["usergroups"])
            if usergroup["handle"] == self.team_name
        )
        self.usergroup_id = response["usergroups"][index]["id"]

    def _get_user_ids(self):
        self._get_team_id()

        # Find all user IDs in the self.team_name usergroup
        response = self.client.api_call(
            api_method="usergroups.users.list",
            params={"usergroup": self.usergroup_id},
        )
        self.user_ids = response["users"]

    def _convert_user_id_to_handle(self, user_id):
        # Convert user IDs to 'real names', or 'display names' if available
        response = self.client.api_call(
            api_method="users.info",
            params={"user": user_id},
        )

        username = response["user"]["profile"]["display_name_normalized"]
        if username == "":
            username = response["user"]["profile"]["real_name_normalized"]

        return username

    def get_users_in_team(self):
        self._get_user_ids()

        user_handles_and_ids = {}
        for user_id in self.user_ids:
            user_handle = self._convert_user_id_to_handle(user_id)
            user_handles_and_ids[user_handle] = user_id

        user_handles_and_ids = OrderedDict(sorted(user_handles_and_ids.items()))

        return user_handles_and_ids


if __name__ == "__main__":
    from rich import print_json

    app = SlackTeamMembers()
    usernames = app.get_users_in_team()
    print_json(data=usernames)
