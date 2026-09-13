"""
Classical test theory (CTT) item analysis for a test's question bank, matching
the Admin PDF's "Аналитика вопросов" tab:
  - "Индекс легкости" (difficulty/easiness): fraction of attempts answered correctly.
  - "Индекс дискриминации": upper-vs-lower 27% discrimination index — how much
    better high scorers do on this item than low scorers.
  - "Балл случайного угадывания": expected score from guessing blindly (1/choices).
  - "Эффективная дискриминация": discrimination corrected for how much of the
    score range guessing already accounts for.
  - "Намеченный вес" / "Эффективный вес": the item's share of the test's total
    points, and that share re-weighted by how much the item's variance actually
    contributes to spreading students' scores apart.

These are standard, documented CTT formulas — not values dictated by the design
mockup (it shows the UI shape, not the underlying math) — chosen because they're
the conventional way to answer "which questions are good, which aren't" (PV-A-1).
"""
import math
from dataclasses import dataclass
from uuid import UUID

UPPER_LOWER_FRACTION = 0.27


@dataclass
class AttemptRecord:
    total_score: float
    is_correct: bool


@dataclass
class QuestionItemStats:
    attempts: int
    difficulty: float
    discrimination: float
    guess_score: float
    effective_discrimination: float
    std_dev: float


def compute_question_stats(records: list[AttemptRecord], num_choices: int) -> QuestionItemStats:
    n = len(records)
    if n == 0:
        return QuestionItemStats(attempts=0, difficulty=0.0, discrimination=0.0, guess_score=0.0,
                                  effective_discrimination=0.0, std_dev=0.0)

    correct_flags = [1.0 if r.is_correct else 0.0 for r in records]
    p = sum(correct_flags) / n
    variance = sum((c - p) ** 2 for c in correct_flags) / n
    std_dev = math.sqrt(variance)

    guess_score = (1.0 / num_choices) if num_choices > 0 else 0.0

    group_size = max(1, round(n * UPPER_LOWER_FRACTION))
    sorted_records = sorted(records, key=lambda r: r.total_score, reverse=True)
    upper = sorted_records[:group_size]
    lower = sorted_records[-group_size:] if group_size < n else sorted_records
    upper_p = sum(1 for r in upper if r.is_correct) / len(upper)
    lower_p = sum(1 for r in lower if r.is_correct) / len(lower)
    discrimination = upper_p - lower_p

    denom = 1.0 - guess_score
    effective_discrimination = discrimination / denom if denom > 0 else discrimination

    return QuestionItemStats(
        attempts=n,
        difficulty=p,
        discrimination=discrimination,
        guess_score=guess_score,
        effective_discrimination=effective_discrimination,
        std_dev=std_dev,
    )


@dataclass
class QuestionWeights:
    intended_weight: float
    effective_weight: float


def compute_weights(mark_out_of_by_question: dict[UUID, int], std_dev_by_question: dict[UUID, float]) -> dict[UUID, QuestionWeights]:
    """Intended weight = each item's share of the test's total possible points.
    Effective weight = that same point value re-weighted by the item's standard
    deviation, i.e. how much it actually contributes to separating students'
    scores (an item worth a lot of points that everyone gets right or wrong the
    same way contributes little to the *spread* of scores)."""
    total_marks = sum(mark_out_of_by_question.values())
    weighted_std_total = sum(
        mark_out_of_by_question[qid] * std_dev_by_question.get(qid, 0.0) for qid in mark_out_of_by_question
    )

    weights: dict[UUID, QuestionWeights] = {}
    for qid, mark_out_of in mark_out_of_by_question.items():
        intended = (mark_out_of / total_marks) if total_marks > 0 else 0.0
        weighted = mark_out_of * std_dev_by_question.get(qid, 0.0)
        effective = (weighted / weighted_std_total) if weighted_std_total > 0 else intended
        weights[qid] = QuestionWeights(intended_weight=intended, effective_weight=effective)
    return weights
