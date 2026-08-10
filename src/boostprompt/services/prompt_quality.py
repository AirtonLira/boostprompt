"""Avaliador determinístico da qualidade do contexto de discovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from boostprompt.models.schemas import DiscoveryMode, PromptQualityEvaluation


class PromptQualityEvaluator:
    """Calcula cobertura, clareza das decisões e prontidão do prompt."""

    _COVERAGE_GROUPS = (
        ("necessidade", "problema", "objetivo"),
        ("usuarios", "stakeholders"),
        ("tipo_solucao", "requisitos_funcionais"),
        ("requisitos_nao_funcionais",),
        ("dados", "integracoes"),
        ("arquitetura", "plataformas", "dominio"),
        ("seguranca",),
        ("entrega", "operacao"),
        ("restricoes", "premissas", "riscos"),
    )
    _EVIDENCE_FIELDS = (
        "objetivo",
        "problema",
        "tipo_solucao",
        "usuarios",
        "stakeholders",
        "requisitos_funcionais",
        "requisitos_nao_funcionais",
        "integracoes",
        "arquitetura",
    )

    @staticmethod
    def _present(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True

    @classmethod
    def _item_count(cls, value: Any) -> int:
        if isinstance(value, (list, tuple, set)):
            return sum(cls._present(item) for item in value)
        return int(cls._present(value))

    def evaluate(
        self,
        *,
        mode: DiscoveryMode,
        context: Mapping[str, Any],
        decisions: Sequence[Mapping[str, Any]],
        questions_count: int,
    ) -> PromptQualityEvaluation:
        if mode is DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE:
            return PromptQualityEvaluation(
                applicable=False,
                coverage=None,
                decision_clarity=None,
                prompt_readiness=None,
                questions_count=questions_count,
                status_text="Avaliação não aplicável ao roteiro gerado diretamente.",
            )

        covered_blocks = sum(
            any(self._present(context.get(field)) for field in group)
            for group in self._COVERAGE_GROUPS
        )
        coverage = round(covered_blocks / len(self._COVERAGE_GROUPS) * 100)

        evidence = min(
            10,
            sum(self._item_count(context.get(field)) for field in self._EVIDENCE_FIELDS)
            + sum(self._item_count(decision.get("decision")) for decision in decisions),
        )
        uncertainty = sum(self._item_count(context.get(field)) for field in ("pendencias", "riscos"))
        decision_clarity = max(0, min(100, round(100 * evidence / (10 + 2 * uncertainty))))
        prompt_readiness = round(
            0.50 * coverage
            + 0.35 * decision_clarity
            + 0.15 * min(questions_count / 30, 1) * 100
        )
        if prompt_readiness == 0:
            status_text = "Aguardando contexto inicial."
        elif prompt_readiness < 70:
            status_text = "Contexto em consolidação."
        else:
            status_text = "Base suficiente para um rascunho de prompt."
        return PromptQualityEvaluation(
            coverage=coverage,
            decision_clarity=decision_clarity,
            prompt_readiness=prompt_readiness,
            questions_count=questions_count,
            status_text=status_text,
        )
