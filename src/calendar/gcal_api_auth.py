"""
Authenticate with Google's Calendar API using a Service Account
"""

import json
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger

from ..encryption.sops import get_decrypted_file


class GoogleCalendarAPI:
    """Interact with the Google Calendar API"""

    def __init__(self, scopes=["https://www.googleapis.com/auth/calendar"]):
        self.scopes = scopes

        # Set filepaths
        project_path = Path(__file__).parent.parent.parent
        self.secrets_path = project_path.joinpath("secrets")

        # Read in calendar ID
        with get_decrypted_file(self.secrets_path.joinpath("calendar_id.json")) as df:
            with open(df) as f:
                contents = json.load(f)

        self.calendar_id = contents["calendar_id"]

    def authenticate(self):
        """Return an authenticated instance of Google's Calendar API"""
        gcp_service_account_file = self.secrets_path.joinpath(
            "gcp_service_account.json"
        )

        with get_decrypted_file(gcp_service_account_file) as decrypted_file:
            creds = service_account.Credentials.from_service_account_file(
                decrypted_file
            )

        creds = creds.with_scopes(self.scopes)

        try:
            return build("calendar", "v3", credentials=creds)
        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            sys.exit(1)
