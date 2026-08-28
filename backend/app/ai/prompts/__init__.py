"""Prompts versionados.

O arquivo em disco é a fonte de verdade (passa por code review); a versão usada em
cada chamada é registrada junto do resultado, para que qualquer saída seja
reproduzível.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.errors import NotFoundError

PROMPTS_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class Prompt:
    slug: str
    version: str
    template: str

    def render(self, **variables: str) -> str:
        rendered = self.template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered


@lru_cache(maxsize=32)
def get_prompt(slug: str, version: str = "v1") -> Prompt:
    path = PROMPTS_DIR / slug / f"{version}.md"
    if not path.is_file():
        raise NotFoundError(
            f"Prompt '{slug}' versão '{version}' não encontrado.",
            code="prompt_not_found",
        )
    return Prompt(slug=slug, version=version, template=path.read_text(encoding="utf-8"))


def latest_version(slug: str) -> str:
    """Maior versão disponível do prompt (v1, v2, …)."""
    directory = PROMPTS_DIR / slug
    versions = sorted(
        (item.stem for item in directory.glob("v*.md")),
        key=lambda name: int(name.lstrip("v")),
    )
    if not versions:
        raise NotFoundError(f"Nenhuma versão do prompt '{slug}'.", code="prompt_not_found")
    return versions[-1]
