"""Serviço de aplicação para um turno durável de discovery."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from boostprompt.agents.architecture import create_architecture_agent
from boostprompt.agents.delivery import create_delivery_agent
from boostprompt.agents.discovery import create_discovery_agent
from boostprompt.agents.question_guide import QuestionGuideAgent
from boostprompt.agents.security import create_security_agent
from boostprompt.agents.summary import SummaryAgent
from boostprompt.agents.synthesis import create_synthesis_agent
from boostprompt.graph.workflow import TurnState, TurnWorkflow, WorkflowAgents
from boostprompt.memory.duckdb_store import DuckDBStore, ResumedSession
from boostprompt.models.schemas import (
    DiscoveryMode,
    Message,
    ResearchFinding,
    Session,
    SessionSummary,
    TurnResult,
)
from boostprompt.research.duckduckgo_mcp import DuckDuckGoMCPResearchProvider


class TurnRunner(Protocol):
    async def run_turn(self, state: TurnState) -> TurnResult: ...


class SessionSummarizer(Protocol):
    async def summarize(
        self,
        *,
        previous: SessionSummary | None,
        messages: Sequence[Message],
        context: dict[str, Any],
    ) -> SessionSummary: ...


class DiscoveryWorkflowService:
    """Centraliza durabilidade e evita que a TUI monte estado de agentes."""

    technical_terms = (
        "api",
        "arquitetura",
        "banco",
        "cloud",
        "compliance",
        "deploy",
        "framework",
        "ia",
        "integração",
        "langgraph",
        "modelo",
        "segurança",
    )

    def __init__(
        self,
        repository: DuckDBStore,
        workflow: TurnRunner,
        summary_agent: SessionSummarizer,
        *,
        recent_message_limit: int = 10,
        summary_threshold: int = 20,
    ) -> None:
        self.repository = repository
        self.workflow = workflow
        self.summary_agent = summary_agent
        self.recent_message_limit = recent_message_limit
        self.summary_threshold = summary_threshold

    @classmethod
    def with_database(
        cls,
        *,
        db_path: str | Path,
        workflow: TurnRunner,
        summary_agent: SessionSummarizer,
        recent_message_limit: int = 10,
        summary_threshold: int = 20,
    ) -> DiscoveryWorkflowService:
        return cls(
            repository=DuckDBStore(db_path),
            workflow=workflow,
            summary_agent=summary_agent,
            recent_message_limit=recent_message_limit,
            summary_threshold=summary_threshold,
        )

    @classmethod
    def create_default(
        cls,
        db_path: str | Path = "data/boostprompt.db",
        model: str = "openai:gpt-4o-mini",
    ) -> DiscoveryWorkflowService:
        agents = WorkflowAgents(
            discovery=create_discovery_agent(model),
            architecture=create_architecture_agent(model),
            security=create_security_agent(model),
            delivery=create_delivery_agent(model),
            synthesis=create_synthesis_agent(model),
            question_guide=QuestionGuideAgent(model),
        )
        workflow = TurnWorkflow(
            agents,
            research_provider=DuckDuckGoMCPResearchProvider(),
        )
        return cls.with_database(
            db_path=db_path,
            workflow=workflow,
            summary_agent=SummaryAgent(model),
        )

    async def create_session(self, name: str, mode: DiscoveryMode) -> Session:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("O nome da sessão é obrigatório.")
        return self.repository.create_session(clean_name, mode)

    async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
        clean_answer = answer.strip()
        if not clean_answer:
            raise ValueError("A resposta não pode estar vazia.")

        resumed = self.repository.load_for_resume(session_id, self.recent_message_limit)
        state = self._build_turn_state(resumed, clean_answer)
        result = await self.workflow.run_turn(state)
        self.repository.append_turn(
            session_id,
            clean_answer,
            result.display_message,
            result.context,
            result.questions_count,
            result.final_markdown,
        )
        if result.research_findings:
            self.repository.save_research_findings(
                session_id,
                state.get("research_query", ""),
                result.research_findings,
            )
        await self._summarize_if_needed(session_id, result.context)
        return result

    def resume_session(self, session_id: str) -> ResumedSession:
        return self.repository.load_for_resume(session_id, self.recent_message_limit)

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.repository.list_sessions()

    def close(self) -> None:
        self.repository.close()

    def _build_turn_state(self, resumed: ResumedSession, answer: str) -> TurnState:
        context = resumed.context.copy()
        summary_context = resumed.summary.model_dump(
            mode="json", exclude={"summarized_through_sequence"}
        )
        if any(summary_context.values()):
            context["resumo_da_sessao"] = summary_context
        research_references = [
            ResearchFinding.model_validate(finding)
            for finding in self.repository.get_research_findings(resumed.session.id)
        ]
        context.setdefault("modo_saida", resumed.session.mode.value)
        context.setdefault("nome_projeto", resumed.session.nome)
        context.setdefault("necessidade", answer)
        return {
            "mode": resumed.session.mode,
            "context": context,
            "messages": [*resumed.messages, Message(role="user", content=answer)],
            "questions_count": resumed.session.questions_count,
            "decisions": resumed.decisions,
            "last_user_message": answer,
            "research_query": self._research_query(answer),
            "research_references": research_references,
        }

    def _research_query(self, answer: str) -> str:
        terms_in_answer = set(re.findall(r"[\wÀ-ÿ]+", answer.casefold()))
        return answer if any(term in terms_in_answer for term in self.technical_terms) else ""

    async def _summarize_if_needed(self, session_id: str, context: dict[str, Any]) -> None:
        previous = self.repository.get_latest_summary(session_id)
        after_sequence = previous.summarized_through_sequence if previous else 0
        messages = self.repository.get_messages_after_sequence(session_id, after_sequence)
        if len(messages) <= self.summary_threshold:
            return
        summary = await self.summary_agent.summarize(
            previous=previous,
            messages=messages,
            context=context,
        )
        latest_sequence = messages[-1].sequence
        if latest_sequence is None:  # pragma: no cover - sequência é obrigatória no repositório
            raise RuntimeError("Mensagem sem sequência não pode ser resumida.")
        self.repository.save_summary(
            session_id,
            summary.model_copy(update={"summarized_through_sequence": latest_sequence}),
        )
