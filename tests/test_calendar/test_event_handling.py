import unittest
from datetime import datetime
from unittest.mock import patch

from src.calendar.event_handling import CalendarEventHandler


class EventHandlerSubClass(CalendarEventHandler):
    def __init__(self, role, usergroup_name):
        self.role = role
        self.today = datetime.today()
        self.usergroup_members = [f"Person {i}" for i in "ABCDEFG"]

        self.gcal_api = None
        self.usergroup_dict = {}
        self.calendar_id = None


def test_create_next_event_dates_meeting_facilitator_no_offset():
    end_date = datetime(2022, 10, 1)

    test_event_handler = EventHandlerSubClass(
        "meeting-facilitator", "meeting-facilitators"
    )
    next_start_date, next_end_date = test_event_handler._calculate_next_event_dates(
        end_date, 0
    )

    expected_start_date = datetime(2022, 10, 1)
    expected_end_date = datetime(2022, 11, 1)

    assert next_start_date == expected_start_date
    assert next_end_date == expected_end_date


def test_create_next_event_dates_support_steward_no_offset():
    end_date = datetime(2022, 9, 21)

    test_event_handler = EventHandlerSubClass("support-steward", "support-stewards")
    next_start_date, next_end_date = test_event_handler._calculate_next_event_dates(
        end_date, 0
    )

    expected_start_date = datetime(2022, 9, 21)
    expected_end_date = datetime(2022, 10, 19)

    assert next_start_date == expected_start_date
    assert next_end_date == expected_end_date


def test_create_next_event_dates_meeting_facilitator_with_offset():
    case = unittest.TestCase()
    end_date = datetime(2022, 10, 1)
    offset = 3
    test_event_handler = EventHandlerSubClass(
        "meeting-facilitator", "meeting-facilitators"
    )

    next_event_dates = []
    for i in range(offset):
        next_event_dates.append(
            test_event_handler._calculate_next_event_dates(end_date, i)
        )

    expected_event_dates = [
        (datetime(2022, 10, 1), datetime(2022, 11, 1)),
        (datetime(2022, 11, 1), datetime(2022, 12, 1)),
        (datetime(2022, 12, 1), datetime(2023, 1, 1)),
    ]

    case.assertCountEqual(next_event_dates, expected_event_dates)


def test_create_next_event_dates_support_steward_with_offset():
    case = unittest.TestCase()
    end_date = datetime(2022, 9, 21)
    offset = 3
    test_event_handler = EventHandlerSubClass("support-steward", "support-stewards")

    next_event_dates = []
    for i in range(offset):
        next_event_dates.append(
            test_event_handler._calculate_next_event_dates(end_date, i)
        )

    expected_event_dates = [
        (datetime(2022, 9, 21), datetime(2022, 10, 19)),
        (datetime(2022, 10, 5), datetime(2022, 11, 2)),
        (datetime(2022, 10, 19), datetime(2022, 11, 16)),
    ]

    case.assertCountEqual(next_event_dates, expected_event_dates)


def test_find_next_team_member_manually():
    test_event_handler = EventHandlerSubClass("support-steward", "support-stewards")
    next_member_no_offset = test_event_handler._find_next_team_member_manually(
        "Person B"
    )
    next_member_with_offset = test_event_handler._find_next_team_member_manually(
        "Person B", 3
    )
    next_member_loop_offset = test_event_handler._find_next_team_member_manually(
        "Person B", 7
    )

    assert next_member_no_offset == "Person C"
    assert next_member_with_offset == "Person F"
    assert next_member_loop_offset == "Person A"


@patch("src.calendar.event_handling.CalendarEventHandler._get_upcoming_events")
def test_get_last_event_meeting_facilitator(mock_upcoming_events):
    test_event_handler = EventHandlerSubClass(
        "meeting-facilitator", "meeting-facilitators"
    )

    mock_upcoming_events.return_value = [
        {
            "start": {"date": "2022-08-01"},
            "end": {"date": "2022-09-01"},
            "summary": "Meeting Facilitator: Person A",
        },
        {
            "start": {"date": "2022-09-01"},
            "end": {"date": "2022-10-01"},
            "summary": "Meeting Facilitator: Person B",
        },
    ]

    end_date, last_member = test_event_handler._get_last_event(suppress_logs=True)

    assert end_date == datetime(2022, 10, 1)
    assert last_member == "Person B"


