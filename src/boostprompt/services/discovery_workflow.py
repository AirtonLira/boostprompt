"""Serviço de aplicação para um turno durável de discovery."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from pydantic_ai.models import Model

from boostprompt.agents.architecture import create_architecture_agent
from boostprompt.agents.delivery import create_delivery_agent
from boostprompt.agents.discovery import create_discovery_agent
from boostprompt.agents.question_guide import QuestionGuideAgent
from boostprompt.agents.research_planner import ResearchPlannerAgent
from boostprompt.agents.security import create_security_agent
from boostprompt.agents.summary import SummaryAgent
from boostprompt.agents.synthesis import create_synthesis_agent
from boostprompt.graph.workflow import TurnState, TurnWorkflow, WorkflowAgents
from boostprompt.llm import ModelProvider, OpenAICompatibleSettings
from boostprompt.memory.duckdb_store import DuckDBStore, ResumedSession
from boostprompt.models.schemas import (
    DiscoveryMode,
    Message,
    PromptQualityEvaluation,
    ResearchFinding,
    Session,
    SessionSummary,
    TurnResult,
)
from boostprompt.research import ExaResearchProvider
from boostprompt.services.prompt_artifact import PromptArtifactValidator
from boostprompt.services.prompt_quality import PromptQualityEvaluator

MINIMUM_PARTIAL_PROMPT_QUESTIONS = 10


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

    def __init__(
        self,
        repository: DuckDBStore,
        workflow: TurnRunner,
        summary_agent: SessionSummarizer,
        *,
        recent_message_limit: int = 10,
        summary_threshold: int = 20,
        quality_evaluator: PromptQualityEvaluator | None = None,
    ) -> None:
        self.repository = repository
        self.workflow = workflow
        self.summary_agent = summary_agent
        self.recent_message_limit = recent_message_limit
        self.summary_threshold = summary_threshold
        self.quality_evaluator = quality_evaluator or PromptQualityEvaluator()

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
        provider: ModelProvider,
        db_path: str | Path | None = None,
        model: Model | str | None = None,
    ) -> DiscoveryWorkflowService:
        settings = OpenAICompatibleSettings.from_environment(provider)
        resolved_model = model or settings.build_model()
        agents = WorkflowAgents(
            discovery=create_discovery_agent(resolved_model),
            architecture=create_architecture_agent(resolved_model),
            security=create_security_agent(resolved_model),
            delivery=create_delivery_agent(resolved_model),
            synthesis=create_synthesis_agent(resolved_model),
            question_guide=QuestionGuideAgent(resolved_model),
            research_planner=ResearchPlannerAgent(resolved_model),
            document_validator=PromptArtifactValidator(),
        )
        workflow = TurnWorkflow(
            agents,
            research_provider=ExaResearchProvider(),
        )
        return cls.with_database(
            db_path=db_path or settings.database_path,
            workflow=workflow,
            summary_agent=SummaryAgent(resolved_model),
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
        answered_questions_count = resumed.session.answered_questions_count + int(
            resumed.session.questions_count > 0
        )
        evaluation = self._evaluate_quality(
            resumed,
            {**resumed.context, **result.context},
            result.questions_count,
        )
        evaluation = evaluation.model_copy(update={"validation_report": result.validation_report})
        result = result.model_copy(
            update={
                "answered_questions_count": answered_questions_count,
                "quality_evaluation": evaluation,
            }
        )
        self.repository.append_turn(
            session_id,
            clean_answer,
            result.display_message,
            result.context,
            result.questions_count,
            result.final_markdown,
            status=(
                "completed"
                if result.final_markdown is not None
                and not result.awaiting_user_answer
                and result.validation_report is not None
                and result.validation_report.valid
                else "needs_review" if result.final_markdown is not None else None
            ),
            quality_evaluation=evaluation,
            answered_questions_count=answered_questions_count,
        )
        if result.research_findings:
            self.repository.save_research_findings(session_id, result.research_findings)
        await self._summarize_if_needed(session_id, result.context)
        return result

    def resume_session(self, session_id: str) -> ResumedSession:
        return self.repository.load_for_resume(session_id, self.recent_message_limit)

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.repository.list_sessions()

    def delete_session(self, session_id: str) -> None:
        self.repository.delete_session(session_id)

    async def generate_partial_prompt(self, session_id: str) -> TurnResult:
        """Gera um rascunho do prompt sem encerrar a entrevista em andamento."""

        resumed = self.repository.load_for_resume(session_id, self.recent_message_limit)
        if resumed.session.mode is not DiscoveryMode.PROMPT_DESENVOLVIMENTO:
            raise ValueError(
                "A geração antecipada está disponível apenas para entrevistas de desenvolvimento."
            )
        if resumed.session.answered_questions_count < MINIMUM_PARTIAL_PROMPT_QUESTIONS:
            raise ValueError("Responda pelo menos 10 respostas confirmadas antes de gerar o prompt.")
        state = self._build_turn_state(resumed, answer=None, force_finalize=True)
        result = await self.workflow.run_turn(state)
        final_markdown = result.final_markdown
        if final_markdown is None:
            raise RuntimeError("Não foi possível gerar o prompt parcial.")
        evaluation = self._evaluate_quality(
            resumed,
            {**resumed.context, **result.context},
            result.questions_count,
        )
        evaluation = evaluation.model_copy(update={"validation_report": result.validation_report})
        result = result.model_copy(
            update={
                "answered_questions_count": resumed.session.answered_questions_count,
                "quality_evaluation": evaluation,
            }
        )
        self.repository.save_generated_markdown(
            session_id,
            result.context,
            result.questions_count,
            "in_progress",
            final_markdown,
            quality_evaluation=evaluation,
        )
        return result

    async def continue_completed_session(self, session_id: str) -> Session:
        """Cria uma entrevista nova a partir de um resumo compacto da sessão concluída."""

        resumed = self.repository.load_for_resume(session_id, self.recent_message_limit)
        if resumed.session.status != "completed":
            raise ValueError("A continuação está disponível apenas para sessões concluídas.")
        messages = [Message.model_validate(message) for message in self.repository.get_messages(session_id)]
        if not messages:
            raise ValueError("Não há conteúdo suficiente para resumir esta sessão concluída.")
        summary = await self.summary_agent.summarize(
            previous=resumed.summary,
            messages=messages,
            context=resumed.context,
        )
        return self.repository.create_continuation(resumed.session, summary)

    def close(self) -> None:
        self.repository.close()

    def _build_turn_state(
        self,
        resumed: ResumedSession,
        answer: str | None,
        *,
        force_finalize: bool = False,
    ) -> TurnState:
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
        if answer is not None:
            context.setdefault("necessidade", answer)
        return {
            "mode": resumed.session.mode,
            "context": context,
            "messages": (
                [*resumed.messages, Message(role="user", content=answer)]
                if answer is not None
                else list(resumed.messages)
            ),
            "questions_count": resumed.session.questions_count,
            "decisions": resumed.decisions,
            "last_user_message": answer or "",
            "research_references": research_references,
            "force_finalize": force_finalize,
        }

    def _evaluate_quality(
        self,
        resumed: ResumedSession,
        context: dict[str, Any],
        questions_count: int,
    ) -> PromptQualityEvaluation:
        evaluation = self.quality_evaluator.evaluate(
            mode=resumed.session.mode,
            context=context,
            decisions=resumed.decisions,
            questions_count=questions_count,
        )
        return evaluation.model_copy(
            update={"evaluated_at": evaluation.evaluated_at.replace(tzinfo=None)}
        )

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
