import json

from app.services.testing_engine.grading import is_correct_answer


class TestIsCorrectAnswer:
    def test_single_exact_match(self):
        assert is_correct_answer("single", "A", "A") is True

    def test_single_mismatch(self):
        assert is_correct_answer("single", "A", "B") is False

    def test_text_exact_match(self):
        assert is_correct_answer("text", "Paris", "Paris") is True

    def test_none_submitted_answer_is_never_correct(self):
        assert is_correct_answer("single", "A", None) is False

    def test_multiple_matches_regardless_of_order(self):
        correct = json.dumps(["0", "2"])
        submitted = json.dumps(["2", "0"])
        assert is_correct_answer("multiple", correct, submitted) is True

    def test_multiple_partial_selection_is_wrong(self):
        correct = json.dumps(["0", "2"])
        submitted = json.dumps(["0"])
        assert is_correct_answer("multiple", correct, submitted) is False

    def test_multiple_extra_selection_is_wrong(self):
        correct = json.dumps(["0", "2"])
        submitted = json.dumps(["0", "1", "2"])
        assert is_correct_answer("multiple", correct, submitted) is False

    def test_multiple_falls_back_to_string_equality_when_not_json(self):
        # Legacy data that was never JSON-encoded still compares as a plain string.
        assert is_correct_answer("multiple", "A", "A") is True
        assert is_correct_answer("multiple", "A", "B") is False
