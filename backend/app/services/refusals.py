"""Gravar a recusa por falta de acervo — em sessão própria, por necessidade.

A recusa **levanta um erro**. O erro sobe pela API, e a transação de quem
chamou é desfeita. Gravar a recusa na mesma sessão seria gravá-la para em
seguida perdê-la junto com o rollback — exatamente o defeito que ``record_usage``
teve de resolver para o gasto com IA.

Por isso aqui se abre uma sessão própria, se grava e se confirma. E, como lá, a
falha ao gravar **não derruba** o fluxo: o candidato precisa receber a recusa
explicada, não um erro de contabilidade. O log é o que denuncia a lacuna.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.models.refusal import ResourceRefusal
from app.models.user import Profile

logger = get_logger(__name__)


async def record_refusal(
    *,
    kind: str,
    reason_code: str,
    detail: str,
    user_id: int | None = None,
    competition_id: int | None = None,
    subject_id: int | None = None,
    topic_id: int | None = None,
    requested: int | None = None,
    available: int | None = None,
    variant: str | None = None,
) -> None:
    """Registra uma recusa por falta de acervo.

    ``competition_id`` é resolvido aqui a partir do concurso principal do
    candidato quando não vem informado — na sessão própria, nunca na de quem
    chamou, que está a caminho do rollback.
    """
    factory = get_session_factory()
    try:
        async with factory() as session:
            alvo = competition_id
            if alvo is None and user_id is not None:
                alvo = (
                    await session.execute(
                        select(Profile.primary_competition_id).where(Profile.user_id == user_id)
                    )
                ).scalar_one_or_none()
            session.add(
                ResourceRefusal(
                    kind=kind,
                    reason_code=reason_code,
                    detail=detail,
                    variant=variant,
                    user_id=user_id,
                    competition_id=alvo,
                    subject_id=subject_id,
                    topic_id=topic_id,
                    requested=requested,
                    available=available,
                )
            )
            await session.commit()
    except Exception as exc:  # pragma: no cover - contabilidade não derruba o fluxo
        logger.warning("refusal.record_failed", kind=kind, reason=reason_code, error=str(exc))
