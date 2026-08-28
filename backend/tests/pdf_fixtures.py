"""Gera PDFs de teste com estrutura parecida com a de um edital real."""

from __future__ import annotations

import pymupdf

EDITAL_PAGES: list[str] = [
    """EDITAL Nº 1/2026 - PCDF, DE 10 DE JANEIRO DE 2026
CONCURSO PÚBLICO PARA O CARGO DE AGENTE DE POLÍCIA

1 DAS DISPOSIÇÕES PRELIMINARES
1.1 O concurso público será regido por este edital e executado pelo Cebraspe.
1.2 A seleção destina-se ao provimento de 1.200 vagas para o cargo de Agente de Polícia
da Polícia Civil do Distrito Federal.
1.3 A remuneração inicial do cargo é de R$ 8.157,00.
1.4 O requisito é diploma de curso superior em qualquer área, devidamente registrado.""",
    """2 DAS INSCRIÇÕES
2.1 As inscrições poderão ser efetuadas de 20 de janeiro de 2026 a 10 de fevereiro de 2026.
2.2 O valor da taxa de inscrição é de R$ 120,00.
2.3 O candidato poderá solicitar isenção da taxa entre 20 e 24 de janeiro de 2026.

3 DAS PROVAS
3.1 A prova objetiva será aplicada no dia 15 de março de 2026, com duração de 4 horas.
3.2 A prova objetiva será composta por 120 questões de múltipla escolha.
3.3 Será eliminado o candidato que obtiver nota inferior a 50% em qualquer bloco.""",
    """4 DO CONTEÚDO PROGRAMÁTICO
4.1 LÍNGUA PORTUGUESA: 1 Compreensão e interpretação de textos. 2 Ortografia oficial.
3 Emprego do sinal indicativo de crase. 4 Sintaxe da oração e do período.
4.2 DIREITO PENAL: 1 Princípios aplicáveis ao direito penal. 2 Crimes contra a pessoa.
3 Crimes contra o patrimônio. 4 Crimes contra a administração pública.
4.3 LEGISLAÇÃO ESPECIAL: 1 Lei de Execução Penal. 2 Lei de Drogas.""",
    """5 DO CRONOGRAMA
5.1 Divulgação do resultado preliminar: 10 de abril de 2026.
5.2 O teste de aptidão física será aplicado em 3 de maio de 2026, de caráter eliminatório.

ANEXO I - QUADRO DE VAGAS
Agente de Polícia: 1.200 vagas, sendo 20% reservadas conforme legislação vigente.""",
]


def build_edital_pdf(pages: list[str] | None = None) -> bytes:
    """PDF com camada de texto, como um edital publicado digitalmente."""
    document = pymupdf.open()
    for content in pages or EDITAL_PAGES:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(56, 56, 540, 780), content, fontsize=10, fontname="helv")
    data: bytes = document.tobytes()
    document.close()
    return data


def build_scanned_pdf(page_count: int = 2) -> bytes:
    """PDF sem camada de texto — simula um edital digitalizado."""
    document = pymupdf.open()
    for _ in range(page_count):
        page = document.new_page()
        page.draw_rect(pymupdf.Rect(60, 60, 500, 700), color=(0, 0, 0), width=1)
    data: bytes = document.tobytes()
    document.close()
    return data
