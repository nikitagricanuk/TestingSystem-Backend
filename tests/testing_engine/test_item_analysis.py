from uuid import uuid4

from app.services.testing_engine.item_analysis import (
    AttemptRecord,
    compute_question_stats,
    compute_weights,
)


class TestComputeQuestionStats:
    def test_no_attempts_returns_zeros(self):
        stats = compute_question_stats([], num_choices=4)
        assert stats.attempts == 0
        assert stats.difficulty == 0.0
        assert stats.discrimination == 0.0

    def test_everyone_correct_has_zero_discrimination(self):
        records = [AttemptRecord(total_score=s, is_correct=True) for s in [10, 20, 30, 40, 50]]
        stats = compute_question_stats(records, num_choices=4)
        assert stats.difficulty == 1.0
        assert stats.discrimination == 0.0
        assert stats.std_dev == 0.0

    def test_perfectly_discriminating_item(self):
        # High scorers all get it right, low scorers all get it wrong.
        records = [
            AttemptRecord(total_score=90, is_correct=True),
            AttemptRecord(total_score=80, is_correct=True),
            AttemptRecord(total_score=20, is_correct=False),
            AttemptRecord(total_score=10, is_correct=False),
        ]
        stats = compute_question_stats(records, num_choices=4)
        assert stats.discrimination == 1.0
        assert stats.difficulty == 0.5

    def test_guess_score_is_inverse_of_choice_count(self):
        records = [AttemptRecord(total_score=1, is_correct=True)]
        stats = compute_question_stats(records, num_choices=5)
        assert stats.guess_score == 0.2

    def test_text_question_with_no_choices_has_zero_guess_score(self):
        records = [AttemptRecord(total_score=1, is_correct=True)]
        stats = compute_question_stats(records, num_choices=0)
        assert stats.guess_score == 0.0

    def test_difficulty_is_fraction_correct(self):
        records = [AttemptRecord(total_score=i, is_correct=(i % 2 == 0)) for i in range(10)]
        stats = compute_question_stats(records, num_choices=4)
        assert stats.difficulty == 0.5


class TestComputeWeights:
    def test_intended_weight_matches_point_share(self):
        q1, q2 = uuid4(), uuid4()
        weights = compute_weights(
            mark_out_of_by_question={q1: 1, q2: 3},
            std_dev_by_question={q1: 0.5, q2: 0.5},
        )
        assert weights[q1].intended_weight == 0.25
        assert weights[q2].intended_weight == 0.75

    def test_effective_weight_favors_higher_variance_items(self):
        q1, q2 = uuid4(), uuid4()
        # Equal points, but q2 discriminates a lot more (higher std dev).
        weights = compute_weights(
            mark_out_of_by_question={q1: 1, q2: 1},
            std_dev_by_question={q1: 0.1, q2: 0.5},
        )
        assert weights[q2].effective_weight > weights[q1].effective_weight

    def test_zero_total_marks_does_not_divide_by_zero(self):
        q1 = uuid4()
        weights = compute_weights(mark_out_of_by_question={q1: 0}, std_dev_by_question={q1: 0.0})
        assert weights[q1].intended_weight == 0.0
        assert weights[q1].effective_weight == 0.0
