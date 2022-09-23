from datetime import datetime

from src.calendar.create_events_bulk import adjust_reference_date


def test_adjust_reference_date_less_than_three():
    test_date = datetime(2022, 9, 19)
    expected_date = datetime(2022, 9, 21)
    result_date = adjust_reference_date(test_date)

    assert result_date == expected_date


def test_adjust_reference_date_more_than_three():
    test_date = datetime(2022, 9, 23)
    expected_date = datetime(2022, 9, 28)
    result_date = adjust_reference_date(test_date)

    assert result_date == expected_date
