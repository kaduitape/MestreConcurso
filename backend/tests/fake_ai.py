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
from app.ai.decisions import (
    DecisionProvider,
    DecisionRequest,
    DecisionResult,
    NoulVerdict,
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
    "positions": [
        {
            "name": "Agente de Polícia",
            "education_level": "SUPERIOR",
            "salary_cents": 815700,
            "vacancies": 1200,
            "cr_vacancies": None,
            "workload_hours": None,
            "requirements": "diploma de curso superior em qualquer área",
            "questions_count": 120,
            "exam_duration_minutes": 240,
            "quote": "provimento de 1.200 vagas para o cargo de Agente de Polícia",
            "page": 1,
        },
    ],
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


#: Extração de um edital com **três cargos**, que é o caso comum. Um deles tem
#: cadastro de reserva, e cada um tem uma disciplina específica além da grade
#: comum — é o que o ``position_label`` das disciplinas amarra.
EXTRACTION_MULTICARGO: dict[str, Any] = {
    "fields": {
        "competition.name": {
            "value": "Concurso Público para provimento de cargos do TJDFT",
            "quote": "CONCURSO PÚBLICO PARA PROVIMENTO DE CARGOS DO QUADRO DE PESSOAL",
            "page": 1,
            "confidence": 0.9,
        },
        "organization.name": {
            "value": "Tribunal de Justica do Distrito Federal",
            "quote": "cargos do Tribunal de Justica do Distrito Federal",
            "page": 1,
            "confidence": 0.9,
        },
        "exam_board.name": {
            "value": "Cebraspe",
            "quote": "executado pelo Cebraspe",
            "page": 1,
            "confidence": 0.9,
        },
        # O cargo principal é o de mais vagas; a lista traz os três.
        "position.name": {
            "value": "Tecnico Judiciario - Area Administrativa",
            "quote": "Tecnico Judiciario - Area Administrativa: 300 vagas",
            "page": 1,
            "confidence": 0.9,
        },
        "position.education_level": {
            "value": "MEDIO",
            "quote": "exigido certificado de conclusao do ensino medio",
            "page": 1,
            "confidence": 0.8,
        },
        "position.salary_cents": {
            "value": 852965,
            "quote": "remuneracao inicial de\nR$ 8.529,65",
            "page": 1,
            "confidence": 0.9,
        },
        "position.vacancies": {
            "value": 300,
            "quote": "Area Administrativa: 300 vagas",
            "page": 1,
            "confidence": 0.9,
        },
        "registration.start_date": {
            "value": "2026-02-02",
            "quote": "As inscrições poderão ser efetuadas de 2 de fevereiro de 2026",
            "page": 2,
            "confidence": 0.9,
        },
        "registration.end_date": {
            "value": "2026-03-01",
            "quote": "a 1 de março de 2026.",
            "page": 2,
            "confidence": 0.85,
        },
        "registration.fee_cents": {
            "value": 13000,
            "quote": "O valor da taxa de inscrição é de R$ 130,00",
            "page": 2,
            "confidence": 0.9,
        },
        "exam.date": {
            "value": "2026-04-19",
            "quote": "A prova objetiva será aplicada no dia 19 de abril de 2026",
            "page": 2,
            "confidence": 0.9,
        },
        "exam.duration_minutes": {
            "value": 240,
            "quote": "com duração de 4 horas",
            "page": 2,
            "confidence": 0.85,
        },
        "exam.questions_count": {
            "value": 120,
            "quote": "cargos de nivel superior tera 120 questoes",
            "page": 2,
            "confidence": 0.85,
        },
        "exam.min_score_rule": {"value": None, "quote": None, "page": None, "confidence": 0.0},
        "elimination.rules": {
            "value": "Eliminado quem obtiver nota inferior a 30% em qualquer bloco",
            "quote": "Será eliminado o candidato que obtiver nota inferior a 30%",
            "page": 2,
            "confidence": 0.9,
        },
    },
    "positions": [
        {
            "name": "Analista Judiciario - Area Administrativa",
            "education_level": "SUPERIOR",
            "salary_cents": 1399478,
            "vacancies": 150,
            "cr_vacancies": None,
            "workload_hours": 40,
            "requirements": "diploma de curso superior em qualquer area",
            "questions_count": 120,
            "exam_duration_minutes": 240,
            "quote": "Analista Judiciario - Area Administrativa: 150 vagas",
            "page": 1,
        },
        {
            "name": "Analista Judiciario - Area de Tecnologia",
            "education_level": "SUPERIOR",
            "salary_cents": 1399478,
            "vacancies": 40,
            "cr_vacancies": 80,
            "workload_hours": None,
            "requirements": "diploma de curso superior em computacao",
            "questions_count": 120,
            "exam_duration_minutes": 240,
            "quote": "Analista Judiciario - Area de Tecnologia: 40 vagas e cadastro de reserva",
            "page": 1,
        },
        {
            "name": "Tecnico Judiciario - Area Administrativa",
            "education_level": "MEDIO",
            "salary_cents": 852965,
            "vacancies": 300,
            "cr_vacancies": None,
            "workload_hours": 40,
            "requirements": "certificado de conclusao do ensino medio",
            "questions_count": None,
            "exam_duration_minutes": 240,
            "quote": "Tecnico Judiciario - Area Administrativa: 300 vagas",
            "page": 1,
        },
        # Cargo que o modelo afirmou com citação que não existe no PDF: não pode
        # virar cargo no catálogo, e tem de aparecer declarado.
        {
            "name": "Oficial de Justica",
            "education_level": "SUPERIOR",
            "salary_cents": None,
            "vacancies": 10,
            "cr_vacancies": None,
            "workload_hours": None,
            "requirements": None,
            "questions_count": None,
            "exam_duration_minutes": None,
            "quote": "Oficial de Justica: 10 vagas conforme quadro anexo deste edital",
            "page": 1,
        },
    ],
    "subjects": [
        {
            "name": "Língua Portuguesa",
            "position_label": None,
            "weight": None,
            "questions_count": None,
            "topics": ["Compreensão e interpretação de textos", "Ortografia oficial"],
            "quote": "LÍNGUA PORTUGUESA: 1 Compreensão e interpretação de textos.",
            "page": 3,
        },
        {
            "name": "Direito Administrativo",
            "position_label": "Analista Judiciario - Area Administrativa",
            "weight": None,
            "questions_count": None,
            "topics": ["Princípios da administração pública", "Atos administrativos"],
            "quote": "DIREITO ADMINISTRATIVO: 1 Princípios da administração pública.",
            "page": 3,
        },
        {
            "name": "Banco de Dados",
            "position_label": "Analista Judiciario - Area de Tecnologia",
            "weight": None,
            "questions_count": None,
            "topics": ["Modelo relacional", "Linguagem SQL"],
            "quote": "BANCO DE DADOS: 1 Modelo relacional. 2 Linguagem SQL.",
            "page": 3,
        },
        # Disciplina própria de um cargo que o catálogo não tem: o cargo entra
        # com a grade comum, e esta fica declarada como lacuna.
        {
            "name": "Nocoes de Arquivologia",
            "position_label": "Tecnico Judiciario - Area Administrativa",
            "weight": None,
            "questions_count": None,
            "topics": ["Gestão de documentos", "Tabela de temporalidade"],
            "quote": "NOCOES DE ARQUIVOLOGIA: 1 Gestão de documentos.",
            "page": 3,
        },
    ],
    "events": [
        {
            "kind": "EXAM",
            "title": "Aplicação da prova objetiva",
            "date_start": "2026-04-19",
            "is_critical": True,
            "quote": "A prova objetiva será aplicada no dia 19 de abril de 2026",
            "page": 2,
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


class FakeDecisionProvider(DecisionProvider):
    """Provedor de julgamento falso: devolve probabilidades programadas.

    Existe pelo mesmo motivo do ``FakeProvider``: exercitar o caminho inteiro —
    resolução da funcionalidade, medição, composição em código — sem gastar
    token e sem depender de rede. As probabilidades são dadas pelo teste, uma por
    chamada, para que a ordem da fila de revisão possa ser conferida.
    """

    slug = "typesafe"
    default_base_url = "https://fake.local"
    default_model = "jev-fake"

    def __init__(
        self,
        credentials: ProviderCredentials | None = None,
        *,
        probabilities: list[float] | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        super().__init__(credentials or ProviderCredentials(api_key="sk-fake-jev"))
        self.probabilities = list(probabilities or [])
        self.fail_with = fail_with
        self.calls: list[DecisionRequest] = []

    async def test_connection(self) -> ConnectionCheck:
        return ConnectionCheck(
            ok=True, message="falso", latency_ms=1, models_available=1, sample_models=["jev-fake"]
        )

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(slug="jev-fake", display_name="Jev (falso)", kind="judgment")]

    async def judge(self, request: DecisionRequest, *, model: str | None = None) -> DecisionResult:
        self.calls.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        # Sem probabilidade programada, a última se repete: o teste decide
        # quantas chamadas acontecem, não este arquivo.
        valor = self.probabilities.pop(0) if self.probabilities else 0.9
        return DecisionResult(
            answers={key: NoulVerdict(probability=valor) for key in request.questions},
            model=model or self.default_model,
            usage=Usage(input_tokens=90, output_tokens=4),
            latency_ms=12,
        )
