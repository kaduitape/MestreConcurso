"""Descrição das funcionalidades que consomem IA (exibidas no painel)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.ai import AIFeature


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    feature: str
    label: str
    description: str
    phase: str
    kind: str = "chat"


FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        AIFeature.NOTICE_EXTRACTION,
        "Análise de edital",
        "Extrai disciplinas, datas e regras do PDF, sempre com citação de página.",
        "Fase 3",
    ),
    FeatureSpec(
        AIFeature.BOARD_PROFILE,
        "Perfil da banca (DNA)",
        "Interpreta o estilo da banca a partir de estatísticas já calculadas em Python. "
        "O resultado fica gravado e não é recalculado a cada acesso.",
        "Fase 6",
    ),
    FeatureSpec(
        AIFeature.QUESTION_CLASSIFY,
        "Classificação de questões",
        "Sugere disciplina, assunto e padrão de pegadinha para revisão humana.",
        "Fase 5",
    ),
    FeatureSpec(
        AIFeature.ERROR_CLASSIFY,
        "Causa do erro",
        "Sugere por que a questão foi errada. A sugestão só entra nas estatísticas "
        "depois que o próprio candidato confirma.",
        "Fase 6",
    ),
    FeatureSpec(
        AIFeature.CHAT_TUTOR,
        "Mestre IA (tutor)",
        "Responde com base no edital, na banca e no desempenho do candidato.",
        "Fase 7",
    ),
    FeatureSpec(
        AIFeature.FLASHCARD_GENERATION,
        "Geração de flashcards",
        "Cria cartões a partir de conteúdo, erros e questões.",
        "Fase 8",
    ),
    FeatureSpec(
        AIFeature.TRAINING_SCRIPT,
        "Roteiro do Estúdio de Treinamento",
        "Produz o roteiro estruturado em cenas, diálogos, destaques e perguntas "
        "para revisão humana antes da publicação.",
        "Estúdio de Treinamento",
    ),
    FeatureSpec(
        AIFeature.EMBEDDINGS,
        "Embeddings",
        "Vetoriza editais e materiais para a busca semântica.",
        "Fase 3",
        kind="embedding",
    ),
    FeatureSpec(
        AIFeature.RERANK,
        "Reordenação de resultados",
        "Reordena os trechos recuperados antes de montar o contexto.",
        "Fase 3",
        kind="rerank",
    ),
)

FEATURE_BY_SLUG: dict[str, FeatureSpec] = {spec.feature: spec for spec in FEATURE_SPECS}
