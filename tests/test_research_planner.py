import pytest

from boostprompt.agents.discovery import DiscoveryResponse
from boostprompt.agents.research_planner import ResearchPlannerAgent
from boostprompt.graph.workflow import TurnWorkflow, WorkflowAgents
from boostprompt.models.schemas import (
    DiscoveryMode,
    Question,
    ResearchFinding,
    ResearchPlan,
    ResearchRequest,
)
from boostprompt.research import ResearchUnavailableError


def question() -> Question:
    return Question(
        number=2,
        category="Arquitetura",
        prompt="Qual mecanismo de autenticação a API deve usar?",
        why_it_matters="A decisão determina requisitos de segurança.",
        alternatives=["OAuth 2.1", "Chaves de API"],
        tradeoffs="OAuth oferece delegação; chaves simplificam integrações internas.",
        ai_recommendation="Avaliar OAuth 2.1 com base em referências atuais.",
        how_to_respond="Escolha uma opção ou explique a necessidade.",
    )


class FakePlanner:
    def __init__(self, calls: list[str], requests: list[ResearchRequest]) -> None:
        self.calls = calls
        self.requests = requests

    async def plan(self, **_kwargs) -> ResearchPlan:
        self.calls.append("plan")
        return ResearchPlan(requests=self.requests, reason="A decisão depende de padrão atual.")


class CapturingResearchProvider:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def search(self, request: ResearchRequest) -> list[ResearchFinding]:
        self.calls.append(f"search:{request.query}")
        return [
            ResearchFinding(
                source_id="oauth-rfc",
                title="OAuth 2.1",
                url="https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1",
                excerpt="Especificação de OAuth.",
                query=request.query,
                decision_context=request.decision_context,
            )
        ]


class UnavailableResearchProvider:
    async def search(self, _request: ResearchRequest) -> list[ResearchFinding]:
        raise ResearchUnavailableError("Exa indisponível")


class CapturingDiscovery:
    def __init__(self, calls: list[str], expects_source: bool = True) -> None:
        self.calls = calls
        self.expects_source = expects_source

    async def ask_next(self, *, research_context: str, **_kwargs) -> DiscoveryResponse:
        self.calls.append("discovery")
        if self.expects_source:
            assert "oauth-rfc" in research_context
        return DiscoveryResponse(question=question(), should_continue=True, summary="Contexto atualizado.")


class StaticFinalAgent:
    async def execute(self, state: dict[str, object]) -> dict[str, object]:
        return state


def state() -> dict[str, object]:
    return {
        "mode": DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        "context": {"necessidade": "Criar uma API"},
        "messages": [],
        "questions_count": 1,
        "last_user_message": "Preciso de OAuth.",
    }


@pytest.mark.asyncio
async def test_research_planner_uses_the_context_and_returns_structured_requests() -> None:
    captured_prompts: list[str] = []

    async def runner(prompt: str) -> ResearchPlan:
        captured_prompts.append(prompt)
        return ResearchPlan(requests=[ResearchRequest(query="OAuth 2.1 specification")])

    plan = await ResearchPlannerAgent(runner=runner).plan(
        context={"necessidade": "Criar uma API"}, messages=[], questions_count=1
    )

    assert plan.requests[0].query == "OAuth 2.1 specification"
    assert "Criar uma API" in captured_prompts[0]


@pytest.mark.asyncio
async def test_workflow_researches_planned_decision_before_generating_question() -> None:
    calls: list[str] = []
    workflow = TurnWorkflow(
        agents=WorkflowAgents(
            discovery=CapturingDiscovery(calls, expects_source=False),
            architecture=StaticFinalAgent(),
            security=StaticFinalAgent(),
            delivery=StaticFinalAgent(),
            synthesis=StaticFinalAgent(),
            research_planner=FakePlanner(calls, [ResearchRequest(query="OAuth 2.1")]),
        ),
        research_provider=CapturingResearchProvider(calls),
    )

    result = await workflow.run_turn(state())

    assert calls == ["plan", "search:OAuth 2.1", "discovery"]
    assert result.research_degraded is False
    assert result.research_findings[0].source_id == "oauth-rfc"


@pytest.mark.asyncio
async def test_workflow_continues_when_planned_search_is_unavailable() -> None:
    calls: list[str] = []
    workflow = TurnWorkflow(
        agents=WorkflowAgents(
            discovery=CapturingDiscovery(calls, expects_source=False),
            architecture=StaticFinalAgent(),
            security=StaticFinalAgent(),
            delivery=StaticFinalAgent(),
            synthesis=StaticFinalAgent(),
            research_planner=FakePlanner(calls, [ResearchRequest(query="OAuth 2.1")]),
        ),
        research_provider=UnavailableResearchProvider(),
    )

    result = await workflow.run_turn(state())

    assert result.awaiting_user_answer is True
    assert result.research_degraded is True
