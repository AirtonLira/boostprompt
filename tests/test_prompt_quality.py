import pytest

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


@pytest.mark.parametrize(
    "context",
    [
        {"necessidade": "Portal", "problema": "Atrasos", "objetivo": "Reduzir prazo"},
        {"usuarios": ["Lojistas"], "stakeholders": ["Operações"]},
        {"tipo_solucao": "Portal", "requisitos_funcionais": ["Cadastrar pedido"]},
        {"requisitos_nao_funcionais": ["Disponibilidade de 99,9%"]},
        {"dados": ["Pedidos"], "integracoes": ["ERP"]},
        {"arquitetura": ["Monólito"], "plataformas": ["Web"], "dominio": "Varejo"},
        {"seguranca": ["OAuth"]},
        {"entrega": ["MVP"], "operacao": ["SRE"]},
        {"restricoes": ["Prazo"], "premissas": ["Equipe disponível"], "riscos": ["ERP"]},
    ],
)
def test_each_approved_coverage_group_counts_once(context: dict[str, object]) -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context=context,
        decisions=[],
        questions_count=0,
    )

    assert evaluation.coverage == 11


def test_one_field_from_each_coverage_group_reaches_full_coverage() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context={
            "objetivo": "Reduzir prazo",
            "usuarios": ["Lojistas"],
            "tipo_solucao": "Portal",
            "requisitos_nao_funcionais": ["Disponibilidade de 99,9%"],
            "dados": ["Pedidos"],
            "plataformas": ["Web"],
            "seguranca": ["OAuth"],
            "operacao": ["SRE"],
            "premissas": ["Equipe disponível"],
        },
        decisions=[],
        questions_count=0,
    )

    assert evaluation.coverage == 100


def test_decision_clarity_counts_each_non_empty_evidence_and_uncertainty_item() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context={
            "objetivo": "Reduzir prazo",
            "usuarios": ["Lojistas", " ", "Operações"],
            "requisitos_funcionais": ["Cadastrar pedido", "Consultar pedido"],
            "pendencias": ["Definir SLA", " ", "Confirmar volume"],
            "riscos": ["Dependência externa", "Indisponibilidade", ""],
        },
        decisions=[
            {"decision": "Entregar MVP"},
            {"decision": "Usar autenticação federada"},
            {"decision": " "},
        ],
        questions_count=0,
    )

    # 7 evidências e 4 incertezas: round(100 * 7 / (10 + 2 * 4)).
    assert evaluation.decision_clarity == 39


def test_decision_clarity_caps_individual_evidence_items_at_ten() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context={"usuarios": [f"Perfil {number}" for number in range(12)]},
        decisions=[],
        questions_count=0,
    )

    assert evaluation.decision_clarity == 100


def test_client_guide_marks_quality_as_not_applicable() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE,
        context={"necessidade": "Portal"},
        decisions=[],
        questions_count=30,
    )
    assert evaluation.applicable is False
    assert (
        evaluation.coverage,
        evaluation.decision_clarity,
        evaluation.prompt_readiness,
    ) == (None, None, None)
    assert evaluation.status_text == "Avaliação não aplicável ao roteiro gerado diretamente."
