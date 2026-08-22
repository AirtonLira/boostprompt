import pytest

from boostprompt.agents.discovery import DiscoveryResponse
from boostprompt.graph.workflow import TurnWorkflow, WorkflowAgents
from boostprompt.models.schemas import (
    DiscoveryMode,
    Message,
    Question,
    ResearchFinding,
    ResearchPlan,
    ResearchRequest,
)
from boostprompt.research import ResearchUnavailableError
from boostprompt.services.prompt_artifact import PromptArtifactValidator


def question() -> Question:
    return Question(
        number=2,
        category="Objetivos",
        prompt="Qual resultado deve definir o sucesso?",
        why_it_matters="Orienta os critérios de aceite.",
        alternatives=["Reduzir custo", "Aumentar conversão"],
        tradeoffs="As prioridades alteram o roadmap.",
        ai_recommendation="Definir uma métrica primária.",
        how_to_respond="Responda livremente.",
    )


class FakeDiscovery:
    def __init__(self, response: DiscoveryResponse) -> None:
        self.response = response
        self.calls = 0

    async def ask_next(self, **_kwargs) -> DiscoveryResponse:
        self.calls += 1
        return self.response


class FakeFinalAgent:
    def __init__(self, final_markdown: str | None = None) -> None:
        self.calls = 0
        self.final_markdown = final_markdown

    async def execute(self, state):
        self.calls += 1
        result = dict(state)
        if self.final_markdown is not None:
            result["final_markdown"] = self.final_markdown
            result["display_message"] = "Escopo final gerado."
        return result


class FakeResearchProvider:
    def __init__(self, findings: list[ResearchFinding] | None = None, unavailable: bool = False) -> None:
        self.findings = findings or []
        self.unavailable = unavailable

    async def search(self, request: ResearchRequest) -> list[ResearchFinding]:
        assert request.decision_context == "discovery"
        if self.unavailable:
            raise ResearchUnavailableError("MCP indisponível")
        return self.findings


class ReferencesCapturingFinalAgent(FakeFinalAgent):
    def __init__(self) -> None:
        super().__init__()
        self.research_references = []

    async def execute(self, state):
        self.research_references = state.get("research_references", [])
        return await super().execute(state)


class FakeQuestionGuide:
    def __init__(self) -> None:
        self.calls = 0

    async def create_guide(self, *, demand: str, research_context: str):
        from boostprompt.models.schemas import QuestionGuide

        self.calls += 1
        assert demand == "Preciso de uma API."
        assert research_context == ""
        return QuestionGuide(
            markdown="# Perguntas para Discovery com o Cliente\n",
            questions=[question()] * 30,
        )


class RepairingSynthesis(FakeFinalAgent):
    def __init__(self, first: str, repaired: str) -> None:
        super().__init__()
        self.first = first
        self.repaired = repaired
        self.repair_calls = 0

    async def execute(self, state):
        self.calls += 1
        return {**state, "final_markdown": self.first}

    async def repair(self, markdown, report, state):
        self.repair_calls += 1
        assert markdown == self.first
        assert report.valid is False
        return self.repaired


def turn_state(questions_count: int) -> dict:
    return {
        "mode": DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        "context": {"necessidade": "Criar uma API"},
        "messages": [Message(role="user", content="Preciso de uma API.")],
        "questions_count": questions_count,
        "last_user_message": "Preciso de uma API.",
    }


@pytest.mark.asyncio
async def test_workflow_calls_discovery_once_then_waits_for_the_next_user_answer() -> None:
    discovery = FakeDiscovery(
        DiscoveryResponse(question=question(), should_continue=True, summary="Objetivo inicial coletado.")
    )
    agents = WorkflowAgents(
        discovery=discovery,
        architecture=FakeFinalAgent(),
        security=FakeFinalAgent(),
        delivery=FakeFinalAgent(),
        synthesis=FakeFinalAgent("# Escopo"),
    )

    result = await TurnWorkflow(agents).run_turn(turn_state(questions_count=1))

    assert discovery.calls == 1
    assert result.awaiting_user_answer is True
    assert result.questions_count == 2
    assert "Qual resultado deve definir o sucesso?" in result.display_message
    assert agents.synthesis.calls == 0


@pytest.mark.asyncio
async def test_workflow_runs_final_agents_only_when_discovery_can_finish_after_minimum() -> None:
    discovery = FakeDiscovery(
        DiscoveryResponse(question=None, should_continue=False, summary="Lacunas críticas fechadas.")
    )
    architecture = FakeFinalAgent()
    security = FakeFinalAgent()
    delivery = FakeFinalAgent()
    synthesis = FakeFinalAgent("# Escopo da Solução")
    agents = WorkflowAgents(
        discovery=discovery,
        architecture=architecture,
        security=security,
        delivery=delivery,
        synthesis=synthesis,
    )

    result = await TurnWorkflow(agents).run_turn(turn_state(questions_count=30))

    assert discovery.calls == 1
    assert architecture.calls == security.calls == delivery.calls == synthesis.calls == 1
    assert result.awaiting_user_answer is False
    assert result.final_markdown == "# Escopo da Solução"


@pytest.mark.asyncio
async def test_workflow_finalizes_without_discovery_when_forced() -> None:
    discovery = FakeDiscovery(
        DiscoveryResponse(question=question(), should_continue=True, summary="Não usar.")
    )
    synthesis = FakeFinalAgent("# Escopo parcial")
    workflow = TurnWorkflow(
        WorkflowAgents(
            discovery=discovery,
            architecture=FakeFinalAgent(),
            security=FakeFinalAgent(),
            delivery=FakeFinalAgent(),
            synthesis=synthesis,
        )
    )
    state = turn_state(questions_count=10)
    state["force_finalize"] = True

    result = await workflow.run_turn(state)

    assert discovery.calls == 0
    assert synthesis.calls == 1
    assert result.final_markdown == "# Escopo parcial"
    assert result.awaiting_user_answer is False


