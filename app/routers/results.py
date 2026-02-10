from datetime import datetime, timezone
import json
from uuid import UUID

from aredis_om import NotFoundError
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.results import Result, LeaderboardEntry, GroupScore
from app.services.auth.routers.auth import get_current_user
from app.schemas.users import UserFull
from app.services.testing_engine.models.redis import Session as SessionModel, SessionStatus, QuestionRedis
from app.repositories.dao.userdao import UserDAO

router = APIRouter()


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


async def _load_questions(question_ids: list[UUID]) -> list[QuestionRedis]:
    questions: list[QuestionRedis] = []
    for question_id in question_ids:
        try:
            questions.append(await QuestionRedis.get(question_id))
        except Exception:
            continue
    return questions


def _group_scores(questions: list[QuestionRedis], answers: dict[str, str]) -> list[GroupScore]:
    grouped: dict[str, dict[str, int]] = {}
    for question in questions:
        group = getattr(question, "category", None) or "general"
        try:
            index_key = int(getattr(question, "index", 0))
        except Exception:
            index_key = getattr(question, "index", 0)
        if group not in grouped:
            grouped[group] = {"correct": 0, "total": 0}
        grouped[group]["total"] += 1
        if answers.get(str(index_key)) == getattr(question, "correct_answer", None):
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
    questions = await _load_questions(question_ids)

    correct_answers = 0
    for question in questions:
        try:
            index_key = int(getattr(question, "index", 0))
        except Exception:
            index_key = getattr(question, "index", 0)
        if answers.get(str(index_key)) == getattr(question, "correct_answer", None):
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
        group_scores=_group_scores(questions, answers),
    )


@router.get("/tests/result/{id}", response_model=Result)
async def get_tests_result_result_id(
    id: UUID,
    current_user: UserFull = Depends(get_current_user),
) -> Result:
    """Get test result by ID"""
    try:
        session = await SessionModel.get(str(id))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found") from exc

    if str(session.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Result not available")

    return await _build_result(session)


@router.get("/tests/leaderboard", response_model=list[LeaderboardEntry])
async def get_tests_leaderboard(
    current_user: UserFull = Depends(get_current_user),
) -> list[LeaderboardEntry]:
    sessions = await SessionModel.find(SessionModel.status == SessionStatus.FINISHED).all()
    if not sessions:
        return []

    entries: list[tuple[float, SessionModel, Result]] = []
    for session in sessions:
        result = await _build_result(session)
        entries.append((result.score or 0.0, session, result))

    entries.sort(key=lambda item: item[0], reverse=True)

    leaderboard: list[LeaderboardEntry] = []
    for idx, (_, session, result) in enumerate(entries, start=1):
        user = await UserDAO().get_user_by_id(str(session.user_id))
        nickname = getattr(user, "nickname", None) if user else None
        leaderboard.append(
            LeaderboardEntry(
                rank=idx,
                nickname=nickname or "Anonymous",
                score=result.score or 0.0,
                test_id=UUID(str(session.test_id)),
                group_scores=result.group_scores,
            )
        )

    return leaderboard
