"""TUI Textual para criar, retomar e conduzir sessões BoostPrompt."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol, TypeAlias

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Markdown,
    Static,
    TextArea,
)

from boostprompt.cli.prompt_quality_panel import PromptQualityPanel
from boostprompt.llm import ModelProvider
from boostprompt.models.schemas import DiscoveryMode, Session, SessionSummary, TurnResult
from boostprompt.services.discovery_workflow import DiscoveryWorkflowService

BindingDefinition: TypeAlias = Binding | tuple[str, str] | tuple[str, str, str]


class SessionService(Protocol):
    async def create_session(self, name: str, mode: DiscoveryMode) -> Session: ...

    async def submit_answer(self, session_id: str, answer: str) -> TurnResult: ...

    async def generate_partial_prompt(self, session_id: str) -> TurnResult: ...

    async def continue_completed_session(self, session_id: str) -> Session: ...

    def resume_session(self, session_id: str) -> Any: ...

    def list_sessions(self) -> list[dict[str, Any]]: ...

    def delete_session(self, session_id: str) -> None: ...


class ProviderSelectionScreen(Screen[None]):
    """Escolhe o provedor antes de inicializar os agentes da aplicação."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="provider-selection"):
            yield Markdown("## Provedor de modelo")
            yield Static("Escolha a configuração que será lida do arquivo `.env`.")
            yield Button("Usar LiteLLM", id="select-litellm", variant="primary")
            yield Button("Usar OpenAI", id="select-openai")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        providers = {
            "select-litellm": ModelProvider.LITELLM,
            "select-openai": ModelProvider.OPENAI,
        }
        button_id = event.button.id
        if button_id is None:
            return
        provider = providers.get(button_id)
        if provider is None:
            return
        try:
            self.boostprompt_app.configure_provider(provider)
        except ValueError as error:
            self.notify(str(error), severity="error")
            return
        self.app.switch_screen(MainMenu())

    @property
    def boostprompt_app(self) -> BoostPromptApp:
        return self.app  # type: ignore[return-value]


