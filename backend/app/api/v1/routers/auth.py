"""Endpoints de autenticação."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentPrincipal, DbSession, RequestCtx, rate_limit
from app.core.config import settings
from app.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TokenPair,
)
from app.schemas.common import MessageResponse
from app.schemas.user import MeRead
from app.services.auth import AuthService, RequestContext

router = APIRouter(prefix="/auth", tags=["auth"])

_GENERIC_EMAIL_RESPONSE = (
    "Se houver uma conta com este e-mail, enviaremos as instruções em instantes."
)


def _context(base: RequestContext, device_label: str | None = None) -> RequestContext:
    return RequestContext(
        ip_address=base.ip_address, user_agent=base.user_agent, device_label=device_label
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageResponse,
    summary="Criar conta",
    dependencies=[Depends(rate_limit(settings.rate_limit_auth, scope="auth:register"))],
)
async def register(payload: RegisterRequest, db: DbSession, ctx: RequestCtx) -> MessageResponse:
    service = AuthService(db)
    user = await service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        context=ctx,
    )
    return MessageResponse(
        message="Conta criada. Confirme seu e-mail para ativar o acesso.",
        detail={"email": user.email},
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Confirmar e-mail",
    dependencies=[Depends(rate_limit(settings.rate_limit_auth, scope="auth:verify"))],
)
async def verify_email(
    payload: EmailVerificationRequest, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await AuthService(db).verify_email(payload.token, ctx)
    return MessageResponse(message="E-mail confirmado. Você já pode entrar.")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Reenviar confirmação de e-mail",
    dependencies=[Depends(rate_limit(settings.rate_limit_password_reset, scope="auth:resend"))],
)
async def resend_verification(
    payload: ResendVerificationRequest, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await AuthService(db).resend_verification(payload.email, ctx)
    return MessageResponse(message=_GENERIC_EMAIL_RESPONSE)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Entrar",
    dependencies=[Depends(rate_limit(settings.rate_limit_auth, scope="auth:login"))],
)
async def login(payload: LoginRequest, db: DbSession, ctx: RequestCtx) -> TokenPair:
    _, tokens = await AuthService(db).login(
        email=payload.email,
        password=payload.password,
        context=_context(ctx, payload.device_label),
    )
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        session_id=tokens.session.public_id,
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Renovar tokens (rotação com detecção de reuso)",
    dependencies=[Depends(rate_limit("60/minute", scope="auth:refresh"))],
)
async def refresh(payload: RefreshRequest, db: DbSession, ctx: RequestCtx) -> TokenPair:
    tokens = await AuthService(db).refresh(payload.refresh_token, ctx)
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        session_id=tokens.session.public_id,
    )


@router.post("/logout", response_model=MessageResponse, summary="Sair deste dispositivo")
async def logout(principal: CurrentPrincipal, db: DbSession, ctx: RequestCtx) -> MessageResponse:
    await AuthService(db).logout(principal.user, principal.session.public_id, ctx)
    return MessageResponse(message="Sessão encerrada.")


@router.post("/logout-all", response_model=MessageResponse, summary="Sair de todos os dispositivos")
async def logout_all(
    principal: CurrentPrincipal, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    revoked = await AuthService(db).logout_all(principal.user, ctx)
    return MessageResponse(
        message="Todas as sessões foram encerradas.", detail={"revoked_sessions": revoked}
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Solicitar redefinição de senha",
    dependencies=[Depends(rate_limit(settings.rate_limit_password_reset, scope="auth:forgot"))],
)
async def forgot_password(
    payload: PasswordResetRequest, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await AuthService(db).request_password_reset(payload.email, ctx)
    return MessageResponse(message=_GENERIC_EMAIL_RESPONSE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Definir nova senha com token",
    dependencies=[Depends(rate_limit(settings.rate_limit_password_reset, scope="auth:reset"))],
)
async def reset_password(
    payload: PasswordResetConfirm, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await AuthService(db).reset_password(payload.token, payload.new_password, ctx)
    return MessageResponse(
        message="Senha redefinida. Todas as sessões anteriores foram encerradas."
    )


@router.get("/me", response_model=MeRead, summary="Dados da conta autenticada")
async def me(principal: CurrentPrincipal) -> MeRead:
    return MeRead.from_user(principal.user)
