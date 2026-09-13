import json


def _as_choice_set(value: str) -> set[str] | None:
    """Parse a JSON-encoded list of choice values into a set; None if not a JSON list."""
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    if isinstance(parsed, list):
        return {str(item) for item in parsed}
    return None


def is_correct_answer(question_type: str, correct_answer: str, submitted_answer: str | None) -> bool:
    """
    Compare a submitted answer against the stored correct answer for a question.

    - "single" / "text": exact string equality (unchanged historical behavior).
    - "multiple": both sides are treated as JSON-encoded lists of choice values and
      compared as sets, so choice order doesn't matter and partial selections don't
      count as correct. Falls back to string equality if either side isn't valid
      JSON (keeps old data/tests that never used multi-select working).
    """
    if submitted_answer is None:
        return False
    if question_type == "multiple":
        correct_set = _as_choice_set(correct_answer)
        submitted_set = _as_choice_set(submitted_answer)
        if correct_set is not None and submitted_set is not None:
            return correct_set == submitted_set
    return submitted_answer == correct_answer
