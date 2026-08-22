import pytest
from pydantic import ValidationError

from boostprompt.models.schemas import (
    DiscoveryMode,
    PromptValidationReport,
    Question,
    ResearchPlan,
    ResearchRequest,
    ResearchTopic,
    SourceKind,
)


def test_question_requires_an_explicit_prompt_and_valid_alternatives() -> None:
    question = Question(
        number=1,
        category="Objetivos",
        prompt="Qual resultado deve definir o sucesso da iniciativa?",
        why_it_matters="A resposta orienta o escopo e os critérios de aceite.",
        alternatives=["Reduzir custo", "Aumentar conversão"],
        tradeoffs="Custo e velocidade podem exigir prioridades diferentes.",
        ai_recommendation="Definir uma métrica primária mensurável.",
        how_to_respond="Escolha uma alternativa ou responda livremente.",
    )

    assert question.prompt.startswith("Qual resultado")
    assert DiscoveryMode.PROMPT_DESENVOLVIMENTO.value == "prompt_desenvolvimento"


def test_question_rejects_missing_prompt_or_less_than_two_alternatives() -> None:
    with pytest.raises(ValidationError):
        Question(
            number=1,
            category="Objetivos",
            prompt="",
            why_it_matters="A resposta orienta o escopo.",
            alternatives=["Reduzir custo"],
            tradeoffs="Há impactos de prioridade.",
            ai_recommendation="Definir uma métrica.",
            how_to_respond="Responda livremente.",
        )


def test_research_plan_limits_each_turn_to_two_queries() -> None:
    plan = ResearchPlan(
        requests=[
            ResearchRequest(query="FastAPI security", topic=ResearchTopic.TECHNICAL),
            ResearchRequest(query="OAuth 2.1", topic=ResearchTopic.SECURITY),
        ]
    )

    assert len(plan.requests) == 2
    assert plan.requests[0].topic is ResearchTopic.TECHNICAL


def test_research_plan_rejects_three_queries() -> None:
    with pytest.raises(ValidationError):
        ResearchPlan(
            requests=[
                ResearchRequest(query="consulta um"),
                ResearchRequest(query="consulta dois"),
                ResearchRequest(query="consulta três"),
            ]
        )


def test_validation_report_serializes_a_repairable_failure() -> None:
    report = PromptValidationReport(
        valid=False,
        missing_sections=["## 17. Plano de execução"],
        missing_prompt_topics=["segurança"],
    )

    assert report.repaired is False
    assert report.valid is False
    assert report.missing_prompt_topics == ["segurança"]


def test_source_kind_has_an_unknown_default_for_legacy_findings() -> None:
    assert SourceKind.UNKNOWN.value == "unknown"
