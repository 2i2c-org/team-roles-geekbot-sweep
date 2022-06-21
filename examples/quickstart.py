"""
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
"""
from __future__ import print_function

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# The name of the calendar to experiment with. Must be one that you own!
CALENDAR_NAME = os.environ.get("CALENDAR_NAME", None)
if CALENDAR_NAME is None:
    raise ValueError("Must provide the CALENDAR_NAME environment variable!")


def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)

        # Get a list of all calendars available to the authenticated user
        print("Getting all available calendars...")
        calendars_result = service.calendarList().list().execute()
        calendars = calendars_result.get("items", [])

        if not calendars:
            print("No calendars found.")

        # Find the ID of the chosen calendar
        calendar_id = None
        for cal in calendars:
            calendar_id = cal["id"] if cal["summary"] == CALENDAR_NAME else None
            if calendar_id is not None:
                break

        # Create a test event in chosen calendar
        print(f"Creating a new event in {CALENDAR_NAME}...")
        body = {
            "summary": "Test Event",
            "start": {
                "date": "2022-06-22",
                "timeZone": "Etc/UTC",
            },
            "end": {
                "date": "2022-07-30",
                "timeZone": "Etc/UTC",
            },
        }
        service.events().insert(calendarId=calendar_id, body=body).execute()

    except HttpError as error:
        print("An error occurred: %s" % error)


if __name__ == "__main__":
    main()
