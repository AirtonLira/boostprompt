from datetime import UTC, datetime

import pytest
from textual.widgets import Button, Input, ListView, LoadingIndicator, Static

from boostprompt.cli.tui_main import (
    BoostPromptApp,
    ChatScreen,
    MainMenu,
    MarkdownPreviewScreen,
)
from boostprompt.memory.duckdb_store import ResumedSession
from boostprompt.models.schemas import (
    DiscoveryMode,
    PromptQualityEvaluation,
    PromptValidationReport,
    Session,
    SessionSummary,
    TurnResult,
)

QUALITY_EVALUATION = PromptQualityEvaluation(
    coverage=42,
    decision_clarity=58,
    prompt_readiness=51,
    questions_count=1,
    status_text="Contexto inicial registrado.",
)


class FakeService:
    def __init__(self) -> None:
        self.created_mode: DiscoveryMode | None = None
        self.submitted: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.partial_prompts: list[str] = []

    def list_sessions(self):
        return []

    def delete_session(self, session_id: str) -> None:
        self.deleted.append(session_id)

    async def create_session(self, name: str, mode: DiscoveryMode) -> Session:
        self.created_mode = mode
        now = datetime.now(UTC)
        return Session(
            id="session-1",
            codigo="BP-2026-001",
            nome=name,
            mode=mode,
            created_at=now,
            updated_at=now,
        )

    async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
        self.submitted.append((session_id, answer))
        return TurnResult(
            display_message="### Pergunta 1 — Objetivos\n\nQual resultado define sucesso?",
            context={"necessidade": answer},
            questions_count=1,
            awaiting_user_answer=True,
        )

    async def generate_partial_prompt(self, session_id: str) -> TurnResult:
        self.partial_prompts.append(session_id)
        return TurnResult(
            display_message="Rascunho do prompt gerado.",
            context={"necessidade": "API"},
            questions_count=10,
            awaiting_user_answer=False,
            final_markdown="# Rascunho do Prompt",
        )


class SessionsWithQualityService(FakeService):
    def list_sessions(self):
        return [
            {
                "id": "session-development",
                "codigo": "BP-2026-073",
                "nome": "API de cobrança",
                "mode": DiscoveryMode.PROMPT_DESENVOLVIMENTO.value,
                "questions_count": 12,
                "status": "in_progress",
                "updated_at": datetime(2026, 8, 10, tzinfo=UTC),
                "prompt_readiness": 73,
                "quality_applicable": True,
                "quality_evaluated_at": datetime(2026, 8, 10, tzinfo=UTC),
            },
            {
                "id": "session-client",
                "codigo": "BP-2026-074",
                "nome": "Roteiro para cliente",
                "mode": DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE.value,
                "questions_count": 30,
                "status": "completed",
                "updated_at": datetime(2026, 8, 10, tzinfo=UTC),
                "prompt_readiness": None,
                "quality_applicable": False,
                "quality_evaluated_at": None,
            },
        ]


class FinalMarkdownService(FakeService):
    async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
        self.submitted.append((session_id, answer))
        return TurnResult(
            display_message="Escopo final gerado.",
            context={"necessidade": answer},
            questions_count=30,
            awaiting_user_answer=False,
            final_markdown="# Escopo da Solução\n\n## 1. Resumo executivo",
        )


class TenAnswerService(FakeService):
    async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
        self.submitted.append((session_id, answer))
        return TurnResult(
            display_message="### Pergunta 10 — Escopo",
            context={"necessidade": answer},
            questions_count=10,
            answered_questions_count=10,
            awaiting_user_answer=True,
        )


class NineAnswerService(FakeService):
    async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
        self.submitted.append((session_id, answer))
        return TurnResult(
            display_message="### Pergunta 10 — Escopo",
            context={"necessidade": answer},
            questions_count=10,
            answered_questions_count=9,
            awaiting_user_answer=True,
        )


