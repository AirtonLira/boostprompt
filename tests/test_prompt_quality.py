from boostprompt.models.schemas import DiscoveryMode
from boostprompt.services.prompt_quality import PromptQualityEvaluator


def test_empty_development_context_has_zero_scores() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context={},
        decisions=[],
        questions_count=0,
    )
    assert (evaluation.coverage, evaluation.decision_clarity, evaluation.prompt_readiness) == (
        0,
        0,
        0,
    )


def test_covered_blocks_and_unresolved_items_change_the_scores() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context={
            "necessidade": "Portal",
            "objetivo": "Reduzir prazo",
            "usuarios": ["lojistas"],
            "requisitos_funcionais": ["Cadastrar pedido"],
            "seguranca": ["OAuth"],
            "pendencias": ["Definir SLA"],
            "riscos": ["Dependência externa"],
        },
        decisions=[{"decision": "Entregar MVP"}],
        questions_count=15,
    )
    assert evaluation.coverage == 56
    assert 0 < evaluation.decision_clarity < 100
    assert 0 < evaluation.prompt_readiness < 100


def test_client_guide_marks_quality_as_not_applicable() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE,
        context={"necessidade": "Portal"},
        decisions=[],
        questions_count=30,
    )
    assert evaluation.applicable is False
    assert evaluation.prompt_readiness is None