@patch("src.calendar.event_handling.CalendarEventHandler._get_upcoming_events")
def test_get_last_event_support_steward(mock_upcoming_events):
    test_event_handler = EventHandlerSubClass("support-steward", "support-stewards")

    mock_upcoming_events.return_value = [
        {
            "start": {"date": "2022-08-24"},
            "end": {"date": "2022-09-21"},
            "summary": "Support Steward: Person A",
        },
        {
            "start": {"date": "2022-09-07"},
            "end": {"date": "2022-10-05"},
            "summary": "Support Steward: Person B",
        },
        {
            "start": {"date": "2022-09-21"},
            "end": {"date": "2022-10-19"},
            "summary": "Support Steward: Person C",
        },
    ]

    end_date, last_member = test_event_handler._get_last_event(suppress_logs=True)

    assert end_date == datetime(2022, 10, 5)
    assert last_member == "Person C"


@patch("src.calendar.event_handling.CalendarEventHandler._get_upcoming_events")
def test_get_first_event_meeting_facilitator(mock_upcoming_events):
    test_event_handler = EventHandlerSubClass(
        "meeting-facilitator", "meeting-facilitators"
    )

    mock_upcoming_events.return_value = [
        {
            "start": {"date": "2022-08-01"},
            "end": {"date": "2022-09-01"},
            "summary": "Meeting Facilitator: Person A",
        },
        {
            "start": {"date": "2022-09-01"},
            "end": {"date": "2022-10-01"},
            "summary": "Meeting Facilitator: Person B",
        },
    ]

    end_date, last_member = test_event_handler.get_first_event()

    assert end_date == datetime(2022, 9, 1)
    assert last_member == "Person A"


@patch("src.calendar.event_handling.CalendarEventHandler._get_upcoming_events")
def test_get_first_event_support_steward(mock_upcoming_events):
    test_event_handler = EventHandlerSubClass("support-steward", "support-stewards")

    mock_upcoming_events.return_value = [
        {
            "start": {"date": "2022-08-24"},
            "end": {"date": "2022-09-21"},
            "summary": "Support Steward: Person A",
        },
        {
            "start": {"date": "2022-09-07"},
            "end": {"date": "2022-10-05"},
            "summary": "Support Steward: Person B",
        },
        {
            "start": {"date": "2022-09-21"},
            "end": {"date": "2022-10-19"},
            "summary": "Support Steward: Person C",
        },
    ]

    end_date, last_member = test_event_handler.get_first_event()

    assert end_date == datetime(2022, 9, 21)
    assert last_member == "Person B"


@patch("src.calendar.event_handling.CalendarEventHandler._get_upcoming_events")
def test_find_next_team_member_from_calendar_meeting_facilitator(mock_upcoming_events):
    test_event_handler = EventHandlerSubClass(
        "meeting-facilitator", "meeting-facilitators"
    )

    mock_upcoming_events.return_value = [
        {
            "start": {"date": "2022-08-01"},
            "end": {"date": "2022-09-01"},
            "summary": "Meeting Facilitator: Person A",
        },
        {
            "start": {"date": "2022-09-01"},
            "end": {"date": "2022-10-01"},
            "summary": "Meeting Facilitator: Person B",
        },
    ]

    next_member = test_event_handler.find_next_team_member_from_calendar()

    assert next_member == "Person B"


@patch("src.calendar.event_handling.CalendarEventHandler._get_upcoming_events")
def test_find_next_team_member_from_calendar_support_steward(mock_upcoming_events):
    test_event_handler = EventHandlerSubClass("support-steward", "support-stewards")

    mock_upcoming_events.return_value = [
        {
            "start": {"date": "2022-08-24"},
            "end": {"date": "2022-09-21"},
            "summary": "Support Steward: Person A",
        },
        {
            "start": {"date": "2022-09-07"},
            "end": {"date": "2022-10-05"},
            "summary": "Support Steward: Person B",
        },
        {
            "start": {"date": "2022-09-21"},
            "end": {"date": "2022-10-19"},
            "summary": "Support Steward: Person C",
        },
    ]

    next_member = test_event_handler.find_next_team_member_from_calendar()

    assert next_member == "Person C"


@patch("src.calendar.event_handling.CalendarEventHandler._get_upcoming_events")
def test_find_next_team_member_from_calendar_not_found(mock_upcoming_events):
    test_event_handler = EventHandlerSubClass(
        "meeting-facilitator", "meeting-facilitators"
    )

    mock_upcoming_events.return_value = [
        {
            "start": {"date": "2022-08-01"},
            "end": {"date": "2022-09-01"},
            "summary": "Meeting Facilitator: Person A",
        },
    ]

    next_member = test_event_handler.find_next_team_member_from_calendar()

    assert next_member is None
