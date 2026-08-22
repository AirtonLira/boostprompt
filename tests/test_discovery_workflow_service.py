import pytest

from boostprompt.graph.workflow import TurnWorkflow
from boostprompt.llm import ModelProvider
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


class PartialFinalWorkflow:
    def __init__(self) -> None:
        self.states = []

    async def run_turn(self, state):
        self.states.append(state)
        return TurnResult(
            display_message="Rascunho gerado.",
            context=state["context"],
            questions_count=state["questions_count"],
            awaiting_user_answer=False,
            final_markdown="# Rascunho",
        )


class CapturingSummaryAgent:
    def __init__(self) -> None:
        self.messages = []

    async def summarize(self, *, previous, messages, context) -> SessionSummary:
        self.messages = list(messages)
        return SessionSummary(
            goal=context["objetivo"],
            decisions=["Entregar MVP"],
            pending_topics=["Definir auditoria"],
        )


class PartialThenQuestionWorkflow:
    async def run_turn(self, state):
        if state.get("force_finalize"):
            return TurnResult(
                display_message="Rascunho gerado.",
                context=state["context"],
                questions_count=state["questions_count"],
                awaiting_user_answer=False,
                final_markdown="# Rascunho",
            )
        return TurnResult(
            display_message="### Pergunta 11 — Escopo",
            context=state["context"],
            questions_count=state["questions_count"] + 1,
            awaiting_user_answer=True,
        )


async def build_service_with_ten_answers(tmp_path) -> tuple[DiscoveryWorkflowService, str]:
    """Prepara uma sessão elegível para geração antecipada, sem usar modelo ou rede."""

    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=PartialFinalWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.append_turn(
        session.id,
        "Demanda",
        "Pergunta 10",
        {"objetivo": "CRM"},
        10,
        answered_questions_count=10,
    )
    return service, session.id


def build_service_for_client_guide(tmp_path) -> DiscoveryWorkflowService:
    """Monta um serviço isolado para o fluxo de roteiro direto ao cliente."""

    return DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=FakeWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )


