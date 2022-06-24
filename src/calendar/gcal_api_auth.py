import json
import os
from tempfile import NamedTemporaryFile

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendarAPI:
    def __init__(self, scopes=["https://www.googleapis.com/auth/calendar"]):
        self.calendar_id = os.environ["CALENDAR_ID"]
        self.service_account_key = json.loads(os.environ["GCP_SERVICE_ACCOUNT_KEY"])
        self.scopes = scopes

    def authenticate(self):
        with NamedTemporaryFile(mode="w") as service_account_file:
            json.dump(self.service_account_key, service_account_file)
            service_account_file.flush()
            creds = service_account.Credentials.from_service_account_file(
                service_account_file.name
            )

        creds = creds.with_scopes(self.scopes)

        try:
            return build("calendar", "v3", credentials=creds)
        except HttpError as error:
            print("An error occurred: %s" % error)
