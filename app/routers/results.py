from datetime import datetime, timedelta, timezone
from enum import Enum
import json
from uuid import UUID

from aredis_om import NotFoundError
from aredis_om.model.model import QueryNotSupportedError
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.results import (
    Result,
    LeaderboardEntry,
    GroupScore,
    SessionReview,
    SessionReviewQuestion,
    QuestionAnalysisOut,
    TestAnalysisOut,
)
from app.services.auth.routers.auth import get_current_user, require_permissions
from app.core.permissions import Permissions
from app.schemas.users import UserFull
from app.services.testing_engine.models.redis import Session as SessionModel, SessionStatus, QuestionRedis
from app.services.testing_engine.grading import is_correct_answer
from app.services.testing_engine.item_analysis import AttemptRecord, compute_question_stats, compute_weights
from app.repositories.dao.userdao import UserDAO
from app.repositories.dao.geodao import SettlementDAO
from app.repositories.dao.testdao import TestDAO

router = APIRouter()


class RatingScope(str, Enum):
    GLOBAL = "global"
    REGION = "region"
    CITY = "city"
    SCHOOL = "school"


class RatingPeriod(str, Enum):
    ALL = "all"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


def _normalize_status(value: object) -> str:
    status_value = value.value if isinstance(value, SessionStatus) else str(value)
    status_map = {
        SessionStatus.ACTIVE.value: "active",
        SessionStatus.FINISHED.value: "completed",
        SessionStatus.CLOSED.value: "expired",
        SessionStatus.CREATED.value: "active",
    }
    return status_map.get(status_value, "active")


def _question_ids_from_session(session: SessionModel) -> list[UUID]:
    try:
        return [UUID(qid) for qid in json.loads(session.question_ids or "[]")]
    except Exception:
        return []


def _score_from_counts(correct_answers: int, total_questions: int) -> float:
    return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0


async def _load_questions(question_ids: list[UUID]) -> dict[UUID, QuestionRedis]:
    """Load QuestionRedis records keyed by question_id.

    Deliberately keyed by id rather than returned as a plain list: QuestionRedis is
    cached globally per-question (many sessions can share one bank question), so its
    own `.index` field may not match *this* session's position for that question.
    Position must always come from this session's own `question_ids` ordering.
    """
    questions: dict[UUID, QuestionRedis] = {}
    for question_id in question_ids:
        try:
            questions[question_id] = await QuestionRedis.get(question_id)
        except Exception:
            continue
    return questions


def _group_scores(
    question_ids: list[UUID],
    questions_by_id: dict[UUID, QuestionRedis],
    answers: dict[str, str],
) -> list[GroupScore]:
    grouped: dict[str, dict[str, int]] = {}
    for position, question_id in enumerate(question_ids):
        question = questions_by_id.get(question_id)
        if question is None:
            continue
        group = getattr(question, "category", None) or "general"
        if group not in grouped:
            grouped[group] = {"correct": 0, "total": 0}
        grouped[group]["total"] += 1
        question_type = getattr(question, "question_type", "single")
        if is_correct_answer(question_type, getattr(question, "correct_answer", None), answers.get(str(position))):
            grouped[group]["correct"] += 1

    scores: list[GroupScore] = []
    for group, counts in grouped.items():
        total = counts["total"]
        correct = counts["correct"]
        scores.append(
            GroupScore(
                group=group,
                score=_score_from_counts(correct, total),
                total=total,
            )
        )
    return scores


