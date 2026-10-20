"""O concurso principal do candidato e a contagem regressiva.

O painel pede "concurso principal" e "dias restantes para a prova". Os dois
dependem de uma declaração que a plataforma nunca pediu: qual concurso o
candidato está perseguindo.

A regra que governa este serviço é a mesma da barra de FOCO da batalha:
**sem dado real não há número.** Se o candidato não escolheu concurso, não há
contagem. Se o edital não trouxe data de prova, não há contagem — e a tela diz
o motivo em vez de exibir um número inventado ou um traço sem explicação.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.audit import AuditAction
from app.models.catalog import Competition, CompetitionEditorialStatus
from app.models.user import Profile, User
from app.services.audit import AuditService
from app.services.auth import RequestContext


@dataclass(frozen=True, slots=True)
class StudyFocus:
    """O foco do candidato, ou o motivo de não haver um."""

    competition_public_id: str | None = None
    competition_name: str | None = None
    organization_name: str | None = None
    exam_date: date | None = None
    #: ``None`` quando não há data. Negativo nunca: prova que já passou é zero.
    days_remaining: int | None = None
    #: Por que não há contagem. A tela mostra isto no lugar do número.
    unavailable_reason: str | None = None


def _days_until(exam_date: date | None, *, today: date) -> int | None:
    if exam_date is None:
        return None
    return max(0, (exam_date - today).days)


class StudyFocusService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def _profile(self, user: User) -> Profile:
        found = (
            await self.session.execute(select(Profile).where(Profile.user_id == user.id))
        ).scalar_one_or_none()
        if found is None:
            found = Profile(user_id=user.id)
            self.session.add(found)
            await self.session.flush()
        return found

    async def _competition(self, public_id: str) -> Competition:
        found = (
            await self.session.execute(
                select(Competition).where(Competition.public_id == public_id)
            )
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Concurso não encontrado.")
        return found

    async def get(self, user: User, *, today: date | None = None) -> StudyFocus:
        profile = await self._profile(user)
        if profile.primary_competition_id is None:
            return StudyFocus(unavailable_reason="Nenhum concurso principal escolhido.")

        competition = (
            await self.session.execute(
                select(Competition).where(Competition.id == profile.primary_competition_id)
            )
        ).scalar_one_or_none()
        if competition is None:
            # O concurso foi removido do catálogo depois da escolha.
            return StudyFocus(unavailable_reason="O concurso escolhido não está mais disponível.")

        days = _days_until(competition.exam_date, today=today or date.today())
        return StudyFocus(
            competition_public_id=competition.public_id,
            competition_name=competition.name,
            organization_name=competition.organization.name if competition.organization else None,
            exam_date=competition.exam_date,
            days_remaining=days,
            unavailable_reason=(
                None if days is not None else "O edital ainda não trouxe a data da prova."
            ),
        )

    async def set_primary(
        self,
        user: User,
        context: RequestContext,
        *,
        competition_public_id: str | None,
    ) -> StudyFocus:
        """Escolhe (ou abandona) o concurso principal.

        Só concurso **publicado** pode ser escolhido: deixar o candidato se
        prender a uma ficha ainda em rascunho exibiria dado que a equipe nem
        terminou de revisar.
        """
        profile = await self._profile(user)

        if competition_public_id is None:
            profile.primary_competition_id = None
        else:
            competition = await self._competition(competition_public_id)
            if not competition.is_published:
                raise ValidationError(
                    "Esse concurso ainda não foi publicado.",
                    code="competition_not_published",
                )
            if competition.editorial_status == CompetitionEditorialStatus.ARCHIVED:
                raise ValidationError("Esse concurso foi arquivado.", code="competition_archived")
            profile.primary_competition_id = competition.id

        await self.audit.record(
            AuditAction.USER_PROFILE_UPDATED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="study_focus",
            resource_id=user.public_id,
            meta={"competition": competition_public_id},
        )
        await self.session.commit()
        return await self.get(user)
