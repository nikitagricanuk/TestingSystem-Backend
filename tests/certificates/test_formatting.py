from datetime import datetime

from app.services.certificates.formatting import (
    format_duration,
    format_russian_date,
    format_short_name,
)


class TestFormatShortName:
    def test_full_three_part_name(self):
        assert format_short_name("Петров Петр Петрович") == "Петров П. П."

    def test_two_part_name(self):
        assert format_short_name("Петров Петр") == "Петров П."

    def test_single_word_returned_unchanged(self):
        assert format_short_name("Петров") == "Петров"

    def test_none_returns_empty_string(self):
        assert format_short_name(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert format_short_name("") == ""


class TestFormatDuration:
    def test_under_an_hour(self):
        assert format_duration(125) == "02:05"

    def test_over_an_hour(self):
        assert format_duration(3725) == "1:02:05"

    def test_none_returns_empty_string(self):
        assert format_duration(None) == ""

    def test_zero_seconds(self):
        assert format_duration(0) == "00:00"


class TestFormatRussianDate:
    def test_formats_with_russian_month_name(self):
        assert format_russian_date(datetime(2025, 7, 15)) == "15 июля 2025"

    def test_january(self):
        assert format_russian_date(datetime(2025, 1, 1)) == "1 января 2025"

    def test_none_returns_empty_string(self):
        assert format_russian_date(None) == ""