async def _build_result(session: SessionModel) -> Result:
    question_ids = _question_ids_from_session(session)
    answers = json.loads(session.answers or "{}")
    questions_by_id = await _load_questions(question_ids)

    correct_answers = 0
    for position, question_id in enumerate(question_ids):
        question = questions_by_id.get(question_id)
        if question is None:
            continue
        question_type = getattr(question, "question_type", "single")
        if is_correct_answer(question_type, getattr(question, "correct_answer", None), answers.get(str(position))):
            correct_answers += 1

    total_questions = len(question_ids)
    score = session.score
    if score is None:
        score = _score_from_counts(correct_answers, total_questions)

    duration_seconds = session.duration
    if duration_seconds is None and session.time_start and session.time_finish:
        duration_seconds = int((session.time_finish - session.time_start).total_seconds())
    if duration_seconds is None and session.time_start:
        duration_seconds = int(
            datetime.now(timezone.utc).timestamp()
            - session.time_start.replace(tzinfo=timezone.utc).timestamp()
        )

    return Result(
        id=UUID(str(session.sid)),
        score=score,
        certificate_available=False,
        certificate_link=None,
        recommendations=[],
        test_id=UUID(str(session.test_id)),
        user_id=UUID(str(session.user_id)),
        status=_normalize_status(session.status),
        time_start=session.time_start,
        time_finish=session.time_finish,
        duration_seconds=duration_seconds,
        rank=None,
        total_questions=total_questions,
        correct_answers=correct_answers,
        group_scores=_group_scores(question_ids, questions_by_id, answers),
    )


async def _load_session(session_id: UUID) -> SessionModel | None:
    try:
        return await SessionModel.get(str(session_id))
    except NotFoundError:
        pass

    try:
        pk_iter = await SessionModel.all_pks()
        async for pk in pk_iter:
            try:
                candidate = await SessionModel.get(pk)
            except NotFoundError:
                continue
            if str(candidate.sid) == str(session_id):
                return candidate
    except Exception:
        return None
    return None


async def _load_finished_sessions(test_id: UUID | None = None) -> list[SessionModel]:
    try:
        query = SessionModel.find(SessionModel.status == SessionStatus.FINISHED)
        if test_id is not None:
            query = SessionModel.find(
                (SessionModel.status == SessionStatus.FINISHED) & (SessionModel.test_id == test_id)
            )
        return await query.all()
    except QueryNotSupportedError:
        pass
    except Exception:
        pass

    sessions: list[SessionModel] = []
    try:
        pk_iter = await SessionModel.all_pks()
        async for pk in pk_iter:
            try:
                session = await SessionModel.get(pk)
            except NotFoundError:
                continue
            status_value = session.status.value if isinstance(session.status, SessionStatus) else str(session.status)
            if status_value != SessionStatus.FINISHED.value:
                continue
            if test_id is not None and str(session.test_id) != str(test_id):
                continue
            sessions.append(session)
    except Exception:
        return []
    return sessions


async def _current_user_scope_ids(current_user: UserFull) -> tuple[UUID | None, UUID | None, UUID | None]:
    """Return (school_id, settlement_id, region_id) for the current user, derived
    from their own school affiliation — used to restrict students to their own
    school/city/region when they request a scoped rating."""
    school = current_user.school
    if school is None:
        return None, None, None
    settlement_id = school.city_id
    region_id = None
    if settlement_id is not None:
        settlement = await SettlementDAO.get(settlement_id)
        region_id = settlement.region_id if settlement else None
    return school.id, settlement_id, region_id


