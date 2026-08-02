import pytest

from boostprompt.graph.workflow import TurnWorkflow
from boostprompt.models.schemas import DiscoveryMode, ResearchFinding, SessionSummary, TurnResult
from boostprompt.services.discovery_workflow import DiscoveryWorkflowService


class FakeWorkflow:
    def __init__(self) -> None:
        self.states = []

    async def run_turn(self, state):
        self.states.append(state)
        return TurnResult(
            display_message="### Pergunta 1 — Objetivos\n\nQual resultado define sucesso?",
            context={**state["context"], "objetivo": "Validar a demanda"},
            questions_count=state["questions_count"] + 1,
            awaiting_user_answer=True,
        )


class FakeSummaryAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def summarize(self, *, previous, messages, context) -> SessionSummary:
        self.calls += 1
        assert messages
        return SessionSummary(
            goal=context["necessidade"],
            decisions=["Persistir cada turno"],
            pending_topics=["Definir volume"],
        )


class ResearchWorkflow:
    async def run_turn(self, state):
        return TurnResult(
            display_message="### Pergunta 1 — Arquitetura",
            context=state["context"],
            questions_count=1,
            awaiting_user_answer=True,
            research_findings=[
                ResearchFinding(
                    title="Documentação LangGraph",
                    url="https://langchain-ai.github.io/langgraph/",
                    excerpt="Persistência de grafos",
                    decision_context="discovery",
                )
            ],
        )


class ExistingReferencesWorkflow:
    def __init__(self) -> None:
        self.research_references = []

    async def run_turn(self, state):
        self.research_references = state["research_references"]
        return TurnResult(
            display_message="### Pergunta 2 — Objetivos",
            context=state["context"],
            questions_count=state["questions_count"] + 1,
            awaiting_user_answer=True,
        )


class FinalWorkflow:
    async def run_turn(self, state):
        return TurnResult(
            display_message="Escopo final gerado.",
            context=state["context"],
            questions_count=30,
            awaiting_user_answer=False,
            final_markdown="# Escopo da Solução\n\n## 1. Resumo executivo",
        )


def test_default_service_builds_all_pydantic_ai_agents(tmp_path) -> None:
    """Garante compatibilidade com a API PydanticAI instalada, sem chamar o modelo."""

    service = DiscoveryWorkflowService.create_default(tmp_path / "sessions.db")
    try:
        assert isinstance(service.workflow, TurnWorkflow)
    finally:
        service.close()


@pytest.mark.asyncio
async def test_submit_answer_persists_answer_and_next_question(tmp_path) -> None:
    workflow = FakeWorkflow()
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=workflow,
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session(
        "Pagamentos", DiscoveryMode.PROMPT_DESENVOLVIMENTO
    )

    result = await service.submit_answer(session.id, "Preciso cobrar clientes.")

    assert result.awaiting_user_answer is True
    assert [message["content"] for message in service.repository.get_messages(session.id)] == [
        "Preciso cobrar clientes.",
        "### Pergunta 1 — Objetivos\n\nQual resultado define sucesso?",
    ]
    assert workflow.states[0]["context"]["necessidade"] == "Preciso cobrar clientes."


@pytest.mark.asyncio
async def test_service_summarizes_old_messages_without_losing_key_points(tmp_path) -> None:
    summary_agent = FakeSummaryAgent()
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=FakeWorkflow(),
        summary_agent=summary_agent,
        summary_threshold=2,
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    await service.submit_answer(session.id, "Precisamos centralizar clientes.")
    await service.submit_answer(session.id, "Usuários são vendedores internos.")

    summary = service.repository.get_latest_summary(session.id)
    assert summary_agent.calls == 1
    assert summary is not None
    assert summary.goal == "Precisamos centralizar clientes."
    assert summary.pending_topics == ["Definir volume"]


@pytest.mark.asyncio
async def test_service_reinjects_the_saved_summary_and_decisions_when_resuming(tmp_path) -> None:
    """Evita que fatos resumidos desapareçam do contexto dos agentes após a retomada."""

    workflow = FakeWorkflow()
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=workflow,
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.save_summary(
        session.id,
        SessionSummary(
            goal="Centralizar clientes",
            decisions=["Priorizar vendedores internos"],
            constraints=["Atender à LGPD"],
            risks=["Base legal pendente"],
            pending_topics=["Definir prazo de retenção"],
        ),
    )
    service.repository.save_decision(
        session.id,
        category="escopo",
        decision="Lançar um MVP",
        alternatives=["Lançamento completo"],
        tradeoffs="Menor escopo reduz prazo inicial.",
    )

    await service.submit_answer(session.id, "Os usuários iniciais são vendedores.")

    state = workflow.states[0]
    assert state["context"]["resumo_da_sessao"]["risks"] == ["Base legal pendente"]
    assert state["decisions"][0]["decision"] == "Lançar um MVP"


@pytest.mark.asyncio
async def test_service_persists_the_final_markdown_for_a_later_resume(tmp_path) -> None:
    """Evita perder o artefato gerado caso o usuário feche a TUI antes de abri-lo."""

    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=FinalWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("Portal", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    await service.submit_answer(session.id, "Criar portal para fornecedores.")

    assert service.resume_session(session.id).final_markdown == (
        "# Escopo da Solução\n\n## 1. Resumo executivo"
    )


def test_research_query_ignores_common_words_that_only_contain_a_technical_substring(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=FakeWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    try:
        assert service._research_query("Quero criar um portal para fornecedores.") == ""
        assert service._research_query("Precisamos de uma API para o portal.").startswith("Precisamos")
    finally:
        service.close()


@pytest.mark.asyncio
async def test_service_persists_research_references_returned_by_workflow(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=ResearchWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("Arquitetura", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    await service.submit_answer(session.id, "Precisamos definir a arquitetura da API.")

    findings = service.repository.get_research_findings(session.id)
    assert findings[0]["url"] == "https://langchain-ai.github.io/langgraph/"


@pytest.mark.asyncio
async def test_service_supplies_previously_persisted_references_to_the_final_workflow(tmp_path) -> None:
    """Garante que referências de turnos anteriores chegam à síntese final."""

    workflow = ExistingReferencesWorkflow()
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=workflow,
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("Portal", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.save_research_findings(
        session.id,
        "LangGraph",
        [
            ResearchFinding(
                title="Documentação LangGraph",
                url="https://langchain-ai.github.io/langgraph/",
                excerpt="Orquestração de fluxos.",
                decision_context="arquitetura",
            )
        ],
    )

    await service.submit_answer(session.id, "Quero criar um portal para fornecedores.")

    assert workflow.research_references[0].url == "https://langchain-ai.github.io/langgraph/"
