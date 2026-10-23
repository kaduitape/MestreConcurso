"""Baralho oficial por tópico: curadoria, publicação e assinatura.

Três invariantes governam este serviço, e todas as três existem porque um cartão
errado é pior do que cartão nenhum — a repetição espaçada **grava** o verso na
memória de quem estuda.

**Nada chega a candidato antes de uma pessoa.** O baralho nasce ``DRAFT`` e só
muda para ``PUBLISHED`` por uma ação humana, que passa pelo portão de auditoria
da Fase 3 e fica registrada com nome e hora. Enquanto é rascunho, nenhum
candidato o enxerga — nem por assinatura, porque a visibilidade cobra o estado
publicado.

**Cartão de IA só existe com citação conferida.** A geração reutiliza a mesma
peneira do baralho pessoal (``FlashcardService.generate_candidates``): o que o
modelo escreve sem respaldo literal no material é descartado, não guardado com
aviso.

**Ninguém recebe baralho por decisão da plataforma.** O candidato assina. É o
que impede que um baralho de "Controle de Constitucionalidade" caia na fila de
quem estuda para um concurso de saúde municipal — e é a diferença entre um
cartão global com escopo e um cartão global solto no banco.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.audit import AuditAction
from app.models.catalog import Competition, Subject, Topic
from app.models.deck import DeckSourceKind, DeckStatus, DeckSubscription, OfficialDeck
from app.models.flashcard import CardOrigin, Flashcard
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.user import Profile, User
from app.repositories.flashcard import FlashcardRepository
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.flashcards import FlashcardService, front_checksum

logger = get_logger(__name__)

#: Teto de cartões por baralho. Acima disso ninguém revisa um tópico só: o
#: baralho deixa de ser estudo de um assunto e vira acervo.
MAX_CARDS_PER_DECK = 120


@dataclass(frozen=True, slots=True)
class DeckView:
    """O baralho com as contagens **derivadas** dos cartões e das assinaturas."""

    deck: OfficialDeck
    active_cards: int = 0
    inactive_cards: int = 0
    ai_cards: int = 0
    subscribers: int = 0


@dataclass(frozen=True, slots=True)
class DeckGenerationResult:
    created: list[Flashcard] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)
    #: Cartões iguais a um que o baralho já tem — inclusive a um desativado.
    duplicated: int = 0
    skipped_reason: str | None = None
    model: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True, slots=True)
class DeckCatalogue:
    """O que o candidato pode assinar, com o escopo da lista dito em português."""

    items: list[DeckView] = field(default_factory=list)
    subscribed: frozenset[int] = frozenset()
    total: int = 0
    scope: str = ""
    competition_name: str | None = None


class OfficialDeckService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cards = FlashcardRepository(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def get(self, public_id: str) -> OfficialDeck:
        found = (
            await self.session.execute(
                select(OfficialDeck).where(OfficialDeck.public_id == public_id)
            )
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Baralho não encontrado.")
        return found

    async def _subscriber_counts(self, deck_ids: Sequence[int]) -> dict[int, int]:
        if not deck_ids:
            return {}
        rows = (
            await self.session.execute(
                select(DeckSubscription.deck_id, func.count())
                .where(DeckSubscription.deck_id.in_(deck_ids))
                .group_by(DeckSubscription.deck_id)
            )
        ).all()
        return {int(row[0]): int(row[1]) for row in rows}

    async def _views(self, decks: Sequence[OfficialDeck]) -> list[DeckView]:
        """Contagens de uma vez, derivadas — nunca colunas de contador."""
        ids = [deck.id for deck in decks]
        if not ids:
            return []
        rows = (
            await self.session.execute(
                select(Flashcard.deck_id, Flashcard.is_active, Flashcard.origin, func.count())
                .where(Flashcard.deck_id.in_(ids))
                .group_by(Flashcard.deck_id, Flashcard.is_active, Flashcard.origin)
            )
        ).all()
        ativos: dict[int, int] = {}
        inativos: dict[int, int] = {}
        por_ia: dict[int, int] = {}
        for deck_id, is_active, origin, total in rows:
            if deck_id is None:
                continue
            chave = int(deck_id)
            if is_active:
                ativos[chave] = ativos.get(chave, 0) + int(total)
                if origin == CardOrigin.AI:
                    por_ia[chave] = por_ia.get(chave, 0) + int(total)
            else:
                inativos[chave] = inativos.get(chave, 0) + int(total)

        assinantes = await self._subscriber_counts(ids)
        return [
            DeckView(
                deck=deck,
                active_cards=ativos.get(deck.id, 0),
                inactive_cards=inativos.get(deck.id, 0),
                ai_cards=por_ia.get(deck.id, 0),
                subscribers=assinantes.get(deck.id, 0),
            )
            for deck in decks
        ]

    async def view(self, deck: OfficialDeck) -> DeckView:
        views = await self._views([deck])
        return views[0]

    async def list_decks(
        self, *, limit: int, offset: int, status: str | None = None, topic_id: int | None = None
    ) -> tuple[list[DeckView], int]:
        base = select(OfficialDeck).order_by(OfficialDeck.id.desc())
        contagem = select(func.count()).select_from(OfficialDeck)
        if status:
            base = base.where(OfficialDeck.status == status)
            contagem = contagem.where(OfficialDeck.status == status)
        if topic_id is not None:
            base = base.where(OfficialDeck.topic_id == topic_id)
            contagem = contagem.where(OfficialDeck.topic_id == topic_id)
        decks = list((await self.session.execute(base.limit(limit).offset(offset))).scalars().all())
        total = int((await self.session.execute(contagem)).scalar_one())
        return await self._views(decks), total

    async def deck_cards(self, deck: OfficialDeck) -> Sequence[Flashcard]:
        """Todos os cartões do baralho, inclusive os desativados pela curadoria."""
        return await self.cards.in_deck(deck.id)

    # ------------------------------------------------------------------ #
    # Curadoria
    # ------------------------------------------------------------------ #
    async def _topic(self, public_id: str) -> Topic:
        found = (
            await self.session.execute(select(Topic).where(Topic.public_id == public_id))
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Tópico não encontrado.")
        return found

    async def create(
        self,
        actor: User,
        context: RequestContext,
        *,
        topic_public_id: str,
        title: str | None = None,
        description: str | None = None,
        source_kind: str = DeckSourceKind.EDITORIAL,
        source_ref: str | None = None,
    ) -> OfficialDeck:
        topic = await self._topic(topic_public_id)
        existente = (
            await self.session.execute(
                select(OfficialDeck).where(OfficialDeck.topic_id == topic.id)
            )
        ).scalar_one_or_none()
        if existente is not None:
            raise ConflictError(
                f"O tópico já tem um baralho oficial ({existente.status}). "
                "Edite o que existe em vez de criar um segundo.",
                code="deck_already_exists",
                details={"deck": existente.public_id, "status": existente.status},
            )

        deck = OfficialDeck(
            topic_id=topic.id,
            subject_id=topic.subject_id,
            title=(title or topic.name).strip()[:200],
            description=description.strip() if description else None,
            status=DeckStatus.DRAFT,
            source_kind=source_kind,
            source_ref=source_ref,
            created_by_user_id=actor.id,
        )
        self.session.add(deck)
        await self.audit.record(
            AuditAction.DECK_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="official_deck",
            resource_id=deck.public_id,
            meta={"topic": topic.public_id},
        )
        await self.session.commit()
        return await self.get(deck.public_id)

    def _guard_editable(self, deck: OfficialDeck) -> None:
        if deck.status == DeckStatus.ARCHIVED:
            raise ConflictError(
                "Este baralho está arquivado. Reabra-o antes de mexer nos cartões.",
                code="deck_archived",
            )

    async def _guard_room(self, deck: OfficialDeck, *, incoming: int = 1) -> None:
        total = len(await self.cards.in_deck(deck.id))
        if total + incoming > MAX_CARDS_PER_DECK:
            raise ConflictError(
                f"O baralho chegou ao limite de {MAX_CARDS_PER_DECK} cartões.",
                code="deck_full",
            )

    async def add_card(
        self,
        actor: User,
        context: RequestContext,
        deck: OfficialDeck,
        *,
        front: str,
        back: str,
        hint: str | None = None,
        tags: list[str] | None = None,
        origin: str = CardOrigin.EDITORIAL,
        source_quote: str | None = None,
        source_document: str | None = None,
        source_page: int | None = None,
        model_slug: str | None = None,
        prompt_version: str | None = None,
        commit: bool = True,
    ) -> Flashcard:
        self._guard_editable(deck)
        cleaned_front = front.strip()
        cleaned_back = back.strip()
        if len(cleaned_front) < 3 or len(cleaned_back) < 1:
            raise ValidationError("O cartão precisa de frente e verso.", code="invalid_flashcard")
        await self._guard_room(deck)

        checksum = front_checksum(cleaned_front)
        if await self.cards.deck_card_by_checksum(deck.id, checksum) is not None:
            raise ConflictError(
                "Este baralho já tem um cartão com esta frente.", code="duplicate_flashcard"
            )

        card = Flashcard(
            user_id=None,
            deck_id=deck.id,
            subject_id=deck.subject_id,
            topic_id=deck.topic_id,
            front=cleaned_front,
            back=cleaned_back,
            hint=hint.strip() if hint else None,
            tags=tags or [],
            origin=origin,
            source_quote=source_quote,
            source_document=source_document,
            source_page=source_page,
            model_slug=model_slug,
            prompt_version=prompt_version,
            checksum=checksum,
        )
        self.session.add(card)
        if commit:
            await self.session.commit()
        return card

    async def generate(
        self,
        actor: User,
        context: RequestContext,
        deck: OfficialDeck,
        *,
        material: str,
        quantity: int = 5,
        source_document: str | None = None,
        source_page: int | None = None,
    ) -> DeckGenerationResult:
        """Gera cartões de IA **dentro do rascunho**, com citação conferida.

        O baralho não é publicado aqui, nem quando todos os cartões passam pela
        conferência: a citação prova que o verso tem respaldo no material, não
        que o material está certo. Quem decide isso é pessoa, na publicação.
        """
        self._guard_editable(deck)
        batch = await FlashcardService(self.session).generate_candidates(
            material=material, quantity=quantity
        )

        criados: list[Flashcard] = []
        repetidos = 0
        for draft in batch.cards:
            try:
                card = await self.add_card(
                    actor,
                    context,
                    deck,
                    front=draft.front,
                    back=draft.back,
                    hint=draft.hint,
                    origin=CardOrigin.AI,
                    source_quote=draft.quote,
                    source_document=source_document,
                    source_page=source_page,
                    model_slug=batch.model_slug,
                    prompt_version=batch.prompt_version,
                    commit=False,
                )
            except ConflictError as exc:
                if getattr(exc, "code", None) == "duplicate_flashcard":
                    repetidos += 1
                    continue
                # Baralho cheio ou arquivado interrompe: insistir só repetiria o erro.
                await self.session.commit()
                raise
            criados.append(card)

        await self.audit.record(
            AuditAction.DECK_GENERATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="official_deck",
            resource_id=deck.public_id,
            meta={
                "created": len(criados),
                "discarded": len(batch.discarded),
                "duplicated": repetidos,
                "model": batch.model_slug,
            },
        )
        await self.session.commit()

        logger.info(
            "deck.generated",
            deck=deck.public_id,
            created=len(criados),
            discarded=len(batch.discarded),
            duplicated=repetidos,
        )
        return DeckGenerationResult(
            created=criados,
            discarded=batch.discarded,
            duplicated=repetidos,
            skipped_reason=batch.skipped_reason,
            model=batch.model_slug,
            prompt_version=batch.prompt_version,
        )

    async def set_card_active(
        self,
        actor: User,
        context: RequestContext,
        deck: OfficialDeck,
        card_public_id: str,
        *,
        is_active: bool,
    ) -> Flashcard:
        """Tira ou devolve um cartão à circulação.

        Desativar não apaga: o cartão sai da fila de quem assinou e o histórico
        de revisão de todos continua de pé. É a ferramenta da curadoria para o
        cartão que o portão não pega — redação ruim, verso incompleto, recorte
        infeliz da citação.
        """
        no_baralho = await self.cards.in_deck(deck.id)
        card = next((item for item in no_baralho if item.public_id == card_public_id), None)
        if card is None:
            raise NotFoundError("Cartão não encontrado neste baralho.")
        card.is_active = is_active
        await self.audit.record(
            AuditAction.DECK_CARD_REVIEWED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="flashcard",
            resource_id=card.public_id,
            meta={"deck": deck.public_id, "is_active": is_active},
        )
        await self.session.commit()
        return card

    async def publish(
        self, actor: User, context: RequestContext, deck: OfficialDeck
    ) -> OfficialDeck:
        """Publica o baralho — a ação que o torna visível para quem assinar."""
        from app.services.content_audit import ContentAuditService

        ativos = await self.cards.in_deck(deck.id, only_active=True)
        if not ativos:
            raise ValidationError(
                "Revise e mantenha ao menos um cartão ativo antes de publicar.",
                code="deck_without_cards",
            )
        # O portão roda **antes** de mudar o estado: baralho barrado não fica
        # publicado nem por um instante, e o laudo é gravado de todo jeito.
        await ContentAuditService(self.session).gate_deck(deck, actor=actor, cards=len(ativos))

        deck.status = DeckStatus.PUBLISHED
        deck.published_at = datetime.now(UTC)
        deck.published_by_user_id = actor.id
        deck.archived_at = None
        await self.audit.record(
            AuditAction.DECK_PUBLISHED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="official_deck",
            resource_id=deck.public_id,
            meta={"cards": len(ativos)},
        )
        await self.session.commit()
        return await self.get(deck.public_id)

    async def archive(
        self, actor: User, context: RequestContext, deck: OfficialDeck
    ) -> OfficialDeck:
        """Tira o baralho de circulação sem apagar cartão nem memória de ninguém."""
        deck.status = DeckStatus.ARCHIVED
        deck.archived_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.DECK_ARCHIVED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="official_deck",
            resource_id=deck.public_id,
        )
        await self.session.commit()
        return await self.get(deck.public_id)

    async def reopen(
        self, actor: User, context: RequestContext, deck: OfficialDeck
    ) -> OfficialDeck:
        """Devolve um baralho arquivado ao rascunho, para nova curadoria."""
        if deck.status != DeckStatus.ARCHIVED:
            raise ConflictError("Este baralho não está arquivado.", code="deck_not_archived")
        deck.status = DeckStatus.DRAFT
        deck.archived_at = None
        deck.published_at = None
        deck.published_by_user_id = None
        await self.audit.record(
            AuditAction.DECK_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="official_deck",
            resource_id=deck.public_id,
            meta={"reopened": True},
        )
        await self.session.commit()
        return await self.get(deck.public_id)

    # ------------------------------------------------------------------ #
    # O lado do candidato
    # ------------------------------------------------------------------ #
    async def _primary_competition(self, user: User) -> Competition | None:
        profile = (
            await self.session.execute(select(Profile).where(Profile.user_id == user.id))
        ).scalar_one_or_none()
        if profile is None or profile.primary_competition_id is None:
            return None
        return (
            await self.session.execute(
                select(Competition).where(Competition.id == profile.primary_competition_id)
            )
        ).scalar_one_or_none()

    async def _subscribed_ids(self, user: User) -> frozenset[int]:
        rows = (
            await self.session.execute(
                select(DeckSubscription.deck_id).where(DeckSubscription.user_id == user.id)
            )
        ).scalars()
        return frozenset(int(item) for item in rows)

    async def catalogue(self, user: User, *, limit: int = 100, offset: int = 0) -> DeckCatalogue:
        """Os baralhos publicados dos tópicos do concurso principal do candidato.

        Sem concurso principal escolhido não há escopo: a lista mostra o que ele
        já assinou e **diz** que está assim, em vez de despejar todo baralho
        publicado da plataforma como se fosse recomendação.
        """
        assinados = await self._subscribed_ids(user)
        competition = await self._primary_competition(user)

        base = select(OfficialDeck).where(OfficialDeck.status == DeckStatus.PUBLISHED)
        if competition is not None:
            topicos = (
                select(NoticeTopic.topic_id)
                .join(NoticeSubject, NoticeTopic.notice_subject_id == NoticeSubject.id)
                .join(Notice, NoticeSubject.notice_id == Notice.id)
                .where(Notice.competition_id == competition.id)
            )
            base = base.where(OfficialDeck.topic_id.in_(topicos))
            escopo = f"Baralhos dos tópicos do edital de {competition.name}."
        else:
            base = base.where(OfficialDeck.id.in_(assinados or {-1}))
            escopo = (
                "Você ainda não escolheu um concurso principal: a lista traz só os "
                "baralhos que você já assinou."
            )

        total = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(base.order_by(None).subquery())
                )
            ).scalar_one()
        )
        decks = list(
            (
                await self.session.execute(
                    base.order_by(OfficialDeck.title).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return DeckCatalogue(
            items=await self._views(decks),
            subscribed=assinados,
            total=total,
            scope=escopo,
            competition_name=competition.name if competition else None,
        )

    async def subscribe(self, user: User, public_id: str) -> OfficialDeck:
        deck = await self.get(public_id)
        if deck.status != DeckStatus.PUBLISHED:
            # Rascunho não é conteúdo: ele existe justamente por não ter passado
            # pela conferência ainda.
            raise NotFoundError("Baralho não encontrado.")
        existente = (
            await self.session.execute(
                select(DeckSubscription).where(
                    DeckSubscription.user_id == user.id, DeckSubscription.deck_id == deck.id
                )
            )
        ).scalar_one_or_none()
        if existente is None:
            self.session.add(DeckSubscription(user_id=user.id, deck_id=deck.id))
            await self.session.commit()
        return deck

    async def unsubscribe(self, user: User, public_id: str) -> OfficialDeck:
        """Sai do baralho. O estado de memória de cada cartão **permanece**.

        Quem volta meses depois reencontra os intervalos onde parou, em vez de
        recomeçar do zero por ter saído de um baralho.
        """
        deck = await self.get(public_id)
        await self.session.execute(
            delete(DeckSubscription).where(
                DeckSubscription.user_id == user.id, DeckSubscription.deck_id == deck.id
            )
        )
        await self.session.commit()
        return deck


async def deck_for_topic(session: AsyncSession, topic_id: int) -> OfficialDeck | None:
    """O baralho oficial de um tópico, em qualquer estado. Um tópico tem no máximo um."""
    return (
        await session.execute(select(OfficialDeck).where(OfficialDeck.topic_id == topic_id))
    ).scalar_one_or_none()


async def subject_of(session: AsyncSession, subject_id: int | None) -> Subject | None:
    if subject_id is None:
        return None
    return (
        await session.execute(select(Subject).where(Subject.id == subject_id))
    ).scalar_one_or_none()