@router.get("/tests/result/{id}", response_model=Result)
async def get_tests_result_result_id(
    id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> Result:
    """Get test result by ID"""
    session = await _load_session(id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")

    if str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Result not available")

    return await _build_result(session)


@router.get("/tests/session/{sid}/review", response_model=SessionReview)
async def get_session_review(
    sid: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> SessionReview:
    """
    Per-question breakdown of one attempt: prompt, choices, the student's answer,
    the correct answer, and time spent per question. Staff with read_any_sessions
    can always view it (PV-A-1's teacher attempt-review requirement); the session's
    own owner can view it only when the test opts in via Test.can_be_reviewed
    ("Разрешить просмотр ответов" in the test editor).
    """
    session = await _load_session(sid)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    is_privileged = Permissions.Sessions.READ_ANY.value in (current_user.permissions or [])
    if not is_privileged:
        if str(session.user_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session not available")
        test = await TestDAO.get(UUID(str(session.test_id)))
        if not test or not test.can_be_reviewed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Review not available for this test")

    question_ids = _question_ids_from_session(session)
    answers = json.loads(session.answers or "{}")
    times = json.loads(getattr(session, "question_times", None) or "{}")
    questions_by_id = await _load_questions(question_ids)

    items: list[SessionReviewQuestion] = []
    for position, question_id in enumerate(question_ids):
        question = questions_by_id.get(question_id)
        student_answer = answers.get(str(position))
        question_type = getattr(question, "question_type", "single") if question else "single"
        correct_answer = getattr(question, "correct_answer", None) if question else None
        choices_raw = getattr(question, "choices", None) if question else None
        try:
            choices = json.loads(choices_raw) if choices_raw else []
        except (TypeError, ValueError):
            choices = []
        items.append(
            SessionReviewQuestion(
                index=position,
                prompt=getattr(question, "content", None) if question else None,
                choices=choices,
                correct_answer=correct_answer,
                student_answer=student_answer,
                is_correct=is_correct_answer(question_type, correct_answer, student_answer),
                time_spent_seconds=times.get(str(position), 0),
            )
        )

    return SessionReview(
        sid=UUID(str(session.sid)),
        test_id=UUID(str(session.test_id)),
        user_id=UUID(str(session.user_id)),
        score=getattr(session, "score", None),
        questions=items,
    )


@router.get("/tests/{test_id}/analysis", response_model=TestAnalysisOut)
async def get_test_analysis(
    test_id: UUID,
    current_user: UserFull = Depends(require_permissions(Permissions.Tests.READ_ANALYSIS)),
) -> TestAnalysisOut:
    """
    Per-question discriminativity/difficulty analysis across every finished
    attempt of this test — the Admin PDF's "Аналитика вопросов" tab.
    """
    test = await TestDAO.get(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    sessions = await _load_finished_sessions(test_id=test_id)

    records_by_question: dict[UUID, list[AttemptRecord]] = {}
    for session in sessions:
        question_ids = _question_ids_from_session(session)
        answers = json.loads(session.answers or "{}")
        total_score = session.score or 0.0
        for position, question_id in enumerate(question_ids):
            answer = answers.get(str(position))
            if answer is None:
                continue
            try:
                question = await QuestionRedis.get(question_id)
            except Exception:
                continue
            question_type = getattr(question, "question_type", "single")
            correct = is_correct_answer(question_type, getattr(question, "correct_answer", None), answer)
            records_by_question.setdefault(question_id, []).append(
                AttemptRecord(total_score=total_score, is_correct=correct)
            )

    if not records_by_question:
        return TestAnalysisOut(
            test_id=test_id, avg_discrimination=0.0, avg_difficulty=0.0, avg_attempts=0.0,
            avg_effective_weight=0.0, questions=[],
        )

    snapshots: dict[UUID, QuestionRedis] = {}
    for question_id in records_by_question:
        try:
            snapshots[question_id] = await QuestionRedis.get(question_id)
        except Exception:
            continue

    stats_by_question = {
        question_id: compute_question_stats(
            records, num_choices=len(json.loads(getattr(snapshots.get(question_id), "choices", None) or "[]"))
        )
        for question_id, records in records_by_question.items()
    }

    mark_out_of_by_question = {
        question_id: getattr(snapshots.get(question_id), "mark_out_of", 1) for question_id in records_by_question
    }
    std_dev_by_question = {qid: s.std_dev for qid, s in stats_by_question.items()}
    weights_by_question = compute_weights(mark_out_of_by_question, std_dev_by_question)

    questions_out: list[QuestionAnalysisOut] = []
    for question_id, stats in stats_by_question.items():
        snapshot = snapshots.get(question_id)
        weights = weights_by_question[question_id]
        questions_out.append(
            QuestionAnalysisOut(
                question_id=question_id,
                category=getattr(snapshot, "category", "") or "",
                question_type=getattr(snapshot, "question_type", "single"),
                attempts=stats.attempts,
                difficulty=stats.difficulty,
                discrimination=stats.discrimination,
                guess_score=stats.guess_score,
                effective_discrimination=stats.effective_discrimination,
                std_dev=stats.std_dev,
                intended_weight=weights.intended_weight,
                effective_weight=weights.effective_weight,
            )
        )

    n = len(questions_out)
    return TestAnalysisOut(
        test_id=test_id,
        avg_discrimination=sum(q.discrimination for q in questions_out) / n,
        avg_difficulty=sum(q.difficulty for q in questions_out) / n,
        avg_attempts=sum(q.attempts for q in questions_out) / n,
        avg_effective_weight=sum(q.effective_weight for q in questions_out) / n,
        questions=questions_out,
    )


_PERIOD_DELTAS = {
    RatingPeriod.WEEK: timedelta(days=7),
    RatingPeriod.MONTH: timedelta(days=30),
    RatingPeriod.YEAR: timedelta(days=365),
}

# Students may only ever see their own scope; teachers/admins/admissions are
# unrestricted and may target any school/city/region explicitly.
_UNRESTRICTED_ROLES = {"teacher", "admin", "admissions_committee"}


@router.get("/tests/leaderboard", response_model=list[LeaderboardEntry])
async def get_tests_leaderboard(
    current_user: UserFull = Depends(get_current_user),
    scope: RatingScope = Query(RatingScope.GLOBAL),
    period: RatingPeriod = Query(RatingPeriod.ALL),
    test_id: UUID | None = None,
    region_id: UUID | None = None,
    settlement_id: UUID | None = None,
    school_id: UUID | None = None,
) -> list[LeaderboardEntry]:
    is_privileged = (current_user.role in _UNRESTRICTED_ROLES) and not current_user.is_guest
    if scope != RatingScope.GLOBAL and not is_privileged:
        # Students (and guests) are always scoped to their own school/city/region,
        # regardless of what they pass in region_id/settlement_id/school_id.
        school_id, settlement_id, region_id = await _current_user_scope_ids(current_user)

    sessions = await _load_finished_sessions(test_id=test_id)
    if not sessions:
        return []

    cutoff = None
    delta = _PERIOD_DELTAS.get(period)
    if delta is not None:
        cutoff = datetime.now(timezone.utc) - delta
    if cutoff is not None:
        def _finished_after_cutoff(s: SessionModel) -> bool:
            finish = s.time_finish
            if finish is None:
                return False
            if finish.tzinfo is None:
                finish = finish.replace(tzinfo=timezone.utc)
            return finish >= cutoff

        sessions = [s for s in sessions if _finished_after_cutoff(s)]

    user_ids = {UUID(str(s.user_id)) for s in sessions}
    users_by_id = await UserDAO().get_users_by_ids(list(user_ids))

    if scope != RatingScope.GLOBAL:
        def _in_scope(session: SessionModel) -> bool:
            user = users_by_id.get(UUID(str(session.user_id)))
            school = getattr(user, "school", None)
            settlement = getattr(school, "settlement", None) if school else None
            if scope == RatingScope.SCHOOL:
                return school_id is not None and school is not None and school.id == school_id
            if scope == RatingScope.CITY:
                return settlement_id is not None and school is not None and school.city_id == settlement_id
            if scope == RatingScope.REGION:
                return (
                    region_id is not None
                    and settlement is not None
                    and settlement.region_id == region_id
                )
            return True

        sessions = [s for s in sessions if _in_scope(s)]

    if not sessions:
        return []

    entries: list[tuple[float, SessionModel, Result]] = []
    for session in sessions:
        result = await _build_result(session)
        entries.append((result.score or 0.0, session, result))

    entries.sort(key=lambda item: item[0], reverse=True)

    leaderboard: list[LeaderboardEntry] = []
    for idx, (_, session, result) in enumerate(entries, start=1):
        user = users_by_id.get(UUID(str(session.user_id)))
        nickname = getattr(user, "nickname", None) if user else None
        school = getattr(user, "school", None) if user else None
        error_rate = (
            1.0 - (result.correct_answers / result.total_questions)
            if result.total_questions
            else 0.0
        )
        leaderboard.append(
            LeaderboardEntry(
                rank=idx,
                nickname=nickname or "Anonymous",
                school=getattr(school, "short_name", None) or getattr(school, "full_name", None) if school else None,
                score=result.score or 0.0,
                error_rate=round(error_rate, 4),
                completed_at=session.time_finish,
                test_id=UUID(str(session.test_id)),
                group_scores=result.group_scores,
            )
        )

    return leaderboard
