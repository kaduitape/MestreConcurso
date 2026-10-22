"""Árvore de conhecimento: o conteúdo programático do edital com o estado real.

O serviço só **coleta**. A derivação de estado é pura e vive em
``app/domain/game/knowledge_tree.py``.

A espinha da árvore é o **conteúdo programático do edital analisado** do
concurso principal do candidato — ``notice_subjects`` → ``notice_topics``, na
ordem em que o edital escreveu. Não é a hierarquia do catálogo: o catálogo é
nosso, o edital é da banca, e é do edital que o candidato vai ser cobrado.

A medição de cada tópico vem do tópico canônico vinculado **e dos subtópicos
dele**: se o edital diz "Crase" e o catálogo tem três subtópicos de crase, uma
resposta em qualquer um dos três conta para o ramo "Crase". O caminho
materializado (``topics.path``) é o que permite fazer isso em uma consulta por
sinal, em vez de uma por tópico.

Cinco consultas, uma por sinal: respostas, questões cadastradas, aulas (com o
progresso real do candidato), mapas mentais e cartões com suas revisões. Nenhum
contador paralelo — tudo derivado na leitura, como o resto da plataforma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.game.knowledge_tree import (
    Evidence,
    SubjectInput,
    SubjectNode,
    TopicInput,
    TreeSummary,
    attention_order,
    build,
    summarize,
)
from app.models.catalog import Competition, Subject, Topic
from app.models.flashcard import Flashcard, FlashcardReview
from app.models.mindmap import MindMap
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.question import Question, QuestionAttempt
from app.models.training import TrainingLesson, TrainingProgress, TrainingProgressStatus
from app.models.user import Profile, User


@dataclass(frozen=True, slots=True)
class KnowledgeTree:
    """A árvore pronta, ou o motivo de não haver uma."""

    competition_public_id: str | None = None
    competition_name: str | None = None
    notice_title: str | None = None
    subjects: tuple[SubjectNode, ...] = ()
    summary: TreeSummary = field(default_factory=TreeSummary)
    #: Tópicos que pedem atenção primeiro, já sem as lacunas da plataforma.
    attention: tuple[str, ...] = ()
    #: Por que não há árvore. A tela mostra isto no lugar dela.
    unavailable_reason: str | None = None


class KnowledgeTreeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def tree(self, user: User) -> KnowledgeTree:
        profile = (
            await self.session.execute(select(Profile).where(Profile.user_id == user.id))
        ).scalar_one_or_none()
        if profile is None or profile.primary_competition_id is None:
            return KnowledgeTree(
                unavailable_reason=(
                    "Escolha seu concurso principal para a árvore nascer do edital dele. "
                    "Sem concurso, não há conteúdo programático de onde tirar os ramos."
                )
            )

        competition = (
            await self.session.execute(
                select(Competition).where(Competition.id == profile.primary_competition_id)
            )
        ).scalar_one_or_none()
        if competition is None:
            return KnowledgeTree(
                unavailable_reason="O concurso principal não está mais no catálogo."
            )

        notice = await self._analysed_notice(competition.id)
        if notice is None:
            return KnowledgeTree(
                competition_public_id=competition.public_id,
                competition_name=competition.name,
                unavailable_reason=(
                    "O edital deste concurso ainda não foi analisado. A árvore é o "
                    "conteúdo programático do edital — sem a análise, ela seria um "
                    "desenho sem fonte."
                ),
            )

        disciplinas = list(
            (
                await self.session.execute(
                    select(NoticeSubject)
                    .where(NoticeSubject.notice_id == notice.id)
                    .order_by(NoticeSubject.order_index)
                )
            )
            .scalars()
            .all()
        )
        # Uma consulta para todos os tópicos do edital, não uma por disciplina:
        # um edital com quinze matérias faria quinze idas ao banco à toa.
        topicos_por_disciplina: dict[int, list[NoticeTopic]] = {
            materia.id: [] for materia in disciplinas
        }
        if disciplinas:
            for topico in (
                (
                    await self.session.execute(
                        select(NoticeTopic)
                        .where(
                            NoticeTopic.notice_subject_id.in_(
                                [materia.id for materia in disciplinas]
                            )
                        )
                        .order_by(NoticeTopic.notice_subject_id, NoticeTopic.order_index)
                    )
                )
                .scalars()
                .all()
            ):
                topicos_por_disciplina[topico.notice_subject_id].append(topico)

        vinculados = {
            topico.topic_id
            for lista in topicos_por_disciplina.values()
            for topico in lista
            if topico.topic_id is not None
        }
        subarvores = await self._subtrees(vinculados)
        alcance = {item for ids in subarvores.values() for item in ids}

        respostas = await self._answers(user, alcance)
        questoes = await self._questions(alcance)
        aulas = await self._lessons(user, alcance)
        mapas = await self._mind_maps(alcance)
        cartoes = await self._cards(user, alcance)
        atividade = await self._last_activity(user, alcance)

        hoje = datetime.now(UTC)
        cores = await self._subject_colors(
            {materia.subject_id for materia in disciplinas if materia.subject_id is not None}
        )

        entradas: list[SubjectInput] = []
        for materia in disciplinas:
            filhos: list[TopicInput] = []
            for topico in topicos_por_disciplina[materia.id]:
                ids = subarvores.get(topico.topic_id or -1, set())
                evidencia = Evidence()
                if ids:
                    answers = sum(respostas.get(item, (0, 0))[0] for item in ids)
                    correct = sum(respostas.get(item, (0, 0))[1] for item in ids)
                    reviews = sum(cartoes.get(item, (0, 0, 0))[1] for item in ids)
                    recalled = sum(cartoes.get(item, (0, 0, 0))[2] for item in ids)
                    ultimo = [atividade[item] for item in ids if item in atividade]
                    evidencia = Evidence(
                        answers=answers,
                        correct=correct,
                        questions_available=sum(questoes.get(item, 0) for item in ids),
                        lessons_available=sum(aulas.get(item, (0, 0))[0] for item in ids),
                        lessons_done=sum(aulas.get(item, (0, 0))[1] for item in ids),
                        mind_maps_available=sum(mapas.get(item, 0) for item in ids),
                        cards=sum(cartoes.get(item, (0, 0, 0))[0] for item in ids),
                        reviews=reviews,
                        recalled=recalled,
                        days_since_activity=(max(0, (hoje - max(ultimo)).days) if ultimo else None),
                    )
                filhos.append(
                    TopicInput(
                        label=topico.raw_label,
                        order=topico.order_index,
                        topic_id=topico.topic_id,
                        # Quantos subtópicos entraram na conta além do próprio nó.
                        descendants=max(0, len(ids) - 1),
                        page_number=topico.page_number,
                        evidence=evidencia,
                    )
                )

            entradas.append(
                SubjectInput(
                    label=materia.raw_label,
                    order=materia.order_index,
                    subject_id=materia.subject_id,
                    color_token=cores.get(materia.subject_id or -1, "subject-especifica"),
                    weight=str(materia.weight) if materia.weight is not None else None,
                    questions_count=materia.questions_count,
                    evidence_level=materia.evidence_level,
                    topics=tuple(filhos),
                )
            )

        arvore = build(entradas)
        return KnowledgeTree(
            competition_public_id=competition.public_id,
            competition_name=competition.name,
            notice_title=notice.title,
            subjects=tuple(arvore),
            summary=summarize(arvore),
            attention=tuple(item.label for item in attention_order(arvore)[:5]),
        )

    # ------------------------------------------------------------------ #
    # Fontes
    # ------------------------------------------------------------------ #
    async def _analysed_notice(self, competition_id: int) -> Notice | None:
        """O edital analisado mais recente. Sem análise, não há programa.

        Mesmo critério do serviço de retificação: edital sem disciplina
        extraída não conta como analisado.
        """
        editais = list(
            (
                await self.session.execute(
                    select(Notice)
                    .where(Notice.competition_id == competition_id)
                    .order_by(Notice.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        for edital in editais:
            total = int(
                (
                    await self.session.execute(
                        select(func.count())
                        .select_from(NoticeSubject)
                        .where(NoticeSubject.notice_id == edital.id)
                    )
                ).scalar_one()
            )
            if total:
                return edital
        return None

    async def _subtrees(self, topic_ids: set[int]) -> dict[int, set[int]]:
        """Para cada tópico vinculado, ele mesmo e os descendentes dele.

        Usa o caminho materializado: uma consulta traz todos os tópicos das
        disciplinas envolvidas e o prefixo do caminho resolve a descendência em
        memória, sem uma consulta recursiva por nó.
        """
        if not topic_ids:
            return {}

        raizes = list(
            (
                await self.session.execute(
                    select(Topic.id, Topic.path, Topic.subject_id).where(Topic.id.in_(topic_ids))
                )
            ).all()
        )
        subject_ids = {int(linha[2]) for linha in raizes}
        todos = list(
            (
                await self.session.execute(
                    select(Topic.id, Topic.path).where(Topic.subject_id.in_(subject_ids))
                )
            ).all()
        )

        resultado: dict[int, set[int]] = {}
        for raiz_id, raiz_path, _ in raizes:
            ids = {int(raiz_id)}
            caminho = str(raiz_path or "")
            if caminho:
                prefixo = f"{caminho}/"
                ids.update(
                    int(linha[0]) for linha in todos if str(linha[1] or "").startswith(prefixo)
                )
            resultado[int(raiz_id)] = ids
        return resultado

    async def _answers(self, user: User, topic_ids: set[int]) -> dict[int, tuple[int, int]]:
        """Respostas e acertos por tópico. Em branco não conta como erro."""
        if not topic_ids:
            return {}
        stmt = (
            select(
                Question.topic_id,
                func.count(),
                func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0),
            )
            .join(Question, Question.id == QuestionAttempt.question_id)
            .where(
                QuestionAttempt.user_id == user.id,
                QuestionAttempt.is_blank.is_(False),
                Question.topic_id.in_(topic_ids),
            )
            .group_by(Question.topic_id)
        )
        return {
            int(linha[0]): (int(linha[1]), int(linha[2]))
            for linha in (await self.session.execute(stmt)).all()
            if linha[0] is not None
        }

    async def _questions(self, topic_ids: set[int]) -> dict[int, int]:
        """Questões publicadas por tópico — o material que existe para treinar."""
        if not topic_ids:
            return {}
        stmt = (
            select(Question.topic_id, func.count())
            .where(Question.topic_id.in_(topic_ids))
            .group_by(Question.topic_id)
        )
        return {
            int(linha[0]): int(linha[1])
            for linha in (await self.session.execute(stmt)).all()
            if linha[0] is not None
        }

    async def _lessons(self, user: User, topic_ids: set[int]) -> dict[int, tuple[int, int]]:
        """Aulas por tópico e quantas o candidato concluiu de verdade."""
        if not topic_ids:
            return {}
        disponiveis = {
            int(linha[0]): int(linha[1])
            for linha in (
                await self.session.execute(
                    select(TrainingLesson.topic_id, func.count())
                    .where(TrainingLesson.topic_id.in_(topic_ids))
                    .group_by(TrainingLesson.topic_id)
                )
            ).all()
            if linha[0] is not None
        }
        concluidas = {
            int(linha[0]): int(linha[1])
            for linha in (
                await self.session.execute(
                    select(TrainingLesson.topic_id, func.count())
                    .join(TrainingProgress, TrainingProgress.lesson_id == TrainingLesson.id)
                    .where(
                        TrainingLesson.topic_id.in_(topic_ids),
                        TrainingProgress.user_id == user.id,
                        TrainingProgress.status == TrainingProgressStatus.COMPLETED,
                    )
                    .group_by(TrainingLesson.topic_id)
                )
            ).all()
            if linha[0] is not None
        }
        return {
            topic_id: (total, concluidas.get(topic_id, 0))
            for topic_id, total in disponiveis.items()
        }

    async def _mind_maps(self, topic_ids: set[int]) -> dict[int, int]:
        if not topic_ids:
            return {}
        stmt = (
            select(MindMap.topic_id, func.count())
            .where(MindMap.topic_id.in_(topic_ids))
            .group_by(MindMap.topic_id)
        )
        return {
            int(linha[0]): int(linha[1])
            for linha in (await self.session.execute(stmt)).all()
            if linha[0] is not None
        }

    async def _cards(self, user: User, topic_ids: set[int]) -> dict[int, tuple[int, int, int]]:
        """Cartões do candidato por tópico, com revisões e acertos de memória."""
        if not topic_ids:
            return {}
        cartoes = {
            int(linha[0]): int(linha[1])
            for linha in (
                await self.session.execute(
                    select(Flashcard.topic_id, func.count())
                    .where(Flashcard.user_id == user.id, Flashcard.topic_id.in_(topic_ids))
                    .group_by(Flashcard.topic_id)
                )
            ).all()
            if linha[0] is not None
        }
        revisoes = {
            int(linha[0]): (int(linha[1]), int(linha[2]))
            for linha in (
                await self.session.execute(
                    select(
                        Flashcard.topic_id,
                        func.count(),
                        # "De novo" é a única nota que significa não lembrou.
                        func.coalesce(
                            func.sum(func.cast(FlashcardReview.rating != "AGAIN", Integer)),
                            0,
                        ),
                    )
                    .join(Flashcard, Flashcard.id == FlashcardReview.flashcard_id)
                    .where(
                        FlashcardReview.user_id == user.id,
                        Flashcard.topic_id.in_(topic_ids),
                    )
                    .group_by(Flashcard.topic_id)
                )
            ).all()
            if linha[0] is not None
        }
        return {
            topic_id: (total, *revisoes.get(topic_id, (0, 0)))
            for topic_id, total in cartoes.items()
        }

    async def _last_activity(self, user: User, topic_ids: set[int]) -> dict[int, datetime]:
        """Atividade mais recente do candidato em cada tópico.

        É o que separa "dominado" de "pede revisão". Entram resposta, revisão
        de cartão e aula aberta — três formas de tocar no assunto.
        """
        if not topic_ids:
            return {}
        fontes: list[tuple[int, datetime]] = []

        for stmt in (
            select(Question.topic_id, func.max(QuestionAttempt.created_at))
            .join(Question, Question.id == QuestionAttempt.question_id)
            .where(QuestionAttempt.user_id == user.id, Question.topic_id.in_(topic_ids))
            .group_by(Question.topic_id),
            select(Flashcard.topic_id, func.max(FlashcardReview.created_at))
            .join(Flashcard, Flashcard.id == FlashcardReview.flashcard_id)
            .where(FlashcardReview.user_id == user.id, Flashcard.topic_id.in_(topic_ids))
            .group_by(Flashcard.topic_id),
            select(TrainingLesson.topic_id, func.max(TrainingProgress.last_seen_at))
            .join(TrainingProgress, TrainingProgress.lesson_id == TrainingLesson.id)
            .where(TrainingProgress.user_id == user.id, TrainingLesson.topic_id.in_(topic_ids))
            .group_by(TrainingLesson.topic_id),
        ):
            for linha in (await self.session.execute(stmt)).all():
                if linha[0] is not None and linha[1] is not None:
                    momento = linha[1]
                    if momento.tzinfo is None:
                        # SQLite devolve ingênuo; comparar com agora exige fuso.
                        momento = momento.replace(tzinfo=UTC)
                    fontes.append((int(linha[0]), momento))

        recente: dict[int, datetime] = {}
        for topic_id, momento in fontes:
            atual = recente.get(topic_id)
            if atual is None or momento > atual:
                recente[topic_id] = momento
        return recente

    async def _subject_colors(self, subject_ids: set[int]) -> dict[int, str]:
        if not subject_ids:
            return {}
        linhas = (
            await self.session.execute(
                select(Subject.id, Subject.color_token).where(Subject.id.in_(subject_ids))
            )
        ).all()
        return {int(linha[0]): str(linha[1] or "subject-especifica") for linha in linhas}
