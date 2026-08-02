import pytest
from pydantic import ValidationError

from boostprompt.models.schemas import DiscoveryMode, Question


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