class NeedsReviewService(FakeService):
    async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
        report = PromptValidationReport(
            valid=False,
            missing_sections=["## 17. Plano de execução"],
        )
        return TurnResult(
            display_message="Documento requer revisão.",
            context={"necessidade": answer},
            questions_count=30,
            answered_questions_count=30,
            awaiting_user_answer=False,
            final_markdown="# Prompt Mestre de Implementação - Portal",
            quality_evaluation=PromptQualityEvaluation(validation_report=report),
            validation_report=report,
        )


class QualityReturningService(FakeService):
    async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
        result = await super().submit_answer(session_id, answer)
        return result.model_copy(update={"quality_evaluation": QUALITY_EVALUATION})


class ResumingFinalService(FakeService):
    def __init__(self) -> None:
        super().__init__()
        now = datetime.now(UTC)
        self.session = Session(
            id="session-final",
            codigo="BP-2026-050",
            nome="Portal final",
            mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
            created_at=now,
            updated_at=now,
            status="completed",
            questions_count=30,
        )
        self.continued_from: str | None = None
        self.continuation = Session(
            id="session-continuation",
            codigo="BP-2026-051",
            nome="Portal final — continuação",
            mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
            created_at=now,
            updated_at=now,
        )

    def list_sessions(self):
        return [self.session.model_dump()]

    def resume_session(self, session_id: str) -> ResumedSession:
        if session_id == self.continuation.id:
            return ResumedSession(
                session=self.continuation,
                messages=[],
                context={"sessao_origem": {"id": self.session.id}},
                summary=SessionSummary(goal="Portal concluído", decisions=["Entregar MVP"]),
                decisions=[],
                final_markdown=None,
                quality_evaluation=None,
            )
        assert session_id == self.session.id
        return ResumedSession(
            session=self.session,
            messages=[],
            context={},
            summary=SessionSummary(goal="Portal concluído"),
            decisions=[],
            final_markdown="# Escopo da Solução\n\n## 1. Resumo executivo",
            quality_evaluation=None,
        )

    async def continue_completed_session(self, session_id: str) -> Session:
        assert session_id == self.session.id
        self.continued_from = session_id
        return self.continuation


class ResumingQualityService(ResumingFinalService):
    def resume_session(self, session_id: str) -> ResumedSession:
        resumed = super().resume_session(session_id)
        return ResumedSession(
            session=resumed.session,
            messages=resumed.messages,
            context=resumed.context,
            summary=resumed.summary,
            decisions=resumed.decisions,
            final_markdown=resumed.final_markdown,
            quality_evaluation=QUALITY_EVALUATION,
        )


