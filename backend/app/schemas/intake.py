"""Schemas do cadastro de concurso por URL.

A tela de revisão precisa de duas coisas que um CRUD comum não dá: **a
procedência de cada campo** (nível de evidência, citação e página) e **o que o
serviço não conseguiu decidir**. Por isso os candidatos a PDF viajam com
pontuação e explicação, e os campos viajam com `applicable` — o que não é
aplicável chega em branco para alguém digitar, e a tela sabe disso sem calcular
nada.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


class IntakeCandidateRead(BaseModel):
    """Um link para PDF que a página oferecia, com a nota que recebeu."""

    url: str
    text: str
    score: int
    explanation: str


class IntakeFieldRead(BaseModel):
    """Um campo da proposta, com a procedência à vista."""

    field_path: str
    label: str
    value: Any = None
    evidence_level: str
    quote: str | None = None
    page_number: int | None = None
    #: Para onde este campo vai na ficha do concurso, quando vai.
    target: str | None = None
    #: Para onde ele vai no cargo. Um campo pode ir para os dois, para um só,
    #: ou para nenhum — e "nenhum" quer dizer que ele fica só no edital.
    position_target: str | None = None
    #: ``False`` quando a evidência não é oficial nem confirmada: a tela mostra
    #: o campo em branco, com o motivo, para uma pessoa preencher.
    applicable: bool


class IntakeGapRead(BaseModel):
    """Uma coisa que o cadastro automático não preencheu, com o motivo."""

    code: str
    label: str
    detail: str | None = None


class IntakeProposalRead(BaseModel):
    fields: list[IntakeFieldRead] = Field(default_factory=list)
    applicable: int = 0
    needs_typing: int = 0


class IntakeRead(BaseModel):
    model_config = _READ

    public_id: str
    source_kind: str
    source_url: str | None = None
    source_name: str | None = None
    status: str
    chosen_url: str | None = None
    choice_reason: str | None = None
    detail: str | None = None
    candidates: list[IntakeCandidateRead] = Field(default_factory=list)
    proposal: IntakeProposalRead = Field(default_factory=IntakeProposalRead)
    matches: dict[str, Any] = Field(default_factory=dict)
    #: ``True`` quando o cadastro saiu sem ninguém digitar nada.
    auto_applied: bool = False
    #: O que ficou faltando. Lista vazia num cadastro automático quer dizer que
    #: o edital sustentava tudo — e é a única leitura em que "cadastrado"
    #: também significa "completo".
    gaps: list[IntakeGapRead] = Field(default_factory=list)
    notice_public_id: str | None = None
    competition_public_id: str | None = None
    applied_at: datetime | None = None
    created_at: datetime


class IntakeStart(BaseModel):
    url: str = Field(min_length=10, max_length=500)
    #: Cadastrar sozinho o que o edital sustentar. Desligado, o serviço monta a
    #: ficha e espera a revisão — que é o caminho de quem quer conferir antes.
    auto_apply: bool = True


class IntakeChoose(BaseModel):
    """Qual PDF uma pessoa aponta quando o serviço recusou escolher."""

    url: str = Field(min_length=10, max_length=500)
    auto_apply: bool = True


class IntakeApply(BaseModel):
    """Os valores que a pessoa revisou — é isto que vira cadastro.

    Nada aqui é lido da proposta: o formulário chega preenchido com o que o
    edital sustenta, mas quem assina é quem envia.
    """

    name: str = Field(min_length=3, max_length=200)
    year: int = Field(ge=1990, le=2100)
    organization_public_id: str | None = None
    organization_name: str | None = Field(default=None, max_length=200)
    organization_short_name: str | None = Field(default=None, max_length=40)
    exam_board_public_id: str | None = None
    #: Os demais campos do concurso, na forma em que a coluna os guarda
    #: (datas em AAAA-MM-DD, números inteiros).
    fields: dict[str, Any] = Field(default_factory=dict)
    #: Os campos do cargo. Sem ``name`` aqui, nenhum cargo é criado — e a grade
    #: de disciplinas, que mora no cargo, também não.
    position: dict[str, Any] = Field(default_factory=dict)


class IntakeReject(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
