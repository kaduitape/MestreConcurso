"""Endpoints da conta do próprio usuário."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentPrincipal, DbSession, RequestCtx, rate_limit
from app.core.errors import InvalidCredentialsError
from app.core.security import verify_password
from app.schemas.auth import PasswordChangeRequest, SessionInfo
from app.schemas.common import MessageResponse
from app.schemas.user import MeRead, ProfileUpdate, UserUpdate
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


class AccountUpdateRequest(UserUpdate):
    """Atualiza conta e perfil em uma única chamada."""

    profile: ProfileUpdate = Field(default_factory=ProfileUpdate)


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirmation: str = Field(description='Digite "EXCLUIR" para confirmar')


@router.get("/me", response_model=MeRead, summary="Meus dados")
async def get_me(principal: CurrentPrincipal) -> MeRead:
    return MeRead.from_user(principal.user)


@router.patch("/me", response_model=MeRead, summary="Atualizar conta e perfil")
async def update_me(
    payload: AccountUpdateRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    ctx: RequestCtx,
) -> MeRead:
    user = await UserService(db).update_account(
        principal.user,
        full_name=payload.full_name,
        profile_data=payload.profile.model_dump(exclude_unset=True),
        context=ctx,
    )
    return MeRead.from_user(user)


@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    summary="Trocar senha",
    dependencies=[Depends(rate_limit("10/hour", scope="users:change-password"))],
)
async def change_password(
    payload: PasswordChangeRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    ctx: RequestCtx,
) -> MessageResponse:
    await AuthService(db).change_password(
        principal.user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        context=ctx,
        keep_session_id=principal.session.id,
    )
    return MessageResponse(
        message="Senha alterada. As demais sessões foram encerradas por segurança."
    )


@router.get("/me/sessions", response_model=list[SessionInfo], summary="Dispositivos conectados")
async def list_sessions(principal: CurrentPrincipal, db: DbSession) -> list[SessionInfo]:
    sessions = await AuthService(db).sessions.list_active(principal.user.id)
    return [
        SessionInfo.model_validate(item).model_copy(
            update={"is_current": item.id == principal.session.id}
        )
        for item in sessions
    ]


@router.delete(
    "/me/sessions/{session_public_id}",
    response_model=MessageResponse,
    summary="Encerrar um dispositivo",
)
async def revoke_session(
    session_public_id: str,
    principal: CurrentPrincipal,
    db: DbSession,
    ctx: RequestCtx,
) -> MessageResponse:
    await AuthService(db).revoke_session(principal.user, session_public_id, ctx)
    return MessageResponse(message="Dispositivo desconectado.")


@router.get(
    "/me/export",
    summary="Exportar meus dados (LGPD)",
    dependencies=[Depends(rate_limit("5/hour", scope="users:export"))],
)
async def export_data(principal: CurrentPrincipal, db: DbSession, ctx: RequestCtx) -> Response:
    import json

    payload = await UserService(db).export_data(principal.user, ctx)
    filename = f"meus-dados-{principal.user.public_id}.json"
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Excluir minha conta (LGPD)",
)
async def delete_account(
    principal: CurrentPrincipal,
    db: DbSession,
    ctx: RequestCtx,
    payload: AccountDeleteRequest = Body(...),
) -> MessageResponse:
    if payload.confirmation.strip().upper() != "EXCLUIR":
        raise InvalidCredentialsError("Confirmação inválida.", code="invalid_confirmation")
    if not verify_password(payload.password, principal.user.password_hash):
        raise InvalidCredentialsError("A senha informada está incorreta.")
    await UserService(db).delete_account(principal.user, ctx)
    return MessageResponse(message="Conta excluída. Seus dados pessoais foram anonimizados.")
