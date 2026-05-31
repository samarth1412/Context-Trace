from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas import (
    EvalQuestionsRequest,
    EvalQuestionsResponse,
    EvalSetCreateRequest,
    EvalSetResponse,
    EvalSetSummary,
)
from app.services.evals import EvalSetService

router = APIRouter(prefix="/eval-sets", tags=["eval-sets"])


@router.post("", response_model=EvalSetResponse, status_code=201)
def create_eval_set(
    request: EvalSetCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> EvalSetResponse:
    return EvalSetService(db, user).create_eval_set(request)


@router.post("/{eval_set_id}/questions", response_model=EvalQuestionsResponse)
def add_eval_questions(
    eval_set_id: str,
    request: EvalQuestionsRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> EvalQuestionsResponse:
    return EvalSetService(db, user).add_questions(eval_set_id, request)


@router.post("/{eval_set_id}/runs", response_model=EvalSetSummary)
def run_eval_set(
    eval_set_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> EvalSetSummary:
    return EvalSetService(db, user).run_existing_traces(eval_set_id)


@router.get("/{eval_set_id}/summary", response_model=EvalSetSummary)
def get_eval_set_summary(
    eval_set_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> EvalSetSummary:
    return EvalSetService(db, user).get_summary(eval_set_id)
