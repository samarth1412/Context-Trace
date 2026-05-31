from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_llm_judge_provider
from app.judge import LLMJudgeProvider
from app.models import User
from app.schemas import (
    ExternalEndpointCreateRequest,
    ExternalEndpointResponse,
    ExternalEndpointRunEvalRequest,
    ExternalEndpointRunEvalResponse,
    ExternalEndpointTestRequest,
    ExternalEndpointTestResponse,
)
from app.services.external_endpoints import ExternalEndpointService

router = APIRouter(tags=["external-endpoints"])


@router.post(
    "/projects/{project_id}/external-endpoints",
    response_model=ExternalEndpointResponse,
    status_code=201,
)
def register_external_endpoint(
    project_id: str,
    request: ExternalEndpointCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ExternalEndpointResponse:
    return ExternalEndpointService(db, user).register_endpoint(project_id, request)


@router.post(
    "/external-endpoints/{endpoint_id}/test",
    response_model=ExternalEndpointTestResponse,
)
async def test_external_endpoint(
    endpoint_id: str,
    request: ExternalEndpointTestRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> ExternalEndpointTestResponse:
    return await ExternalEndpointService(db, user).test_endpoint(endpoint_id, request)


@router.post(
    "/external-endpoints/{endpoint_id}/run-eval",
    response_model=ExternalEndpointRunEvalResponse,
)
async def run_external_endpoint_eval(
    endpoint_id: str,
    request: ExternalEndpointRunEvalRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    judge_provider: Annotated[LLMJudgeProvider, Depends(get_llm_judge_provider)],
) -> ExternalEndpointRunEvalResponse:
    return await ExternalEndpointService(db, user).run_eval(
        endpoint_id,
        request,
        judge_provider,
    )
