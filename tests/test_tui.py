from datetime import UTC, datetime

import pytest
from textual.widgets import Button, Input, ListView, LoadingIndicator

from boostprompt.cli.tui_main import BoostPromptApp, ChatScreen, MainMenu, MarkdownPreviewScreen
from boostprompt.memory.duckdb_store import ResumedSession
from boostprompt.models.schemas import DiscoveryMode, Session, SessionSummary, TurnResult


class FakeService:
    def __init__(self) -> None:
        self.created_mode: DiscoveryMode | None = None
        self.submitted: list[tuple[str, str]] = []
        self.deleted: list[str] = []

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
            questions_count=30,
        )

    def list_sessions(self):
        return [self.session.model_dump()]

    def resume_session(self, session_id: str) -> ResumedSession:
        assert session_id == self.session.id
        return ResumedSession(
            session=self.session,
            messages=[],
            context={},
            summary=SessionSummary(goal="Portal concluído"),
            decisions=[],
            final_markdown="# Escopo da Solução\n\n## 1. Resumo executivo",
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
async def test_new_session_collects_output_mode_before_opening_chat() -> None:
    service = FakeService()
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
        assert (tmp_path / "output" / "Portal_final_escopo.md").read_text(encoding="utf-8") == (
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