class MainMenu(Screen[None]):
    """Tela inicial com os caminhos de sessão disponíveis."""

    BINDINGS: ClassVar[list[BindingDefinition]] = [Binding("q", "quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-menu"):
            yield Static("# BoostPrompt CLI", id="title")
            yield Static("Escolha uma opção para iniciar ou retomar o discovery.", id="subtitle")
            yield Button("Nova sessão", id="new_session", variant="primary")
            yield Button("Listar sessões", id="list_sessions")
            yield Button("Retomar por código", id="resume_session")
            yield Button("Sair", id="quit", variant="error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit()
        elif event.button.id == "new_session":
            self.app.push_screen(NewSessionScreen())
        elif event.button.id == "list_sessions":
            self.app.push_screen(SessionsListScreen())
        elif event.button.id == "resume_session":
            self.app.push_screen(ResumeSessionScreen())


class NewSessionScreen(Screen[None]):
    """Cria uma sessão e exige que o usuário escolha o modo de saída."""

    BINDINGS: ClassVar[list[BindingDefinition]] = [Binding("escape", "back", "Voltar")]

    def __init__(self) -> None:
        super().__init__()
        self.mode = DiscoveryMode.PROMPT_DESENVOLVIMENTO

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="new-session-form"):
            yield Markdown("## Nova sessão")
            yield Label("Nome da sessão:")
            yield Input(placeholder="Ex.: API de pagamentos", id="session-name-input")
            yield Static(self._mode_description(), id="mode-description")
            with Horizontal(id="mode-actions"):
                yield Button(
                    "Prompt de implementação",
                    id="mode-development",
                    variant="primary",
                )
                yield Button("Roteiro para o cliente", id="mode-client-guide")
            with Horizontal():
                yield Button("Cancelar", id="cancel")
                yield Button("Criar sessão", id="create", variant="success")
        yield Footer()

    def _mode_description(self) -> str:
        if self.mode is DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE:
            return (
                "Modo atual: roteiro de 30 a 50 perguntas para enviar ao cliente, "
                "gerado diretamente a partir da demanda."
            )
        return (
            "Modo atual: entrevista guiada de 30 a 50 perguntas, seguida de um prompt "
            "mestre de implementação."
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
            return
        if event.button.id == "mode-development":
            self.mode = DiscoveryMode.PROMPT_DESENVOLVIMENTO
        elif event.button.id == "mode-client-guide":
            self.mode = DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE
        elif event.button.id == "create":
            name = self.query_one("#session-name-input", Input).value.strip()
            if not name:
                self.notify("Informe o nome da sessão.", severity="warning")
                return
            try:
                session = await self.boostprompt_app.service.create_session(name, self.mode)
            except (RuntimeError, ValueError) as error:
                self.notify(f"Não foi possível criar a sessão: {error}", severity="error")
                return
            self.app.push_screen(ChatScreen(session=session, is_new=True))
            return
        else:
            return
        self.query_one("#mode-description", Static).update(self._mode_description())

    @property
    def boostprompt_app(self) -> BoostPromptApp:
        return self.app  # type: ignore[return-value]


class SessionsListScreen(Screen[None]):
    """Lista sessões persistidas e permite abri-las."""

    BINDINGS: ClassVar[list[BindingDefinition]] = [Binding("escape", "back", "Voltar")]

    def __init__(self) -> None:
        super().__init__()
        self._sessions_by_item_id: dict[str, dict[str, Any]] = {}
        self._pending_delete_item_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="sessions-list"):
            yield Markdown("## Sessões salvas")
            yield LoadingIndicator(id="loading")
            yield ListView(id="sessions-list-view")
        with Horizontal(id="sessions-actions"):
            yield Button("Voltar", id="back")
            yield Button("Atualizar", id="refresh", variant="primary")
            yield Button("Excluir sessão", id="delete", variant="error")
        yield Footer()

    async def on_mount(self) -> None:
        await self._load_sessions()

    async def _load_sessions(self) -> None:
        loading = self.query_one("#loading", LoadingIndicator)
        loading.display = True
        list_view = self.query_one("#sessions-list-view", ListView)
        await list_view.clear()
        self._sessions_by_item_id.clear()
        self._pending_delete_item_id = None
        self.query_one("#delete", Button).label = "Excluir sessão"
        sessions = self.boostprompt_app.service.list_sessions()
        if not sessions:
            await list_view.append(ListItem(Static("Nenhuma sessão encontrada."), id="empty"))
        else:
            for session in sessions:
                item_id = f"session-{session['id']}"
                self._sessions_by_item_id[item_id] = session
                await list_view.append(
                    ListItem(
                        Static(self._format_session_item(session)),
                        id=item_id,
                    )
                )
        loading.display = False

    @staticmethod
    def _format_session_item(session: dict[str, Any]) -> str:
        mode = session.get("mode", DiscoveryMode.PROMPT_DESENVOLVIMENTO.value)
        updated_at = session.get("updated_at")
        if isinstance(updated_at, datetime):
            updated_text = updated_at.strftime("%d/%m/%Y %H:%M")
        else:
            updated_text = "não disponível"

        if session.get("quality_applicable") is True and isinstance(
            session.get("prompt_readiness"), int
        ):
            readiness = f"{session['prompt_readiness']}/100"
        elif session.get("quality_applicable") is False:
            readiness = "não aplicável"
        else:
            readiness = "sem avaliação"

        return (
            f"{session['codigo']} — {session['nome']}\n"
            f"Modo: {mode} | Status: {session['status']} | "
            f"{session['questions_count']} perguntas\n"
            f"Atualizada em: {updated_text}\n"
            f"Prontidão: {readiness}"
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "refresh":
            await self._load_sessions()
        elif event.button.id == "delete":
            await self._delete_selected_session()

    async def _delete_selected_session(self) -> None:
        list_view = self.query_one("#sessions-list-view", ListView)
        delete_button = self.query_one("#delete", Button)
        highlighted = list_view.highlighted_child
        if highlighted is None or highlighted.id not in self._sessions_by_item_id:
            self.notify("Selecione uma sessão para excluir.", severity="warning")
            return
        if self._pending_delete_item_id != highlighted.id:
            self._pending_delete_item_id = highlighted.id
            delete_button.label = "Confirmar exclusão?"
            return
        self._pending_delete_item_id = None
        delete_button.label = "Excluir sessão"
        session_id = self._sessions_by_item_id[highlighted.id]["id"]
        self.boostprompt_app.service.delete_session(session_id)
        await self._load_sessions()
        self.notify("Sessão excluída.")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if item_id is None or item_id not in self._sessions_by_item_id:
            return
        self.app.push_screen(ChatScreen(session=Session.model_validate(self._sessions_by_item_id[item_id]), is_new=False))

    @property
    def boostprompt_app(self) -> BoostPromptApp:
        return self.app  # type: ignore[return-value]


class ResumeSessionScreen(Screen[None]):
    """Abre uma sessão existente pelo código gerado pelo DuckDB."""

    BINDINGS: ClassVar[list[BindingDefinition]] = [Binding("escape", "back", "Voltar")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="resume-session-form"):
            yield Markdown("## Retomar sessão")
            yield Label("Código da sessão:")
            yield Input(placeholder="BP-2026-001", id="session-code-input")
            with Horizontal():
                yield Button("Cancelar", id="cancel")
                yield Button("Retomar", id="resume", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
            return
        if event.button.id != "resume":
            return
        code = self.query_one("#session-code-input", Input).value.strip().upper()
        session_data = next(
            (session for session in self.boostprompt_app.service.list_sessions() if session["codigo"] == code),
            None,
        )
        if session_data is None:
            self.notify("Sessão não encontrada.", severity="error")
            return
        self.app.push_screen(ChatScreen(session=Session.model_validate(session_data), is_new=False))

    @property
    def boostprompt_app(self) -> BoostPromptApp:
        return self.app  # type: ignore[return-value]


class ChatScreen(Screen[None]):
    """Renderiza a conversa; toda durabilidade fica no serviço de aplicação."""

    BINDINGS: ClassVar[list[BindingDefinition]] = [Binding("escape", "back", "Voltar")]

    def __init__(self, session: Session, is_new: bool) -> None:
        super().__init__()
        self.session = session
        self.is_new = is_new
        self.final_markdown: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="chat-layout"):
            with Vertical(id="chat-container"):
                yield Markdown(f"## {self.session.nome}", id="chat-title")
                with ScrollableContainer(id="chat-messages"):
                    pass
                with Horizontal(id="chat-input-area"):
                    yield Input(placeholder="Digite sua resposta ou demanda...", id="chat-input")
                    yield Button("Enviar", id="send", variant="primary")
            yield PromptQualityPanel()
        with Horizontal(id="chat-actions"):
            yield Button("Gerar prompt agora", id="generate-partial", variant="success", disabled=True)
            yield Button("Gerar/abrir Markdown", id="generate", variant="success")
            yield Button("Continuar em nova entrevista", id="continue-session", disabled=True)
            yield Button("Voltar", id="back", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self._update_chat_layout(self.size.width)
        if self.is_new:
            self._render_message(
                "assistant",
                "Sessão criada e salva localmente. Descreva a demanda para começar.",
            )
            self._update_action_availability()
            return
        resumed = self.boostprompt_app.service.resume_session(self.session.id)
        self.session = resumed.session
        self.query_one("#prompt-quality-panel", PromptQualityPanel).update_evaluation(
            resumed.quality_evaluation
        )
        for message in resumed.messages:
            self._render_message(message.role, message.content)
        if resumed.summary.goal:
            summary = (
                self._format_summary(resumed.summary)
                if self.session.status == "completed"
                else f"Resumo recuperado: {resumed.summary.goal}"
            )
            self._render_message("system", summary)
        self.final_markdown = resumed.final_markdown
        if self.final_markdown is not None:
            self._render_message(
                "system",
                "O Markdown final recuperado está disponível para abrir ou salvar.",
            )
        self._update_action_availability()

    def on_resize(self, event: events.Resize) -> None:
        self._update_chat_layout(event.size.width)

    def _update_chat_layout(self, width: int) -> None:
        self.query_one("#chat-layout").set_class(width <= 100, "narrow")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "send":
            await self._send_message()
        elif event.button.id == "generate":
            self._open_markdown()
        elif event.button.id == "generate-partial":
            await self._generate_partial_prompt()
        elif event.button.id == "continue-session":
            await self._continue_session()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            await self._send_message()

    async def _send_message(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        message = input_widget.value.strip()
        if not message:
            return
        input_widget.disabled = True
        try:
            result = await self.boostprompt_app.service.submit_answer(self.session.id, message)
        except (KeyError, RuntimeError, ValueError) as error:
            self.notify(f"Não foi possível processar a mensagem: {error}", severity="error")
        else:
            self._render_message("user", message)
            self._render_message("assistant", result.display_message)
            self.final_markdown = result.final_markdown
            evaluation = result.quality_evaluation
            if evaluation is not None and evaluation.validation_report is None:
                evaluation = evaluation.model_copy(update={"validation_report": result.validation_report})
            self.query_one("#prompt-quality-panel", PromptQualityPanel).update_evaluation(
                evaluation
            )
            self.session = self.session.model_copy(
                update={
                    "questions_count": result.questions_count,
                    "answered_questions_count": result.answered_questions_count,
                    "status": (
                        "completed"
                        if result.final_markdown is not None
                        and not result.awaiting_user_answer
                        and result.validation_report is not None
                        and result.validation_report.valid
                        else "needs_review"
                        if result.final_markdown is not None
                        else self.session.status
                    ),
                }
            )
            self._update_action_availability()
            if result.research_degraded:
                self.notify("Pesquisa indisponível; turno continuou em modo degradado.", severity="warning")
            elif result.research_findings:
                self.notify(f"{len(result.research_findings)} referência(s) pesquisada(s).")
            if result.validation_report is not None and not result.validation_report.valid:
                self.notify("Documento requer revisão antes de ser considerado concluído.", severity="warning")
        finally:
            input_widget.value = ""
            input_widget.disabled = False
            input_widget.focus()

    async def _generate_partial_prompt(self) -> None:
        try:
            result = await self.boostprompt_app.service.generate_partial_prompt(self.session.id)
        except (RuntimeError, ValueError) as error:
            self.notify(f"Não foi possível gerar o prompt: {error}", severity="error")
            return
        self.final_markdown = result.final_markdown
        self.query_one("#prompt-quality-panel", PromptQualityPanel).update_evaluation(
            result.quality_evaluation
        )
        self.session = self.session.model_copy(
            update={
                "questions_count": result.questions_count,
                "answered_questions_count": result.answered_questions_count,
                "status": "in_progress",
            }
        )
        self._render_message("assistant", result.display_message)
        self._update_action_availability()
        self.notify("Rascunho do prompt salvo. Você pode continuar a entrevista.")

    async def _continue_session(self) -> None:
        try:
            continuation = await self.boostprompt_app.service.continue_completed_session(
                self.session.id
            )
        except (RuntimeError, ValueError) as error:
            self.notify(f"Não foi possível iniciar a continuação: {error}", severity="error")
            return
        self.app.push_screen(ChatScreen(session=continuation, is_new=False))

    def _update_action_availability(self) -> None:
        partial_enabled = (
            self.session.mode is DiscoveryMode.PROMPT_DESENVOLVIMENTO
            and self.session.answered_questions_count >= 10
            and self.session.status not in {"completed", "needs_review"}
        )
        self.query_one("#generate-partial", Button).disabled = not partial_enabled
        self.query_one("#continue-session", Button).disabled = self.session.status != "completed"

    @staticmethod
    def _format_summary(summary: SessionSummary) -> str:
        groups = {
            "Fatos confirmados": summary.confirmed_facts,
            "Decisões": summary.decisions,
            "Restrições": summary.constraints,
            "Riscos": summary.risks,
            "Pendências": summary.pending_topics,
        }
        lines = ["## Resumo da sessão concluída", f"- Objetivo: {summary.goal}"]
        for title, items in groups.items():
            lines.extend(f"- {title}: {item}" for item in items)
        return "\n".join(lines)

    def _render_message(self, role: str, content: str) -> None:
        container = self.query_one("#chat-messages", ScrollableContainer)
        message_style = "user-message" if role == "user" else "assistant-message"
        container.mount(Markdown(f"**{role.capitalize()}:**\n\n{content}", classes=message_style))
        container.scroll_end(animate=False)

    def _open_markdown(self) -> None:
        if self.final_markdown is None:
            self.notify("O Markdown estará disponível após concluir o fluxo atual.", severity="warning")
            return
        output_path = Path("output") / f"{self.session.nome.replace(' ', '_')}_prompt_mestre.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.final_markdown, encoding="utf-8")
        self.app.push_screen(MarkdownPreviewScreen(self.final_markdown, output_path))

    @property
    def boostprompt_app(self) -> BoostPromptApp:
        return self.app  # type: ignore[return-value]


class MarkdownPreviewScreen(Screen[None]):
    """Exibe o Markdown final já persistido como arquivo local."""

    BINDINGS: ClassVar[list[BindingDefinition]] = [Binding("escape", "back", "Voltar")]

    def __init__(self, markdown_content: str, file_path: Path) -> None:
        super().__init__()
        self.markdown_content = markdown_content
        self.file_path = file_path

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="markdown-preview"):
            yield Markdown(f"## Preview: {self.file_path}")
            yield TextArea(self.markdown_content, language="markdown", read_only=True)
            yield Button("Voltar", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()


class BoostPromptApp(App[None]):
    """Aplicativo Textual com serviço injetável para testes funcionais."""

    CSS = """
    #main-menu, #new-session-form, #resume-session-form, #sessions-list, #provider-selection {
        align: center middle;
    }
    #main-menu, #new-session-form, #resume-session-form, #provider-selection { width: 72; }
    #chat-layout { height: 1fr; }
    #chat-container, #markdown-preview { height: 1fr; }
    #chat-container { width: 1fr; }
    #prompt-quality-panel { width: 34; min-width: 28; border: solid $primary; padding: 1; }
    #chat-messages { height: 1fr; border: solid $primary; padding: 1; }
    #chat-input-area, #chat-actions, #sessions-actions, #mode-actions { height: auto; padding: 1; }
    #chat-input { width: 1fr; }
    #sessions-list-view { height: 1fr; border: solid $primary; }
    .user-message { background: $primary 20%; padding: 1; margin: 1; }
    .assistant-message { background: $secondary 20%; padding: 1; margin: 1; }
    #chat-layout.narrow { layout: vertical; overflow-y: auto; }
    #chat-layout.narrow #chat-container { min-height: 13; }
    #chat-layout.narrow #prompt-quality-panel {
        width: 1fr;
        height: auto;
        overflow-y: auto;
    }
    """

    BINDINGS: ClassVar[list[BindingDefinition]] = [Binding("q", "quit", "Sair")]

    def __init__(self, service: SessionService | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._service = service

    def on_mount(self) -> None:
        self.push_screen(MainMenu() if self._service is not None else ProviderSelectionScreen())

    def configure_provider(self, provider: ModelProvider) -> None:
        self._service = DiscoveryWorkflowService.create_default(provider=provider)

    @property
    def service(self) -> SessionService:
        if self._service is None:
            raise RuntimeError("Selecione um provedor de modelo antes de iniciar uma sessão.")
        return self._service

    def on_unmount(self) -> None:
        close = getattr(self._service, "close", None)
        if callable(close):
            close()


def main() -> None:
    """Executa a TUI BoostPrompt."""

    BoostPromptApp().run()


if __name__ == "__main__":
    main()
