"""Adaptador da AISA.one.

A AISA expõe a API de Chat Completions compatível com OpenAI. Herdar o
adaptador HTTP existente preserva o mesmo contrato, o teste de conexão e o
tratamento de erros sem acoplar o restante da aplicação ao gateway.
"""

from __future__ import annotations

from app.ai.providers.openai import OpenAIProvider


class AisaProvider(OpenAIProvider):
    slug = "aisa"
    default_base_url = "https://api.aisa.one/v1"


__all__ = ["AisaProvider"]
