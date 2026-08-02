"""Workflow LangGraph orientado a um único turno de discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from boostprompt.agents.discovery import DiscoveryAgent, format_question
from boostprompt.agents.question_guide import QuestionGuideAgent
from boostprompt.models.schemas import DiscoveryMode, ResearchFinding, TurnResult
from boostprompt.research.duckduckgo_mcp import ResearchUnavailableError


class FinalAgent(Protocol):
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]: ...


class ResearchProvider(Protocol):
    async def search(self, query: str, decision_context: str = "") -> list[ResearchFinding]: ...


class TurnState(TypedDict, total=False):
    mode: DiscoveryMode
    context: dict[str, Any]
    messages: list[Any]
    decisions: list[dict[str, Any]]
    questions_count: int
    last_user_message: str
    research_query: str
    research_context: str
    research_findings: list[ResearchFinding]
    research_references: list[ResearchFinding]
    research_degraded: bool
    should_finalize: bool
    awaiting_user_answer: bool
    display_message: str
    final_markdown: str | None
    discovery_summary: str


@dataclass(frozen=True)
class WorkflowAgents:
    """Dependências de agente necessárias para cada caminho do grafo."""

    discovery: DiscoveryAgent
    architecture: FinalAgent
    security: FinalAgent
    delivery: FinalAgent
    synthesis: FinalAgent
    question_guide: QuestionGuideAgent | None = None


class TurnWorkflow:
    """Executa no máximo uma pergunta interativa a cada submissão do usuário."""

    def __init__(
        self,
        agents: WorkflowAgents,
        research_provider: ResearchProvider | None = None,
    ) -> None:
        self.agents = agents
        self.research_provider = research_provider
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(TurnState)
        graph.add_node("research", self._research)
        graph.add_node("discovery", self._discovery)
        graph.add_node("question_guide", self._question_guide)
        graph.add_node("architecture", self._architecture)
        graph.add_node("security", self._security)
        graph.add_node("delivery", self._delivery)
        graph.add_node("synthesis", self._synthesis)
        graph.add_node("complete", self._complete)

        graph.add_edge(START, "research")
        graph.add_conditional_edges(
            "research",
            self._route_after_research,
            {
                "guide": "question_guide",
                "discovery": "discovery",
                "finalize": "architecture",
            },
        )
        graph.add_conditional_edges(
            "discovery",
            self._route_after_discovery,
            {"wait": "complete", "finalize": "architecture"},
        )
        graph.add_edge("question_guide", "complete")
        graph.add_edge("architecture", "security")
        graph.add_edge("security", "delivery")
        graph.add_edge("delivery", "synthesis")
        graph.add_edge("synthesis", "complete")
        graph.add_edge("complete", END)
        return graph.compile()

    async def run_turn(self, state: TurnState) -> TurnResult:
        """Executa o grafo e devolve somente os dados que a TUI precisa renderizar."""

        final_state = await self.graph.ainvoke(state)
        final_markdown = final_state.get("final_markdown")
        awaiting = bool(final_state.get("awaiting_user_answer", final_markdown is None))
        display_message = final_state.get("display_message")
        if not display_message:
            display_message = "A sessão foi atualizada."
        return TurnResult(
            display_message=display_message,
            context=final_state.get("context", {}),
            questions_count=int(final_state.get("questions_count", 0)),
            awaiting_user_answer=awaiting,
            final_markdown=final_markdown,
            research_findings=final_state.get("research_findings", []),
            research_degraded=bool(final_state.get("research_degraded", False)),
        )

    async def _research(self, state: TurnState) -> dict[str, Any]:
        query = state.get("research_query", "").strip()
        existing_references = state.get("research_references", [])
        if not query:
            return {
                "research_context": self._render_references(existing_references),
                "research_findings": [],
                "research_references": existing_references,
                "research_degraded": False,
            }
        if self.research_provider is None:
            return {
                "research_context": "Pesquisa não configurada; recomendações em modo degradado.",
                "research_findings": [],
                "research_references": existing_references,
                "research_degraded": True,
            }
        try:
            findings = await self.research_provider.search(query, decision_context="discovery")
        except ResearchUnavailableError:
            return {
                "research_context": "Pesquisa DuckDuckGo indisponível; recomendações em modo degradado.",
                "research_findings": [],
                "research_references": existing_references,
                "research_degraded": True,
            }
        existing_urls = {item.url for item in existing_references}
        fresh_findings = [item for item in findings if item.url not in existing_urls]
        references = [*existing_references, *fresh_findings]
        return {
            "research_context": self._render_references(references),
            "research_findings": fresh_findings,
            "research_references": references,
            "research_degraded": False,
        }

    @staticmethod
    def _render_references(references: list[ResearchFinding]) -> str:
        return "\n".join(f"- {item.title}: {item.url}" for item in references)

    @staticmethod
    def _route_after_research(state: TurnState) -> str:
        if state["mode"] is DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE:
            return "guide"
        return "discovery"

    async def _question_guide(self, state: TurnState) -> dict[str, Any]:
        if self.agents.question_guide is None:
            raise RuntimeError("QuestionGuideAgent não foi configurado.")
        guide = await self.agents.question_guide.create_guide(
            demand=state.get("last_user_message") or state.get("context", {}).get("necessidade", ""),
            research_context=state.get("research_context", ""),
        )
        return {
            "questions_count": len(guide.questions),
            "final_markdown": guide.markdown,
            "display_message": "Roteiro de perguntas para o cliente gerado.",
            "awaiting_user_answer": False,
        }

    async def _discovery(self, state: TurnState) -> dict[str, Any]:
        questions_count = int(state.get("questions_count", 0))
        response = await self.agents.discovery.ask_next(
            context=state.get("context", {}),
            messages=state.get("messages", []),
            questions_count=questions_count,
            research_context=state.get("research_context", ""),
        )
        context = state.get("context", {}).copy()
        context.update(response.context_update)
        if response.question is None or questions_count >= 50:
            if questions_count < 30:
                raise RuntimeError("Discovery encerrou antes de 30 perguntas respondidas.")
            return {
                "context": context,
                "discovery_summary": response.summary,
                "should_finalize": True,
                "awaiting_user_answer": False,
            }
        return {
            "context": context,
            "questions_count": questions_count + 1,
            "discovery_summary": response.summary,
            "display_message": format_question(response.question),
            "should_finalize": False,
            "awaiting_user_answer": True,
        }

    @staticmethod
    def _route_after_discovery(state: TurnState) -> str:
        return "finalize" if state.get("should_finalize", False) else "wait"

    async def _architecture(self, state: TurnState) -> dict[str, Any]:
        return await self.agents.architecture.execute(dict(state))

    async def _security(self, state: TurnState) -> dict[str, Any]:
        return await self.agents.security.execute(dict(state))

    async def _delivery(self, state: TurnState) -> dict[str, Any]:
        return await self.agents.delivery.execute(dict(state))

    async def _synthesis(self, state: TurnState) -> dict[str, Any]:
        return await self.agents.synthesis.execute(dict(state))

    @staticmethod
    def _complete(state: TurnState) -> dict[str, Any]:
        return {
            "awaiting_user_answer": bool(state.get("awaiting_user_answer", False)),
            "display_message": state.get("display_message", "A sessão foi atualizada."),
        }


def create_turn_workflow(
    agents: WorkflowAgents,
    research_provider: ResearchProvider | None = None,
) -> TurnWorkflow:
    """Factory explícita para a orquestração LangGraph por turno."""

    return TurnWorkflow(agents=agents, research_provider=research_provider)


def create_boostprompt_workflow(
    discovery_agent: DiscoveryAgent,
    architecture_agent: FinalAgent,
    security_agent: FinalAgent,
    delivery_agent: FinalAgent,
    synthesis_agent: FinalAgent,
    _memory_agent: Any | None = None,
    debug: bool = False,
) -> tuple[Any, Any]:
    """Compatibilidade temporária para consumidores da factory anterior."""

    del debug
    workflow = create_turn_workflow(
        WorkflowAgents(
            discovery=discovery_agent,
            architecture=architecture_agent,
            security=security_agent,
            delivery=delivery_agent,
            synthesis=synthesis_agent,
        )
    )
    return workflow.graph, workflow.run_turn
