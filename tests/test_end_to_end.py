import pytest

from boostprompt.graph.workflow import TurnWorkflow, WorkflowAgents
from boostprompt.models.schemas import (
    DiscoveryMode,
    Question,
    QuestionGuide,
    SessionSummary,
)
from boostprompt.services.discovery_workflow import DiscoveryWorkflowService


def question(number: int) -> Question:
    return Question(
        number=number,
        category="Escopo",
        prompt=f"Qual decisão número {number} deve ser tomada?",
        why_it_matters="Evita premissas no roteiro.",
        alternatives=["Alternativa A", "Alternativa B"],
        tradeoffs="Custo versus prazo.",
        ai_recommendation="Priorizar a alternativa A.",
        how_to_respond="Escolha uma alternativa.",
    )


class FailingDiscovery:
    async def ask_next(self, **_kwargs):
        raise AssertionError("O discovery interativo não deve rodar no modo cliente.")


class FakeGuide:
    async def create_guide(self, *, demand: str, research_context: str) -> QuestionGuide:
        assert demand == "Portal para fornecedores"
        assert research_context == ""
        return QuestionGuide(
            markdown="# Perguntas para Discovery com o Cliente\n\n## Demanda informada\nPortal",
            questions=[question(number) for number in range(1, 31)],
        )


class FakeFinalAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, state):
        self.calls += 1
        return state


class FakeSummaryAgent:
    async def summarize(self, **_kwargs) -> SessionSummary:
        return SessionSummary()


@pytest.mark.asyncio
async def test_client_guide_is_persisted_without_running_scope_final_agents(tmp_path) -> None:
    architecture = FakeFinalAgent()
    security = FakeFinalAgent()
    delivery = FakeFinalAgent()
    synthesis = FakeFinalAgent()
    workflow = TurnWorkflow(
        WorkflowAgents(
            discovery=FailingDiscovery(),
            architecture=architecture,
            security=security,
            delivery=delivery,
            synthesis=synthesis,
            question_guide=FakeGuide(),
        )
    )
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=workflow,
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session(
        "Portal", DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE
    )

    result = await service.submit_answer(session.id, "Portal para fornecedores")

    assert result.final_markdown is not None
    assert result.final_markdown.startswith("# Perguntas para Discovery com o Cliente")
    assert architecture.calls == security.calls == delivery.calls == synthesis.calls == 0
    assert [message["content"] for message in service.repository.get_messages(session.id)] == [
        "Portal para fornecedores",
        "Roteiro de perguntas para o cliente gerado.",
    ]
