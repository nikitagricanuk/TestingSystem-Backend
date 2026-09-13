from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services.certificates.field_values import build_field_values, build_verification_code


class TestBuildFieldValues:
    def test_builds_all_fields_from_user_and_result(self):
        user = SimpleNamespace(
            full_name="Петров Петр Петрович",
            school=SimpleNamespace(short_name="Школа №4", full_name="МАОУ Школа №4"),
        )
        result = SimpleNamespace(score=84.5, duration_seconds=125, time_finish=datetime(2025, 7, 15))

        values = build_field_values(user=user, result=result, rank=3)

        assert values["full_name_short"] == "Петров П. П."
        assert values["score"] == "84.5"
        assert values["rank"] == "3"
        assert values["duration"] == "02:05"
        assert values["date"] == "15 июля 2025"
        assert values["school"] == "Школа №4"

    def test_missing_user_produces_empty_name_and_school(self):
        result = SimpleNamespace(score=50.0, duration_seconds=60, time_finish=datetime(2025, 1, 1))
        values = build_field_values(user=None, result=result)
        assert values["full_name_short"] == ""
        assert values["school"] == ""
        assert values["rank"] == ""

    def test_school_falls_back_to_full_name_when_no_short_name(self):
        user = SimpleNamespace(full_name="A B", school=SimpleNamespace(short_name=None, full_name="Full School Name"))
        result = SimpleNamespace(score=1, duration_seconds=1, time_finish=None)
        values = build_field_values(user=user, result=result)
        assert values["school"] == "Full School Name"


class TestBuildVerificationCode:
    def test_is_deterministic_for_the_same_result_id(self):
        rid = uuid4()
        assert build_verification_code(rid) == build_verification_code(rid)

    def test_differs_between_results(self):
        assert build_verification_code(uuid4()) != build_verification_code(uuid4())

    def test_is_ten_uppercase_hex_characters(self):
        code = build_verification_code(uuid4())
        assert len(code) == 10
        assert code == code.upper()
        int(code, 16)  # raises if not hex
