import argparse
import json
import os
from datetime import datetime, timedelta
from itertools import cycle, islice
from pathlib import Path

from dateutil.relativedelta import relativedelta
from googleapiclient.errors import HttpError

from src.calendar.gcal_api_auth import GoogleCalendarAPI
from src.geekbot.get_slack_team_members import SlackTeamMembers

ROOT_DIR = Path(__file__).parent.parent.parent

ROLE_CYCLES = {
    "meeting-facilitator": {
        "unit": "months",
        "frequency": 1,  # Monthly
        "period": 1,
        "n_cycles": 12,  # Equates to 1 year
    },
    "support-steward": {
        "unit": "days",
        "frequency": 14,  # Fortnightly
        "period": 28,  # 4 weeks
        "n_cycles": 26,  # Equates to 1 year
    },
}


class CreateBulkEvents:
    def __init__(self, date=None):
        self.calendar_id = os.environ["CALENDAR_ID"]
        self._generate_reference_date(date=date)
        self.team_members = SlackTeamMembers().get_users_in_team().keys()
        self.gcal_api = GoogleCalendarAPI().authenticate()

        team_roles_path = ROOT_DIR.joinpath("team-roles.json")
        with open(team_roles_path) as stream:
            self.team_roles = json.load(stream)

    def _generate_reference_date(self, date=None):
        if date is None:
            self.reference_date = datetime.today()
        else:
            self.reference_date = datetime.strptime(date, "%Y-%m-%d")

    def _adjust_reference_date(self):
        weekday_num = self.reference_date.isoweekday()

        if weekday_num < 3:
            self.reference_date = self.reference_date + timedelta(
                days=(3 - weekday_num)
            )
        elif weekday_num > 3:
            self.reference_date = self.reference_date + timedelta(
                days=(7 + (3 - weekday_num))
            )

    def _calculate_event_dates_meeting_facilitator(self, offset):
        start_date = self.reference_date + relativedelta(
            months=ROLE_CYCLES["meeting-facilitator"]["frequency"] * offset + 1
        )
        end_date = start_date + relativedelta(
            months=ROLE_CYCLES["meeting-facilitator"]["period"]
        )

        start_date = start_date.replace(day=1)
        end_date = end_date.replace(day=1)

        return start_date, end_date

    def _calculate_event_dates_support_steward(self, offset):

        start_date = self.reference_date + timedelta(
            days=(ROLE_CYCLES["support-steward"]["frequency"] * offset)
        )
        end_date = start_date + timedelta(
            days=(ROLE_CYCLES["support-steward"]["period"])
        )

        return start_date, end_date

    def _create_event(self, role, name, offset):
        if role == "meeting-facilitator":
            start_date, end_date = self._calculate_event_dates_meeting_facilitator(
                offset
            )
        elif role == "support-steward":
            start_date, end_date = self._calculate_event_dates_support_steward(offset)

        body = {
            "summary": f"{' '.join(role.split('-')).title()}: {name.split()[0]}",
            "start": {
                "date": start_date.strftime("%Y-%m-%d"),
                "timeZone": "Etc/UTC",
            },
            "end": {
                "date": end_date.strftime("%Y-%m-%d"),
                "timeZone": "Etc/UTC",
            },
        }

        try:
            self.gcal_api.events().insert(
                calendarId=self.calendar_id, body=body
            ).execute()
        except HttpError as error:
            print(f"An error occured: {error}")

    def create_bulk_events(self, role, n_cycles=None):
        if role == "meeting-facilitator":
            current_member = self.team_roles[role.replace("-", "_")]["name"]
        elif role == "support-steward":
            self._adjust_reference_date()
            current_member = self.team_roles[role.replace("-", "_")]["current"]["name"]
        current_member_index = list(self.team_members).index(current_member)

        if n_cycles is None:
            n_cycles = ROLE_CYCLES[role]["n_cycles"]

        team_members = list(
            islice(
                cycle(self.team_members),
                current_member_index + 1,
                n_cycles + current_member_index + 1,
            )
        )

        for i in range(n_cycles):
            next_team_member = team_members[i]
            self._create_event(role, next_team_member, i)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "role",
        choices=["meeting-facilitator", "support-steward"],
        help="",
    )
    parser.add_argument(
        "-n",
        "--n-cycles",
        type=int,
        default=None,
        help="",
    )
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        help="",
    )

    args = parser.parse_args()

    create_bulk_events = CreateBulkEvents(date=args.date)
    create_bulk_events.create_bulk_events(args.role, n_cycles=args.n_cycles)


if __name__ == "__main__":
    main()
