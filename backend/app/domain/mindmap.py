"""Mapas mentais — o conteúdo do mapa, separado do desenho dele.

A decisão que sustenta o módulo inteiro está no próprio pedido:

    "Caso o gerador de imagens não reproduza textos com fidelidade, gere a arte
    sem os textos internos e insira-os posteriormente por uma camada de texto
    programática."

É o que acontece aqui, e não só por precaução: **gerador de imagem não escreve
português confiável**. Num mapa de estudo, texto embaralhado não é um defeito
estético — é conteúdo errado sendo decorado. Um "art. 37" que vira "ait. 3Z" na
imagem ensina uma coisa falsa a quem está estudando para prova.

Por isso o mapa é **dado estruturado**: a IA produz painéis, itens e cores; a
arte medieval é moldura e fundo; e o texto é texto de verdade na tela — legível,
selecionável, pesquisável e sem risco de sair torto. Quem lê de celular amplia;
quem precisa de leitor de tela consegue ouvir.

O módulo é puro: sem I/O, sem IA, sem banco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

#: Versão do contrato do mapa. Entra na impressão digital do cache: mudar a
#: estrutura precisa invalidar o que foi gerado com a estrutura antiga.
MAP_VERSION = "v1"

#: Abaixo de dois painéis não é mapa mental, é um cartão com título.
MIN_PANELS = 2
#: Acima de oito a tela vira poluição — o próprio pedido fixa esse teto.
MAX_PANELS = 8

#: Itens por painel. Acima disso o painel deixa de caber e deixa de ser lido.
MAX_ITEMS_PER_PANEL = 6
MAX_ITEM_CHARS = 180
MAX_TITLE_CHARS = 90


class PanelKind(StrEnum):
    """Os oito tipos de painel do pedido, nesta ordem de leitura."""

    CONCEITO = "CONCEITO"
    REGRAS = "REGRAS"
    CLASSIFICACOES = "CLASSIFICACOES"
    APLICACAO = "APLICACAO"
    EXCECOES = "EXCECOES"
    ERROS_COMUNS = "ERROS_COMUNS"
    MACETES = "MACETES"
    PEGADINHAS = "PEGADINHAS"


@dataclass(frozen=True, slots=True)
class PanelSpec:
    kind: str
    label: str
    #: O que entra neste painel — vai no prompt, para a IA não misturar.
    guidance: str
    #: Cor do sistema do pedido. Um painel, uma cor, sempre a mesma.
    color_token: str
    icon: str


#: O sistema de cores é fixo e declarado: azul para conceito, verde para regra
#: correta, vermelho para proibição e exceção, roxo para classificação, dourado
#: para macete e laranja para pegadinha. Cor que muda de significado entre dois
#: mapas deixa de ser informação e vira enfeite.
PANELS: tuple[PanelSpec, ...] = (
    PanelSpec(
        PanelKind.CONCEITO,
        "Conceito",
        "Definição objetiva do assunto, em uma ou duas frases.",
        "game-blue",
        "scroll",
    ),
    PanelSpec(
        PanelKind.REGRAS,
        "Regras fundamentais",
        "Os princípios e as informações essenciais que a prova cobra.",
        "success",
        "shield",
    ),
    PanelSpec(
        PanelKind.CLASSIFICACOES,
        "Classificações",
        "Tipos, categorias ou divisões do assunto.",
        "game-purple",
        "crown",
    ),
    PanelSpec(
        PanelKind.APLICACAO,
        "Aplicação prática",
        "Exemplos claros e contextualizados, corretos e incorretos.",
        "success",
        "sword",
    ),
    PanelSpec(
        PanelKind.EXCECOES,
        "Exceções",
        "Particularidades e casos especiais que fogem da regra geral.",
        "danger",
        "flame",
    ),
    PanelSpec(
        PanelKind.ERROS_COMUNS,
        "Erros comuns",
        "Confusões frequentes de quem estuda este assunto.",
        "danger",
        "skull",
    ),
    PanelSpec(
        PanelKind.MACETES,
        "Macetes de memorização",
        "Associações, frases e técnicas curtas para decorar.",
        "game-gold",
        "key",
    ),
    PanelSpec(
        PanelKind.PEGADINHAS,
        "Pegadinhas de concurso",
        "O que as bancas costumam cobrar para derrubar o candidato.",
        "game-orange",
        "trap",
    ),
)

PANELS_BY_KIND: dict[str, PanelSpec] = {item.kind: item for item in PANELS}

#: Ordem de leitura, para o mapa sair sempre com a mesma espinha dorsal.
PANEL_ORDER: dict[str, int] = {item.kind: index for index, item in enumerate(PANELS)}


class ItemTone(StrEnum):
    """O tom de um item dentro do painel."""

    NEUTRO = "NEUTRO"
    CORRETO = "CORRETO"
    INCORRETO = "INCORRETO"
    ALERTA = "ALERTA"


TONE_COLOR: dict[str, str] = {
    ItemTone.NEUTRO: "slate",
    ItemTone.CORRETO: "success",
    ItemTone.INCORRETO: "danger",
    ItemTone.ALERTA: "game-orange",
}


@dataclass(frozen=True, slots=True)
class MapItem:
    text: str
    tone: str = ItemTone.NEUTRO
    #: Fonte declarada pelo material (artigo, súmula, página). Nunca inventada:
    #: vem vazia quando o conteúdo-base não trouxe nenhuma.
    source: str | None = None


@dataclass(frozen=True, slots=True)
class MapPanel:
    kind: str
    title: str
    items: list[MapItem] = field(default_factory=list)

    @property
    def spec(self) -> PanelSpec:
        return PANELS_BY_KIND[self.kind]


@dataclass(frozen=True, slots=True)
class MindMapContent:
    """O mapa como dado. O desenho é outra camada."""

    subject: str
    topic: str
    center_label: str
    panels: list[MapPanel] = field(default_factory=list)
    #: Aviso para revisão humana quando algo pedia conferência.
    review_notes: list[str] = field(default_factory=list)


class MapValidationError(ValueError):
    """Estrutura que não serve para virar mapa."""


def _clean(value: object, *, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit].strip()


def validate_content(raw: object, *, subject: str, topic: str) -> MindMapContent:
    """Transforma a resposta da IA em mapa, ou recusa dizendo o que faltou.

    A validação é severa de propósito. Um painel com tipo inventado, um item
    vazio ou um mapa com um painel só passariam despercebidos na tela e
    chegariam a quem estuda como se fossem material revisado.
    """
    if not isinstance(raw, dict):
        raise MapValidationError("A IA não devolveu um objeto de mapa.")

    raw_panels = raw.get("panels")
    if not isinstance(raw_panels, list) or not raw_panels:
        raise MapValidationError("O mapa veio sem painéis.")

    panels: list[MapPanel] = []
    seen: set[str] = set()
    for entry in raw_panels:
        if not isinstance(entry, dict):
            continue
        kind = _clean(entry.get("kind"), limit=40).upper()
        if kind not in PANELS_BY_KIND or kind in seen:
            # Tipo desconhecido ou repetido é descartado em silêncio: a IA
            # errar o rótulo não pode virar painel sem cor nem sentido.
            continue
        seen.add(kind)

        raw_items = entry.get("items")
        items: list[MapItem] = []
        for item in raw_items if isinstance(raw_items, list) else []:
            text = _clean(
                item.get("text") if isinstance(item, dict) else item, limit=MAX_ITEM_CHARS
            )
            if not text:
                continue
            tone = _clean(item.get("tone"), limit=20).upper() if isinstance(item, dict) else ""
            source = _clean(item.get("source"), limit=120) if isinstance(item, dict) else ""
            items.append(
                MapItem(
                    text=text,
                    tone=tone if tone in set(ItemTone) else ItemTone.NEUTRO,
                    source=source or None,
                )
            )
            if len(items) >= MAX_ITEMS_PER_PANEL:
                break

        if not items:
            continue

        spec = PANELS_BY_KIND[kind]
        panels.append(
            MapPanel(
                kind=kind,
                title=_clean(entry.get("title"), limit=MAX_TITLE_CHARS) or spec.label,
                items=items,
            )
        )

    if len(panels) < MIN_PANELS:
        raise MapValidationError(f"O mapa precisa de ao menos {MIN_PANELS} painéis com conteúdo.")

    panels.sort(key=lambda item: PANEL_ORDER[item.kind])
    panels = panels[:MAX_PANELS]

    notes_raw = raw.get("review_notes")
    notes = [
        _clean(note, limit=240)
        for note in (notes_raw if isinstance(notes_raw, list) else [])
        if _clean(note, limit=240)
    ]

    return MindMapContent(
        subject=_clean(subject, limit=140),
        topic=_clean(topic, limit=240),
        center_label=_clean(raw.get("center_label"), limit=60) or _clean(topic, limit=60),
        panels=panels,
        review_notes=notes[:6],
    )


def to_dict(content: MindMapContent) -> dict[str, object]:
    """Serializa o mapa para guardar e para a tela desenhar."""
    return {
        "version": MAP_VERSION,
        "subject": content.subject,
        "topic": content.topic,
        "center_label": content.center_label,
        "review_notes": content.review_notes,
        "panels": [
            {
                "kind": panel.kind,
                "title": panel.title,
                "label": panel.spec.label,
                "color_token": panel.spec.color_token,
                "icon": panel.spec.icon,
                "items": [
                    {
                        "text": item.text,
                        "tone": item.tone,
                        "tone_color": TONE_COLOR[item.tone],
                        "source": item.source,
                    }
                    for item in panel.items
                ],
            }
            for panel in content.panels
        ],
    }