def test_default_service_builds_all_pydantic_ai_agents(tmp_path, monkeypatch) -> None:
    """Garante compatibilidade com a API PydanticAI instalada, sem chamar o modelo."""

    env_file = tmp_path / "litellm.env"
    env_file.write_text(
        "LLM_MODEL=litellm/gpt-4.1-mini\n"
        "LITELLM_BASE_URL=https://litellm.example.test/v1\n"
        "API_KEY=token-for-test",
        encoding="utf-8",
    )
    monkeypatch.setenv("BOOSTPROMPT_ENV_FILE", str(env_file))
    service = DiscoveryWorkflowService.create_default(
        ModelProvider.LITELLM, tmp_path / "sessions.db"
    )
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
async def test_submit_answer_counts_only_answers_to_displayed_questions(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=FakeWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("Pagamentos", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    initial = await service.submit_answer(session.id, "Preciso cobrar clientes.")
    confirmed = await service.submit_answer(session.id, "Lojistas parceiros.")

    assert initial.answered_questions_count == 0
    assert confirmed.answered_questions_count == 1
    assert service.resume_session(session.id).session.answered_questions_count == 1


@pytest.mark.asyncio
async def test_submit_answer_returns_and_persists_quality_evaluation(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=FakeWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("Pagamentos", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    result = await service.submit_answer(session.id, "Preciso cobrar clientes.")

    assert result.quality_evaluation is not None
    assert service.resume_session(session.id).quality_evaluation == result.quality_evaluation


@pytest.mark.asyncio
async def test_partial_prompt_refreshes_quality_without_creating_messages(tmp_path) -> None:
    service, session_id = await build_service_with_ten_answers(tmp_path)
    before = service.repository.get_messages(session_id)

    result = await service.generate_partial_prompt(session_id)

    assert result.quality_evaluation is not None
    assert service.repository.get_messages(session_id) == before


@pytest.mark.asyncio
async def test_client_guide_result_is_marked_not_applicable(tmp_path) -> None:
    service = build_service_for_client_guide(tmp_path)
    session = await service.create_session("Portal", DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE)

    result = await service.submit_answer(session.id, "Preciso de perguntas para o cliente.")

    assert result.quality_evaluation is not None
    assert result.quality_evaluation.applicable is False


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


@pytest.mark.asyncio
async def test_partial_prompt_requires_ten_answered_questions(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db", workflow=FakeWorkflow(), summary_agent=FakeSummaryAgent()
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    with pytest.raises(ValueError, match="pelo menos 10"):
        await service.generate_partial_prompt(session.id)


@pytest.mark.asyncio
async def test_partial_prompt_requires_ten_confirmed_answers(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=FakeWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.append_turn(
        session.id,
        "Demanda",
        "Pergunta 10",
        {"objetivo": "CRM"},
        10,
        answered_questions_count=9,
    )

    with pytest.raises(ValueError, match="10 respostas"):
        await service.generate_partial_prompt(session.id)


@pytest.mark.asyncio
async def test_partial_prompt_finalizes_without_appending_a_user_message(tmp_path) -> None:
    workflow = PartialFinalWorkflow()
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db", workflow=workflow, summary_agent=FakeSummaryAgent()
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.append_turn(
        session.id,
        "Demanda",
        "Pergunta 10",
        {"objetivo": "CRM"},
        10,
        answered_questions_count=10,
    )

    result = await service.generate_partial_prompt(session.id)

    assert workflow.states[0]["force_finalize"] is True
    assert result.final_markdown == "# Rascunho"
    assert [item["content"] for item in service.repository.get_messages(session.id)] == [
        "Demanda",
        "Pergunta 10",
    ]
    assert service.resume_session(session.id).session.status == "in_progress"


@pytest.mark.asyncio
async def test_continuation_summarizes_completed_session_and_injects_only_summary(tmp_path) -> None:
    workflow = FakeWorkflow()
    summary_agent = CapturingSummaryAgent()
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db", workflow=workflow, summary_agent=summary_agent
    )
    source = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.append_turn(
        source.id,
        "Criar CRM para vendedores.",
        "Pergunta 30",
        {"objetivo": "CRM de vendas"},
        30,
    )
    service.repository.save_generated_markdown(
        source.id, {"objetivo": "CRM de vendas"}, 30, "completed", "# Escopo final"
    )

    continuation = await service.continue_completed_session(source.id)
    await service.submit_answer(continuation.id, "A nova feature terá auditoria.")

    assert [message.content for message in summary_agent.messages] == [
        "Criar CRM para vendedores.",
        "Pergunta 30",
    ]
    assert continuation.id != source.id
    state = workflow.states[-1]
    assert state["context"]["resumo_da_sessao"]["decisions"] == ["Entregar MVP"]
    assert [message.content for message in state["messages"]] == ["A nova feature terá auditoria."]


@pytest.mark.asyncio
async def test_continuation_rejects_a_session_that_is_not_completed(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db", workflow=FakeWorkflow(), summary_agent=FakeSummaryAgent()
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    with pytest.raises(ValueError, match="concluídas"):
        await service.continue_completed_session(session.id)


@pytest.mark.asyncio
async def test_session_accepts_new_answers_after_partial_prompt_generation(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=PartialThenQuestionWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.append_turn(
        session.id,
        "Demanda",
        "Pergunta 10",
        {"objetivo": "CRM"},
        10,
        answered_questions_count=10,
    )

    await service.generate_partial_prompt(session.id)
    await service.submit_answer(session.id, "A nova feature terá auditoria.")

    resumed = service.resume_session(session.id)
    assert resumed.session.status == "in_progress"
    assert resumed.session.questions_count == 11
    assert service.repository.get_messages(session.id)[-1]["content"] == "### Pergunta 11 — Escopo"


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
