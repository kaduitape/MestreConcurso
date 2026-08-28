"""Provedor de IA falso para exercitar o pipeline sem gastar tokens de verdade."""

from __future__ import annotations

import json
from typing import Any

from app.ai.base import (
    AIProvider,
    CompletionRequest,
    CompletionResult,
    ConnectionCheck,
    EmbeddingResult,
    ModelInfo,
    ProviderCredentials,
    Usage,
)


class FakeProvider(AIProvider):
    """Devolve respostas programadas e conta quantas chamadas recebeu."""

    slug = "openai"
    default_base_url = "https://fake.local/v1"

    def __init__(
        self,
        credentials: ProviderCredentials | None = None,
        *,
        completion_payload: dict[str, Any] | None = None,
        raw_completion: str | None = None,
        embedding_dimensions: int = 4,
    ) -> None:
        super().__init__(credentials or ProviderCredentials(api_key="sk-fake-000000000000"))
        self.completion_payload = completion_payload or {}
        self.raw_completion = raw_completion
        self.embedding_dimensions = embedding_dimensions
        self.completion_calls: list[CompletionRequest] = []
        self.embedding_calls: list[list[str]] = []

    async def test_connection(self) -> ConnectionCheck:
        return ConnectionCheck(ok=True, message="ok", latency_ms=5, models_available=2)

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(slug="gpt-4o-mini", display_name="gpt-4o-mini", kind="chat"),
            ModelInfo(
                slug="text-embedding-3-small",
                display_name="text-embedding-3-small",
                kind="embedding",
            ),
        ]

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.completion_calls.append(request)
        content = self.raw_completion
        if content is None:
            content = json.dumps(self.completion_payload, ensure_ascii=False)
        return CompletionResult(
            content=content,
            model=request.model,
            usage=Usage(input_tokens=1200, output_tokens=400),
            latency_ms=42,
        )

    async def embed(self, texts: list[str], model: str) -> EmbeddingResult:
        self.embedding_calls.append(texts)
        vectors = [
            [float((index + position) % 7) / 7 for position in range(self.embedding_dimensions)]
            for index, _ in enumerate(texts)
        ]
        return EmbeddingResult(
            vectors=vectors,
            model=model,
            usage=Usage(input_tokens=sum(len(text) // 4 for text in texts)),
            latency_ms=12,
        )


# Resposta plausível para o edital de teste: uma citação verdadeira, uma inventada
# e um campo ausente — os três caminhos que o validador precisa tratar.
EXTRACTION_PAYLOAD: dict[str, Any] = {
    "fields": {
        "competition.name": {
            "value": "Concurso Público para o cargo de Agente de Polícia",
            "quote": "CONCURSO PÚBLICO PARA O CARGO DE AGENTE DE POLÍCIA",
            "page": 1,
            "confidence": 0.95,
        },
        "organization.name": {
            "value": "Polícia Civil do Distrito Federal",
            "quote": "da Polícia Civil do Distrito Federal.",
            "page": 1,
            "confidence": 0.9,
        },
        "exam_board.name": {
            "value": "Cebraspe",
            "quote": "executado pelo Cebraspe",
            "page": 1,
            "confidence": 0.9,
        },
        "position.name": {
            "value": "Agente de Polícia",
            "quote": "para o cargo de Agente de Polícia",
            "page": 1,
            "confidence": 0.9,
        },
        "position.salary_cents": {
            "value": 815700,
            "quote": "A remuneração inicial do cargo é de R$ 8.157,00.",
            "page": 1,
            "confidence": 0.9,
        },
        "position.vacancies": {
            "value": 1200,
            "quote": "provimento de 1.200 vagas para o cargo de Agente de Polícia",
            "page": 1,
            "confidence": 0.85,
        },
        "position.education_level": {
            "value": "SUPERIOR",
            "quote": "diploma de curso superior em qualquer área",
            "page": 1,
            "confidence": 0.8,
        },
        "registration.start_date": {
            "value": "2026-01-20",
            "quote": "As inscrições poderão ser efetuadas de 20 de janeiro de 2026",
            "page": 2,
            "confidence": 0.9,
        },
        "registration.end_date": {
            "value": "2026-02-10",
            "quote": "a 10 de fevereiro de 2026.",
            "page": 2,
            "confidence": 0.85,
        },
        "registration.fee_cents": {
            "value": 12000,
            "quote": "O valor da taxa de inscrição é de R$ 120,00.",
            "page": 2,
            "confidence": 0.9,
        },
        "exam.date": {
            "value": "2026-03-15",
            "quote": "A prova objetiva será aplicada no dia 15 de março de 2026",
            "page": 2,
            "confidence": 0.95,
        },
        "exam.duration_minutes": {
            "value": 240,
            "quote": "com duração de 4 horas",
            "page": 2,
            "confidence": 0.8,
        },
        "exam.questions_count": {
            "value": 120,
            "quote": "composta por 120 questões de múltipla escolha",
            "page": 2,
            "confidence": 0.9,
        },
        "exam.min_score_rule": {
            "value": "Nota mínima de 50% por bloco",
            # Citação que NÃO existe no documento: precisa ser rebaixada.
            "quote": "O candidato deverá obter no mínimo 70% de aproveitamento geral",
            "page": 2,
            "confidence": 0.6,
        },
        "elimination.rules": {
            "value": "Eliminado quem obtiver nota inferior a 50% em qualquer bloco",
            "quote": (
                "Será eliminado o candidato que obtiver nota inferior a 50% em qualquer bloco."
            ),
            "page": 2,
            "confidence": 0.9,
        },
    },
    "subjects": [
        {
            "name": "Língua Portuguesa",
            "topics": [
                "Compreensão e interpretação de textos",
                "Ortografia oficial",
                "Emprego do sinal indicativo de crase",
            ],
            "quote": "LÍNGUA PORTUGUESA: 1 Compreensão e interpretação de textos.",
            "page": 3,
        },
        {
            "name": "Direito Penal",
            "topics": ["Crimes contra a pessoa", "Crimes contra o patrimônio"],
            "quote": "DIREITO PENAL: 1 Princípios aplicáveis ao direito penal.",
            "page": 3,
        },
        {
            "name": "Legislação Especial",
            "topics": [],
            "quote": "LEGISLAÇÃO ESPECIAL: 1 Lei de Execução Penal.",
            "page": 3,
        },
    ],
    "events": [
        {
            "kind": "EXAM",
            "title": "Aplicação da prova objetiva",
            "date_start": "2026-03-15",
            "is_critical": True,
            "quote": "A prova objetiva será aplicada no dia 15 de março de 2026",
            "page": 2,
        },
        {
            "kind": "PHYSICAL_TEST",
            "title": "Teste de aptidão física",
            "date_start": "2026-05-03",
            "is_critical": True,
            "quote": "O teste de aptidão física será aplicado em 3 de maio de 2026",
            "page": 4,
        },
        {
            "kind": "OTHER",
            "title": "Evento sem data legível",
            "date_start": "data a definir",
            "is_critical": False,
            "quote": None,
            "page": None,
        },
    ],
}


# Sugestão de classificação plausível — é apenas sugestão: nada é aplicado sozinho.
CLASSIFY_PAYLOAD: dict[str, Any] = {
    "subject": "Direito Penal",
    "topic": "Crimes contra a pessoa",
    "difficulty": "HARD",
    "tags": ["homicídio", "qualificadoras"],
    "confidence": 0.82,
    "rationale": "O enunciado trata de qualificadoras do homicídio.",
}