@pytest.mark.asyncio
async def test_workflow_keeps_prior_references_and_adds_the_new_exa_result() -> None:
    """Evita perder fontes de pesquisas anteriores antes de gerar o escopo final."""

    existing = ResearchFinding(
        title="Documentação DuckDB",
        url="https://duckdb.org/docs/",
        excerpt="Persistência local.",
    )
    new = ResearchFinding(
        title="Documentação LangGraph",
        url="https://langchain-ai.github.io/langgraph/",
        excerpt="Orquestração de agentes.",
    )
    architecture = ReferencesCapturingFinalAgent()
    agents = WorkflowAgents(
        discovery=FakeDiscovery(
            DiscoveryResponse(question=None, should_continue=False, summary="Concluído.")
        ),
        architecture=architecture,
        security=FakeFinalAgent(),
        delivery=FakeFinalAgent(),
        synthesis=FakeFinalAgent("# Escopo"),
    )
    state = turn_state(questions_count=50)
    state.update(
        research_plan=ResearchPlan(
            requests=[ResearchRequest(query="LangGraph e DuckDB")]
        ),
        research_references=[existing],
    )

    result = await TurnWorkflow(
        agents,
        research_provider=FakeResearchProvider([new]),
    ).run_turn(state)

    assert [reference.url for reference in architecture.research_references] == [
        "https://duckdb.org/docs/",
        "https://langchain-ai.github.io/langgraph/",
    ]
    assert result.research_findings == [new]


@pytest.mark.asyncio
async def test_client_guide_bypasses_the_interview_and_final_scope_agents() -> None:
    guide = FakeQuestionGuide()
    discovery = FakeDiscovery(
        DiscoveryResponse(question=question(), should_continue=True, summary="Não usar.")
    )
    architecture = FakeFinalAgent()
    security = FakeFinalAgent()
    delivery = FakeFinalAgent()
    synthesis = FakeFinalAgent("# Não usar")
    agents = WorkflowAgents(
        discovery=discovery,
        architecture=architecture,
        security=security,
        delivery=delivery,
        synthesis=synthesis,
        question_guide=guide,
    )
    state = turn_state(questions_count=0)
    state["mode"] = DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE

    result = await TurnWorkflow(agents).run_turn(state)

    assert guide.calls == 1
    assert discovery.calls == architecture.calls == security.calls == delivery.calls == synthesis.calls == 0
    assert result.final_markdown == "# Perguntas para Discovery com o Cliente\n"
    assert result.questions_count == 30


@pytest.mark.asyncio
async def test_workflow_uses_degraded_research_without_blocking_the_next_question() -> None:
    discovery = FakeDiscovery(
        DiscoveryResponse(question=question(), should_continue=True, summary="Prosseguir sem fontes.")
    )
    agents = WorkflowAgents(
        discovery=discovery,
        architecture=FakeFinalAgent(),
        security=FakeFinalAgent(),
        delivery=FakeFinalAgent(),
        synthesis=FakeFinalAgent("# Escopo"),
    )
    state = turn_state(questions_count=10)
    state["research_plan"] = ResearchPlan(requests=[ResearchRequest(query="LangGraph")])

    result = await TurnWorkflow(
        agents,
        research_provider=FakeResearchProvider(unavailable=True),
    ).run_turn(state)

    assert discovery.calls == 1
    assert result.research_degraded is True
    assert result.awaiting_user_answer is True


@pytest.mark.asyncio
async def test_workflow_incorporates_the_fiftieth_answer_before_forced_finalization() -> None:
    discovery = FakeDiscovery(
        DiscoveryResponse(
            question=question(),
            should_continue=True,
            context_update={"decisao_final": "Usar implantação gradual."},
            summary="Última resposta incorporada.",
        )
    )
    synthesis = FakeFinalAgent("# Escopo final")
    agents = WorkflowAgents(
        discovery=discovery,
        architecture=FakeFinalAgent(),
        security=FakeFinalAgent(),
        delivery=FakeFinalAgent(),
        synthesis=synthesis,
    )

    result = await TurnWorkflow(agents).run_turn(turn_state(questions_count=50))

    assert discovery.calls == 1
    assert synthesis.calls == 1
    assert result.final_markdown == "# Escopo final"
    assert result.questions_count == 50
    assert result.context["decisao_final"] == "Usar implantação gradual."


@pytest.mark.asyncio
async def test_workflow_repairs_an_invalid_document_once() -> None:
    synthesis = RepairingSynthesis(first="# Escopo da Solução", repaired="# Ainda incompleto")
    workflow = TurnWorkflow(
        WorkflowAgents(
            discovery=FakeDiscovery(
                DiscoveryResponse(question=None, should_continue=False, summary="Concluído.")
            ),
            architecture=FakeFinalAgent(),
            security=FakeFinalAgent(),
            delivery=FakeFinalAgent(),
            synthesis=synthesis,
            document_validator=PromptArtifactValidator(),
        )
    )

    result = await workflow.run_turn(turn_state(questions_count=30))

    assert synthesis.repair_calls == 1
    assert result.validation_report is not None
    assert result.validation_report.valid is False
    assert result.validation_report.repaired is True
