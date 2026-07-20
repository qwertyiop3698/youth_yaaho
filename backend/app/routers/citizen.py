"""docs/07 /api/v1/citizen/* 라우터.

doc01 권한분리 원칙: citizen 엔드포인트는 익명 접근을 허용하지만, 생성 시 한 번
발급한 X-Session-Token과 session_id를 함께 요구한다. 개인정보 포함 데이터는 이
라우터 안에서만 다룬다.

2026-07-09 회원가입/로그인(JWT) 추가: 기존 익명 진단 플로우는 그대로 유지하고,
로그인한 회원이 /diagnose를 호출하면 person(user_id)을 세션에 연동하는 방식으로만
확장한다 - 로그인은 히스토리 저장/조회를 위한 선택 기능이지 필수가 아니다.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from .. import db
from ..dependencies import get_engine
from ..schemas import (
    DiagnoseRequest,
    DiagnoseResponse,
    ExplanationResponse,
    HistoryEntry,
    HistoryResponse,
    LoginRequest,
    OtherPolicyItem,
    RecommendationItem,
    RecommendationsResponse,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from ..services import auth_service, diagnose_service, explanation_service, recommendation_service
from ..services.pipeline_store import PipelineStore, get_pipeline_store
from ..user_auth import get_current_user_id, get_optional_current_user_id

router = APIRouter(prefix="/api/v1/citizen", tags=["citizen"])


@router.post("/auth/signup", response_model=SignupResponse, status_code=201)
def signup(payload: SignupRequest, engine: Engine = Depends(get_engine)) -> SignupResponse:
    try:
        result = auth_service.signup(engine, payload.email, payload.password, payload.birthdate, payload.dong_code)
    except auth_service.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except auth_service.AgeLimitExceededError as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    return SignupResponse(**result)


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, engine: Engine = Depends(get_engine)) -> TokenResponse:
    try:
        tokens = auth_service.login(engine, payload.email, payload.password)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except auth_service.AgeLimitExceededError as exc:
        raise HTTPException(status_code=401, detail=exc.detail) from exc
    return TokenResponse(**tokens)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, engine: Engine = Depends(get_engine)) -> TokenResponse:
    try:
        tokens = auth_service.refresh_tokens(engine, payload.refresh_token)
    except auth_service.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except auth_service.UserNotFoundError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except auth_service.AgeLimitExceededError as exc:
        raise HTTPException(status_code=401, detail=exc.detail) from exc
    return TokenResponse(**tokens)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    engine: Engine = Depends(get_engine), user_id: str = Depends(get_current_user_id)
) -> Response:
    auth_service.revoke_user_tokens(engine, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/auth/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    engine: Engine = Depends(get_engine), user_id: str = Depends(get_current_user_id)
) -> Response:
    """로그인 회원의 진단 세션과 계정을 실제로 삭제한다.

    access/refresh 토큰은 별도 저장하지 않는 stateless JWT지만, 사용자가 삭제된 뒤에는
    모든 인증 경로가 DB 사용자 존재를 확인하므로 더 이상 사용할 수 없다.
    """
    with engine.begin() as conn:
        conn.execute(delete(db.citizen_sessions).where(db.citizen_sessions.c.user_id == user_id))
        conn.execute(delete(db.users_table).where(db.users_table.c.user_id == user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_session_or_404(
    engine: Engine,
    session_id: str,
    current_user_id: str | None = None,
    session_token: str | None = None,
) -> dict:
    with engine.connect() as conn:
        row = (
            conn.execute(select(db.citizen_sessions).where(db.citizen_sessions.c.session_id == session_id))
            .mappings()
            .first()
        )
    if row is None:
        raise HTTPException(status_code=404, detail="session_id를 찾을 수 없습니다.")
    session = dict(row)
    owner_id = session.get("user_id")
    if owner_id is None:
        expected_hash = session.get("access_token_hash")
        provided_hash = _hash_session_token(session_token) if session_token else None
        if not expected_hash or not provided_hash or not secrets.compare_digest(provided_hash, expected_hash):
            raise HTTPException(status_code=401, detail="익명 진단 세션 토큰이 없거나 올바르지 않습니다.")
        return session
    if owner_id is not None and current_user_id is None:
        raise HTTPException(status_code=401, detail="로그인 회원의 진단 기록입니다. 로그인이 필요합니다.")
    if owner_id is not None and owner_id != current_user_id:
        raise HTTPException(status_code=403, detail="다른 사용자의 진단 기록에는 접근할 수 없습니다.")
    return session


@router.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(
    payload: DiagnoseRequest,
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
    user_id: str | None = Depends(get_optional_current_user_id),
) -> DiagnoseResponse:
    result = diagnose_service.diagnose(payload, store)
    session_id = str(uuid.uuid4())
    session_access_token = secrets.token_urlsafe(32) if user_id is None else None

    diagnosis_result = {
        "domain_indices": result["domain_indices"],
        "cluster_membership": result["cluster_membership"],
        "risk_probability": result["risk_probability"],
        "shap_top3": result.get("shap_top3") or [],
    }

    with engine.begin() as conn:
        conn.execute(
            db.citizen_sessions.insert().values(
                session_id=session_id,
                user_id=user_id,  # 로그인 안 했으면 None(익명 진단 - 기존 플로우 그대로)
                access_token_hash=(
                    _hash_session_token(session_access_token) if session_access_token is not None else None
                ),
                input_payload=payload.model_dump(),
                diagnosis_result=diagnosis_result,
                created_at=datetime.now(timezone.utc),
            )
        )

    return DiagnoseResponse(
        session_id=session_id,
        session_access_token=session_access_token,
        domain_indices=diagnosis_result["domain_indices"],
        cluster_membership=diagnosis_result["cluster_membership"],
        risk_probability=diagnosis_result["risk_probability"],
        diagnosis_mode="approximate",
        approximation_notice=diagnose_service.APPROXIMATION_NOTICE,
    )


@router.get("/{session_id}/recommendations", response_model=RecommendationsResponse)
def recommendations(
    session_id: str,
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
    user_id: str | None = Depends(get_optional_current_user_id),
    session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> RecommendationsResponse:
    session = _get_session_or_404(engine, session_id, user_id, session_token)
    recs = recommendation_service.recommend_policies(session["input_payload"], session["diagnosis_result"], store)
    other_policies = recommendation_service.list_other_policies(session["input_payload"], store)
    return RecommendationsResponse(
        recommendations=[RecommendationItem(**r) for r in recs],
        other_policies=[OtherPolicyItem(**p) for p in other_policies],
    )


@router.get("/{session_id}/explanation", response_model=ExplanationResponse)
def explanation(
    session_id: str,
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
    user_id: str | None = Depends(get_optional_current_user_id),
    session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> ExplanationResponse:
    session = _get_session_or_404(engine, session_id, user_id, session_token)

    if session.get("explanation_text"):
        # docs/06: "응답은 세션에 캐싱해 동일 세션 재요청 시 재호출하지 않음"
        return ExplanationResponse(
            session_id=session_id,
            explanation=session["explanation_text"],
            is_llm_generated=bool(session.get("explanation_is_llm_generated")),
        )

    diagnosis_result = session["diagnosis_result"]
    recs = recommendation_service.recommend_policies(session["input_payload"], diagnosis_result, store)
    text, is_llm_generated = explanation_service.generate_explanation(
        diagnosis_result.get("domain_indices", {}),
        diagnosis_result.get("shap_top3"),
        recs,
        cluster_membership=diagnosis_result.get("cluster_membership"),
        risk_probability=diagnosis_result.get("risk_probability"),
    )

    with engine.begin() as conn:
        conn.execute(
            db.citizen_sessions.update()
            .where(db.citizen_sessions.c.session_id == session_id)
            .values(explanation_text=text, explanation_is_llm_generated=is_llm_generated)
        )

    return ExplanationResponse(session_id=session_id, explanation=text, is_llm_generated=is_llm_generated)


@router.get("/{session_id}/history", response_model=HistoryResponse)
def history(
    session_id: str,
    engine: Engine = Depends(get_engine),
    user_id: str | None = Depends(get_optional_current_user_id),
    session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> HistoryResponse:
    session = _get_session_or_404(engine, session_id, user_id, session_token)
    return HistoryResponse(
        session_id=session_id,
        history=[HistoryEntry(created_at=str(session["created_at"]), diagnosis_result=session["diagnosis_result"])],
        note=(
            "현재는 session_id 기준 단일 진단만 저장됩니다. 재방문 시 변화 추이(docs/09)를 "
            "보려면 개인별 식별자(실명인증 연동 등)로 세션을 연결하는 별도 설계가 필요합니다."
        ),
    )
