"""Validação determinística do prompt Markdown final de implementação."""

from __future__ import annotations

import re
import unicodedata
from typing import ClassVar
from urllib.parse import urlparse

from boostprompt.models.schemas import PromptValidationReport


class PromptArtifactValidator:
    """Verifica a estrutura mínima do único prompt entregue ao implementador."""

    TITLE_PREFIX = "# Prompt Mestre de Implementação - "
    CANONICAL_SECTIONS = (
        "## 1. Contexto e objetivo",
        "## 2. Problema e contexto",
        "## 3. Objetivos de negócio",
        "## 4. Público-alvo, usuários e stakeholders",
        "## 5. Premissas e restrições",
        "## 6. Requisitos funcionais",
        "## 7. Requisitos não funcionais",
        "## 8. Arquitetura recomendada",
        "## 9. Stack tecnológica sugerida",
        "## 10. Dados, integrações e fluxos",
        "## 11. Segurança, privacidade e compliance",
        "## 12. Estratégia de entrega e operação",
        "## 13. Observabilidade, suporte e evolução",
        "## 14. Riscos, trade-offs e mitigação",
        "## 15. Roadmap sugerido",
        "## 16. Decisões consolidadas",
        "## 17. Plano de execução",
        "## 18. Critérios de aceite",
        "## 19. Estratégia de validação",
        "## 20. Pendências para execução",
        "## 21. Referências consultadas",
        "## 22. Instruções ao agente implementador",
    )
    _PROMPT_TOPICS: ClassVar[dict[str, tuple[str, ...]]] = {
        "objetivo e escopo": ("objetivo", "escopo"),
        "restrições": ("restri",),
        "requisitos funcionais": (r"requisitos? funcion(?:al|ais)",),
        "requisitos não funcionais": (r"requisitos? nao funcion(?:al|ais)",),
        "arquitetura": ("arquitetura",),
        "dados e integrações": ("dados", "integr"),
        "segurança": ("seguranca",),
        "testes": ("teste",),
        "observabilidade": ("observabilidade",),
        "entrega": ("entrega",),
        "critérios de aceite": (r"criterios? de aceite",),
    }

    def validate(self, markdown: str) -> PromptValidationReport:
        """Retorna as lacunas estruturais sem inferir requisitos ausentes."""

        warnings: list[str] = []
        if not markdown.lstrip().startswith(self.TITLE_PREFIX):
            warnings.append("O documento não usa o título canônico do prompt mestre.")
        if re.search(r"(?mi)^# Escopo da Solução\s*$", markdown):
            warnings.append("O título legado # Escopo da Solução não é permitido.")
        if re.search(r"(?i)\b(documento acima|prompt abaixo|escopo acima)\b", markdown):
            warnings.append("O prompt não pode depender de outro documento ou de conteúdo externo.")

        contents = {
            heading: self._section_content(markdown, heading)
            for heading in self.CANONICAL_SECTIONS
        }
        missing_sections = [
            heading for heading, content in contents.items() if content is None or not content.strip()
        ]
        implementation_instructions = contents[self.CANONICAL_SECTIONS[-1]] or ""
        normalized_instructions = self._normalize(implementation_instructions)
        missing_prompt_topics = [
            topic
            for topic, terms in self._PROMPT_TOPICS.items()
            if not all(re.search(term, normalized_instructions) for term in terms)
        ]
        invalid_reference_urls = self._invalid_reference_urls(
            contents[self.CANONICAL_SECTIONS[-2]] or ""
        )
        return PromptValidationReport(
            valid=not (
                warnings or missing_sections or missing_prompt_topics or invalid_reference_urls
            ),
            missing_sections=missing_sections,
            missing_prompt_topics=missing_prompt_topics,
            invalid_reference_urls=invalid_reference_urls,
            warnings=warnings,
        )

    @staticmethod
    def _section_content(markdown: str, heading: str) -> str | None:
        match = re.search(rf"(?m)^{re.escape(heading)}\s*$", markdown)
        if match is None:
            return None
        next_heading = re.search(r"(?m)^##\s+", markdown[match.end() :])
        end = match.end() + next_heading.start() if next_heading else len(markdown)
        return markdown[match.end() : end].strip()

    @classmethod
    def _invalid_reference_urls(cls, references: str) -> list[str]:
        urls = set(re.findall(r"(?im)^\s*URL:\s*(\S+)\s*$", references))
        urls.update(re.findall(r"https?://[^\s)\]]+", references))
        return sorted(url for url in urls if not cls._is_valid_url(url))

    @staticmethod
    def _is_valid_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFD", value.casefold())
        return "".join(character for character in decomposed if not unicodedata.combining(character))
