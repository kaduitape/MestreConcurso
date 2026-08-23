"""Concurso Intelligence Engine — camada de IA isolada do restante da aplicação.

Nenhum módulo de negócio importa SDK de fornecedor: tudo passa pela porta
``AIProvider``. Trocar de fornecedor é trocar o adaptador, não o produto.
"""
