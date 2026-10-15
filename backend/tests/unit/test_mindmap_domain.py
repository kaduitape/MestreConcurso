"""Mapas mentais — a validação que separa material revisável de lixo.

A regra que estes testes vigiam: **mapa mental é material de memorização**. O
que estiver escrito ali vai ser decorado, então estrutura inválida precisa ser
recusada antes de chegar à tela, e não corrigida em silêncio.
"""

from __future__ import annotations

import pytest

from app.domain.mindmap import (
    MAX_ITEMS_PER_PANEL,
    MAX_PANELS,
    MIN_PANELS,
    PANELS,
    PANELS_BY_KIND,
    ItemTone,
    MapValidationError,
    PanelKind,
    to_dict,
    validate_content,
)


def _raw(**overrides):
    base = {
        "center_label": "Crase",
        "panels": [
            {
                "kind": "CONCEITO",
                "title": "O que é",
                "items": [{"text": "Fusão da preposição 'a' com o artigo 'a'."}],
            },
            {
                "kind": "REGRAS",
                "title": "Quando ocorre",
                "items": [
                    {"text": "Diante de palavra feminina que admite artigo.", "tone": "CORRETO"}
                ],
            },
        ],
        "review_notes": [],
    }
    base.update(overrides)
    return base


def _validate(raw):
    return validate_content(raw, subject="Língua Portuguesa", topic="Crase")


class TestCatalogue:
    def test_os_oito_paineis_do_pedido_existem(self):
        assert {item.kind for item in PANELS} == set(PanelKind)

    def test_cada_painel_declara_cor_e_orientacao(self):
        for item in PANELS:
            assert item.color_token, "painel sem cor não participa do sistema de cores"
            assert item.guidance, "sem orientação a IA mistura o conteúdo dos painéis"
            assert item.label

    def test_a_cor_de_cada_painel_e_fixa(self):
        """Cor que muda de significado entre dois mapas vira enfeite."""
        assert PANELS_BY_KIND[PanelKind.CONCEITO].color_token == "game-blue"
        assert PANELS_BY_KIND[PanelKind.EXCECOES].color_token == "danger"
        assert PANELS_BY_KIND[PanelKind.MACETES].color_token == "game-gold"
        assert PANELS_BY_KIND[PanelKind.PEGADINHAS].color_token == "game-orange"


class TestValidation:
    def test_um_mapa_valido_passa(self):
        mapa = _validate(_raw())
        assert mapa.center_label == "Crase"
        assert len(mapa.panels) == 2

    def test_resposta_que_nao_e_objeto_e_recusada(self):
        with pytest.raises(MapValidationError):
            _validate(["isto não é um mapa"])

    def test_mapa_sem_paineis_e_recusado(self):
        with pytest.raises(MapValidationError):
            _validate(_raw(panels=[]))

    def test_um_painel_so_nao_e_mapa_mental(self):
        with pytest.raises(MapValidationError, match=str(MIN_PANELS)):
            _validate(_raw(panels=[_raw()["panels"][0]]))

    def test_painel_de_tipo_inventado_e_descartado(self):
        """Tipo fora do catálogo viraria painel sem cor nem sentido."""
        raw = _raw()
        raw["panels"].append({"kind": "RESUMO_MAGICO", "title": "X", "items": [{"text": "algo"}]})
        mapa = _validate(raw)
        assert {item.kind for item in mapa.panels} == {"CONCEITO", "REGRAS"}

    def test_painel_repetido_entra_uma_vez_so(self):
        raw = _raw()
        raw["panels"].append(dict(raw["panels"][0]))
        assert len(_validate(raw).panels) == 2

    def test_painel_sem_item_com_texto_e_descartado(self):
        raw = _raw()
        raw["panels"].append({"kind": "MACETES", "title": "Vazio", "items": [{"text": "   "}]})
        mapa = _validate(raw)
        assert all(item.kind != "MACETES" for item in mapa.panels)

    def test_os_paineis_saem_na_ordem_de_leitura(self):
        raw = _raw()
        raw["panels"] = [
            {"kind": "PEGADINHAS", "title": "P", "items": [{"text": "cuidado"}]},
            {"kind": "CONCEITO", "title": "C", "items": [{"text": "definição"}]},
            {"kind": "REGRAS", "title": "R", "items": [{"text": "regra"}]},
        ]
        assert [item.kind for item in _validate(raw).panels] == [
            "CONCEITO",
            "REGRAS",
            "PEGADINHAS",
        ]

    def test_o_teto_de_paineis_e_respeitado(self):
        raw = _raw()
        raw["panels"] = [
            {"kind": item.kind, "title": item.label, "items": [{"text": "conteúdo"}]}
            for item in PANELS
        ]
        assert len(_validate(raw).panels) <= MAX_PANELS

    def test_o_teto_de_itens_por_painel_e_respeitado(self):
        raw = _raw()
        raw["panels"][0]["items"] = [{"text": f"item {i}"} for i in range(20)]
        assert len(_validate(raw).panels[0].items) == MAX_ITEMS_PER_PANEL

    def test_tom_desconhecido_vira_neutro(self):
        raw = _raw()
        raw["panels"][0]["items"] = [{"text": "algo", "tone": "MÁGICO"}]
        assert _validate(raw).panels[0].items[0].tone == ItemTone.NEUTRO

    def test_titulo_vazio_cai_no_rotulo_do_painel(self):
        raw = _raw()
        raw["panels"][0]["title"] = ""
        assert _validate(raw).panels[0].title == PANELS_BY_KIND["CONCEITO"].label


class TestSources:
    def test_fonte_vazia_nao_vira_citacao(self):
        """Fonte em branco no material não pode virar referência na tela."""
        raw = _raw()
        raw["panels"][0]["items"] = [{"text": "algo", "source": "   "}]
        assert _validate(raw).panels[0].items[0].source is None

    def test_fonte_declarada_e_preservada(self):
        raw = _raw()
        raw["panels"][0]["items"] = [{"text": "algo", "source": "Art. 37 da CF"}]
        assert _validate(raw).panels[0].items[0].source == "Art. 37 da CF"

    def test_as_duvidas_da_ia_chegam_a_revisao(self):
        raw = _raw(review_notes=["Confirmar se a súmula ainda está em vigor.", "  "])
        mapa = _validate(raw)
        assert mapa.review_notes == ["Confirmar se a súmula ainda está em vigor."]


class TestSerialization:
    def test_o_mapa_serializado_leva_cor_e_icone_de_cada_painel(self):
        saida = to_dict(_validate(_raw()))
        assert saida["version"]
        primeiro = saida["panels"][0]
        assert primeiro["color_token"] == "game-blue"
        assert primeiro["icon"]
        assert primeiro["items"][0]["tone_color"]

    def test_o_assunto_acompanha_o_mapa(self):
        saida = to_dict(_validate(_raw()))
        assert saida["subject"] == "Língua Portuguesa"
        assert saida["topic"] == "Crase"