@pytest.mark.asyncio
async def test_provider_selection_uses_litellm_environment_before_opening_the_menu(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / "litellm.env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_MODEL=litellm/gpt-4.1-mini",
                "LITELLM_BASE_URL=https://litellm.example.test/v1",
                "API_KEY=token-for-test",
                f"DUCKDB_PATH={tmp_path / 'sessions.db'}",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BOOSTPROMPT_ENV_FILE", str(env_file))
    app = BoostPromptApp()

    async with app.run_test() as pilot:
        assert app.screen.query_one("#select-litellm", Button).disabled is False
        await pilot.click("#select-litellm")
        await pilot.pause()

        assert isinstance(app.screen, MainMenu)


@pytest.mark.asyncio
async def test_provider_selection_keeps_the_selection_screen_when_litellm_is_not_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BOOSTPROMPT_ENV_FILE", raising=False)
    for name in ("LLM_MODEL", "LLM_BASE_URL", "LITELLM_BASE_URL", "LLM_API_KEY", "LITELLM_API_KEY", "API_KEY"):
        monkeypatch.delenv(name, raising=False)
    app = BoostPromptApp()

    async with app.run_test() as pilot:
        await pilot.click("#select-litellm")
        await pilot.pause()

        assert app.screen.query_one("#select-openai", Button).disabled is False
        assert not isinstance(app.screen, MainMenu)


@pytest.mark.asyncio
async def test_refreshing_session_list_keeps_loading_widget_mounted() -> None:
    app = BoostPromptApp(service=FakeService())

    async with app.run_test() as pilot:
        await pilot.click("#list_sessions")
        await pilot.click("#refresh")

        assert app.screen.query_one("#loading", LoadingIndicator).display is False


@pytest.mark.asyncio
async def test_session_list_shows_update_timestamp_and_last_prompt_readiness() -> None:
    service = SessionsWithQualityService()
    app = BoostPromptApp(service=service)

    async with app.run_test() as pilot:
        await pilot.click("#list_sessions")
        list_view = app.screen.query_one("#sessions-list-view", ListView)
        rendered = [str(item.query_one(Static).render()) for item in list_view.children]

        assert "Prontidão: 73/100" in rendered[0]
        assert "Atualizada em: 10/08/2026 00:00" in rendered[0]
        assert "Prontidão: não aplicável" in rendered[1]


@pytest.mark.asyncio
async def test_new_session_collects_output_mode_before_opening_chat() -> None:
    service = TenAnswerService()
    app = BoostPromptApp(service=service)

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "Portal de fornecedores"
        await pilot.click("#mode-client-guide")
        await pilot.click("#create")
        await pilot.pause()

        assert service.created_mode is DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE
        assert isinstance(app.screen, ChatScreen)


@pytest.mark.asyncio
async def test_chat_submission_delegates_one_turn_to_the_session_service() -> None:
    service = FakeService()
    app = BoostPromptApp(service=service)

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "API"
        await pilot.click("#create")
        app.screen.query_one("#chat-input", Input).value = "Preciso de uma API de cobrança."
        await pilot.click("#send")
        await pilot.pause()

        assert service.submitted == [("session-1", "Preciso de uma API de cobrança.")]


@pytest.mark.asyncio
async def test_chat_updates_the_fixed_quality_panel_after_a_turn() -> None:
    app = BoostPromptApp(service=QualityReturningService())

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "API"
        await pilot.click("#create")
        app.screen.query_one("#chat-input", Input).value = "Criar API."
        await pilot.click("#send")
        await pilot.pause()

        panel = app.screen.query_one("#prompt-quality-panel")
        assert "Cobertura do contexto" in str(panel.render())
        assert "42/100" in str(panel.render())


@pytest.mark.asyncio
async def test_narrow_chat_reflows_quality_panel_without_compressing_metrics() -> None:
    app = BoostPromptApp(service=QualityReturningService())

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "API"
        await pilot.click("#create")
        await pilot.pause()

        layout = app.screen.query_one("#chat-layout")
        panel = app.screen.query_one("#prompt-quality-panel")
        input_area = app.screen.query_one("#chat-input-area")
        actions = app.screen.query_one("#chat-actions")

        assert layout.has_class("narrow")
        assert layout.max_scroll_y > 0
        layout.scroll_end(animate=False)
        await pilot.pause()
        assert panel.content_region.height >= 9
        assert input_area.region.y + input_area.region.height <= panel.region.y
        assert panel.region.y + panel.region.height <= actions.region.y


@pytest.mark.asyncio
async def test_resumed_chat_renders_the_persisted_quality_panel() -> None:
    app = BoostPromptApp(service=ResumingQualityService())

    async with app.run_test() as pilot:
        await pilot.click("#resume_session")
        app.screen.query_one("#session-code-input", Input).value = "BP-2026-050"
        await pilot.click("#resume")
        await pilot.pause()

        assert "Prontidão do prompt" in str(app.screen.query_one("#prompt-quality-panel").render())


@pytest.mark.asyncio
async def test_partial_prompt_button_becomes_available_after_ten_answers_and_opens_the_draft(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    service = TenAnswerService()
    app = BoostPromptApp(service=service)

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "API"
        await pilot.click("#create")
        assert app.screen.query_one("#generate-partial", Button).disabled is True

        app.screen.query_one("#chat-input", Input).value = "Preciso de uma API."
        await pilot.click("#send")
        await pilot.pause()
        assert app.screen.query_one("#generate-partial", Button).disabled is False

        await pilot.click("#generate-partial")
        await pilot.pause()
        await pilot.click("#generate")
        await pilot.pause()

        assert service.partial_prompts == ["session-1"]
        assert isinstance(app.screen, MarkdownPreviewScreen)
        assert (tmp_path / "output" / "API_prompt_mestre.md").read_text(encoding="utf-8") == "# Rascunho do Prompt"


@pytest.mark.asyncio
async def test_partial_prompt_button_stays_disabled_after_nine_confirmed_answers() -> None:
    app = BoostPromptApp(service=NineAnswerService())

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "API"
        await pilot.click("#create")
        app.screen.query_one("#chat-input", Input).value = "Preciso de uma API."
        await pilot.click("#send")
        await pilot.pause()

        assert app.screen.query_one("#generate-partial", Button).disabled is True


@pytest.mark.asyncio
async def test_quality_panel_exposes_an_invalid_final_document() -> None:
    app = BoostPromptApp(service=NeedsReviewService())

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "Portal"
        await pilot.click("#create")
        app.screen.query_one("#chat-input", Input).value = "Criar portal."
        await pilot.click("#send")
        await pilot.pause()

        panel = app.screen.query_one("#prompt-quality-panel")
        assert "Documento requer revisão: ## 17. Plano de execução" in str(panel.render())


@pytest.mark.asyncio
async def test_chat_writes_the_final_markdown_and_opens_its_preview(tmp_path, monkeypatch) -> None:
    """Garante que o resultado final vira um artefato Markdown local utilizável."""

    monkeypatch.chdir(tmp_path)
    app = BoostPromptApp(service=FinalMarkdownService())

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "Portal final"
        await pilot.click("#create")
        app.screen.query_one("#chat-input", Input).value = "Criar portal."
        await pilot.click("#send")
        await pilot.click("#generate")
        await pilot.pause()

        assert isinstance(app.screen, MarkdownPreviewScreen)
        assert (tmp_path / "output" / "Portal_final_prompt_mestre.md").read_text(encoding="utf-8") == (
            "# Escopo da Solução\n\n## 1. Resumo executivo"
        )


@pytest.mark.asyncio
async def test_deleting_selected_session_requires_a_confirmation_click() -> None:
    service = ResumingFinalService()
    app = BoostPromptApp(service=service)

    async with app.run_test() as pilot:
        await pilot.click("#list_sessions")
        await pilot.pause()
        app.screen.query_one("#sessions-list-view", ListView).index = 0
        await pilot.pause()

        await pilot.click("#delete")
        await pilot.pause()
        assert service.deleted == []

        await pilot.pause(0.25)  # aguarda o efeito visual do clique liberar o botão
        await pilot.click("#delete")
        await pilot.pause()
        assert service.deleted == [service.session.id]


@pytest.mark.asyncio
async def test_resumed_session_restores_the_final_markdown_for_download(tmp_path, monkeypatch) -> None:
    """Evita que um escopo já concluído desapareça depois de fechar a TUI."""

    monkeypatch.chdir(tmp_path)
    app = BoostPromptApp(service=ResumingFinalService())

    async with app.run_test() as pilot:
        await pilot.click("#resume_session")
        app.screen.query_one("#session-code-input", Input).value = "BP-2026-050"
        await pilot.click("#resume")
        await pilot.pause()
        await pilot.click("#generate")
        await pilot.pause()

        assert isinstance(app.screen, MarkdownPreviewScreen)


@pytest.mark.asyncio
async def test_completed_session_can_start_a_compact_continuation() -> None:
    service = ResumingFinalService()
    app = BoostPromptApp(service=service)

    async with app.run_test() as pilot:
        await pilot.click("#list_sessions")
        app.screen.query_one("#sessions-list-view", ListView).index = 0
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#continue-session")
        await pilot.pause()

        assert service.continued_from == "session-final"
        assert isinstance(app.screen, ChatScreen)
        assert "continuação" in app.screen.session.nome
