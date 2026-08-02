# CLI/TUI Session Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar uma CLI Textual que conduz discovery por turnos, pesquisa via MCP DuckDuckGo, persiste sessões no DuckDB e gera os dois formatos definidos pelas skills Codex/Claude.

**Architecture:** Um `DiscoveryWorkflowService` será a fronteira entre Textual, LangGraph e DuckDB. Cada turno executa somente um nó de discovery, persiste o delta e encerra; o grafo só executa os agentes finais quando a entrevista puder finalizar. Adaptadores injetáveis isolam PydanticAI e o MCP para testes funcionais sem chamadas externas.

**Tech Stack:** Python 3.11+, Textual, LangGraph, PydanticAI, MCP stdio, DuckDB, Pydantic, pytest/pytest-asyncio/pytest-cov, Ruff e mypy.

## Global Constraints

- Todo texto apresentado ao usuário e todo Markdown final deve ser pt-BR.
- `prompt_desenvolvimento` faz 30 a 50 perguntas, uma por resposta; `roteiro_perguntas_cliente` produz diretamente 30 a 50 perguntas.
- Textual somente renderiza/interage; LangGraph orquestra; PydanticAI produz respostas estruturadas; DuckDB é a fonte local de verdade.
- O servidor de pesquisa é o MCP `ddg-search`, iniciado como `uvx duckduckgo-mcp-server`; indisponibilidade deve usar modo degradado e nunca inventar fontes.
- Cada interação deve ser durável sem botão manual Salvar e não pode duplicar mensagens.
- Não fazer commit sem aprovação explícita do usuário.

---

## File Structure

- `src/boostprompt/models/schemas.py`: contratos Pydantic para modos, perguntas, resumos, pesquisa, sessão e resultado de turno.
- `src/boostprompt/memory/duckdb_store.py`: schema migratório e repositório transacional de sessões, mensagens, snapshots, resumos e referências.
- `src/boostprompt/research/duckduckgo_mcp.py`: porta de pesquisa e adaptador MCP stdio.
- `src/boostprompt/agents/discovery.py`: pergunta estruturada com texto explícito e um único passo de discovery.
- `src/boostprompt/agents/summary.py`: condensação PydanticAI de contexto de retomada.
- `src/boostprompt/agents/question_guide.py`: geração direta do roteiro para cliente.
- `src/boostprompt/graph/workflow.py`: grafo por turno e ramificação de finalização.
- `src/boostprompt/services/discovery_workflow.py`: serviço que cria sessão, monta contexto, executa grafo e persiste deltas.
- `src/boostprompt/cli/tui_main.py`: telas Textual orientadas pelo serviço, seleção de modo e refresh seguro.
- `tests/`: testes unitários reais e testes funcionais do repositório, grafo, serviço, MCP e TUI.

### Task 1: Contratos de domínio e cobertura configurada

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/boostprompt/models/schemas.py`
- Create: `tests/test_schemas.py`

**Interfaces:**
- Produces `DiscoveryMode`, `Question`, `ResearchFinding`, `SessionSummary`, `TurnResult` e `QuestionGuide` para os agentes, serviço e TUI.

- [ ] **Step 1: Write the failing test**

```python
from boostprompt.models.schemas import DiscoveryMode, Question

def test_question_requires_explicit_prompt_and_two_alternatives() -> None:
    question = Question(
        number=1,
        category="Objetivo",
        prompt="Qual resultado deve definir sucesso?",
        why_it_matters="Orienta o escopo.",
        alternatives=["Reduzir custo", "Aumentar conversão"],
        tradeoffs="Custo versus velocidade.",
        ai_recommendation="Definir uma métrica primária.",
        how_to_respond="Escolha uma opção ou responda livremente.",
    )
    assert question.prompt.startswith("Qual resultado")
    assert DiscoveryMode.PROMPT_DESENVOLVIMENTO.value == "prompt_desenvolvimento"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_schemas.py -q`

Expected: FAIL because `DiscoveryMode` and the `prompt` field do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class DiscoveryMode(str, Enum):
    PROMPT_DESENVOLVIMENTO = "prompt_desenvolvimento"
    ROTEIRO_PERGUNTAS_CLIENTE = "roteiro_perguntas_cliente"

class Question(BaseModel):
    number: int = Field(ge=1, le=50)
    category: str
    prompt: str = Field(min_length=1)
    why_it_matters: str
    alternatives: list[str] = Field(min_length=2, max_length=4)
    tradeoffs: str
    ai_recommendation: str
    how_to_respond: str
```

Add `pytest-cov` to the `dev` extra and configure coverage for `boostprompt`, with a terminal missing-lines report.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_schemas.py -q`

Expected: PASS.

### Task 2: Persistência incremental e resumo recuperável

**Files:**
- Modify: `src/boostprompt/memory/duckdb_store.py`
- Create: `tests/test_duckdb_store.py`

**Interfaces:**
- Consumes: `DiscoveryMode`, `SessionSummary` e mensagens `role`/`content` de Task 1.
- Produces: `create_session(name, mode)`, `append_turn(...)`, `load_for_resume(...)`, `save_summary(...)` e `list_sessions()`.

- [ ] **Step 1: Write the failing test**

```python
def test_append_turn_is_durable_without_duplicating_prior_messages(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "session.db")
    session = store.create_session("Pagamentos", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    store.append_turn(session.id, "Quero uma API.", "Qual público utilizará a API?", {}, 1)
    store.append_turn(session.id, "Lojistas.", "Qual volume diário?", {"usuarios": ["lojistas"]}, 2)
    resumed = store.load_for_resume(session.id, recent_limit=10)
    assert [message["content"] for message in resumed.messages] == [
        "Quero uma API.", "Qual público utilizará a API?", "Lojistas.", "Qual volume diário?"
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_duckdb_store.py::test_append_turn_is_durable_without_duplicating_prior_messages -q`

Expected: FAIL because `create_session` has no mode/session record and `append_turn` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def append_turn(self, session_id: str, user_content: str, assistant_content: str,
                context: dict[str, Any], questions_count: int) -> None:
    with self.transaction():
        self._append_message(session_id, "user", user_content)
        self._append_message(session_id, "assistant", assistant_content)
        self._save_snapshot(session_id, context, questions_count)
```

Add additive schema migrations for `mode`, ordered message `sequence`, `session_summaries` and `research_findings`. Use UTC timestamps and deterministic sequence allocation per session.

- [ ] **Step 4: Add the resume-summary regression test**

```python
def test_load_for_resume_returns_summary_and_only_recent_messages(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "session.db")
    session = store.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    store.save_summary(session.id, {"goal": "Centralizar clientes", "risks": ["LGPD"]}, 4)
    # append three later messages
    resumed = store.load_for_resume(session.id, recent_limit=2)
    assert resumed.summary["goal"] == "Centralizar clientes"
    assert len(resumed.messages) == 2
```

- [ ] **Step 5: Run focused tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_duckdb_store.py -q`

Expected: PASS.

### Task 3: Agentes PydanticAI de discovery, resumo e roteiro

**Files:**
- Modify: `src/boostprompt/agents/discovery.py`
- Create: `src/boostprompt/agents/summary.py`
- Create: `src/boostprompt/agents/question_guide.py`
- Modify: `src/boostprompt/agents/__init__.py`
- Create: `tests/test_agents_contract.py`

**Interfaces:**
- Consumes: modelos de Task 1 e estado por turno de Task 4.
- Produces: `DiscoveryAgent.ask_next(state)`, `SummaryAgent.summarize(...)` e `QuestionGuideAgent.create_guide(...)` com saídas Pydantic validadas.

- [ ] **Step 1: Write the failing tests**

```python
def test_discovery_formats_the_explicit_question_text() -> None:
    assert format_question(sample_question()).splitlines()[0] == "### Pergunta 1 — Objetivo"
    assert "Qual resultado deve definir sucesso?" in format_question(sample_question())

def test_question_guide_rejects_a_document_with_29_questions() -> None:
    with pytest.raises(ValidationError):
        QuestionGuide(markdown="# Perguntas", questions=[sample_question()] * 29)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_agents_contract.py -q`

Expected: FAIL because the formatter has no explicit prompt and guide contracts do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class SummaryAgent:
    async def summarize(self, previous: SessionSummary | None,
                        messages: Sequence[Message], context: dict[str, Any]) -> SessionSummary:
        result = await self.agent.run(render_summary_prompt(previous, messages, context))
        return result.data
```

Make the Pydantic result types validate 30–50 questions for guide mode and require `prompt`, `tradeoffs` and 2–4 alternatives for discovery mode. Keep provider calls behind methods that can be substituted by fakes in tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_agents_contract.py -q`

Expected: PASS.

### Task 4: MCP DuckDuckGo research adapter

**Files:**
- Create: `src/boostprompt/research/__init__.py`
- Create: `src/boostprompt/research/duckduckgo_mcp.py`
- Create: `tests/test_duckduckgo_mcp.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces `ResearchProvider.search(query) -> list[ResearchFinding]` and `ResearchUnavailableError`.
- Consumes: MCP stdio server `uvx duckduckgo-mcp-server` and models from Task 1.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_provider_normalizes_mcp_search_results() -> None:
    provider = DuckDuckGoMCPResearchProvider(client=FakeMCPClient([{"title": "LangGraph", "url": "https://langchain-ai.github.io/langgraph/", "text": "Docs"}]))
    findings = await provider.search("LangGraph persistence")
    assert findings[0].url.startswith("https://")

@pytest.mark.asyncio
async def test_provider_raises_typed_error_when_server_is_unavailable() -> None:
    provider = DuckDuckGoMCPResearchProvider(client=UnavailableMCPClient())
    with pytest.raises(ResearchUnavailableError):
        await provider.search("DuckDB")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_duckduckgo_mcp.py -q`

Expected: FAIL because the provider module is missing.

- [ ] **Step 3: Write minimal implementation**

```python
class DuckDuckGoMCPResearchProvider:
    async def search(self, query: str) -> list[ResearchFinding]:
        try:
            raw_results = await self._client.search(query)
        except (OSError, MCPError) as error:
            raise ResearchUnavailableError("Pesquisa DuckDuckGo indisponível.") from error
        return [ResearchFinding.model_validate(result) for result in raw_results]
```

Implement the real client with PydanticAI/MCP stdio APIs, command `uvx` and argument `duckduckgo-mcp-server`. Do not connect during import. Add a direct `mcp` dependency only if it is not already provided by the selected PydanticAI API.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_duckduckgo_mcp.py -q`

Expected: PASS.

### Task 5: LangGraph executes one interview turn

**Files:**
- Modify: `src/boostprompt/graph/workflow.py`
- Create: `tests/test_workflow.py`

**Interfaces:**
- Consumes: `DiscoveryAgent`, optional `ResearchProvider`, final agents and structured state.
- Produces `create_turn_workflow(agents)` and `run_turn(state)`; each call returns `TurnResult`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_workflow_calls_discovery_once_and_stops_for_user_answer() -> None:
    agents = FakeAgents(discovery=FakeDiscovery(continue_interview=True))
    result = await run_turn(agents, new_state(questions_count=1))
    assert agents.discovery.calls == 1
    assert result.awaiting_user_answer is True

@pytest.mark.asyncio
async def test_workflow_runs_final_agents_only_when_interview_can_finish() -> None:
    agents = FakeAgents(discovery=FakeDiscovery(continue_interview=False))
    result = await run_turn(agents, new_state(questions_count=30))
    assert agents.synthesis.calls == 1
    assert result.final_markdown is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_workflow.py -q`

Expected: FAIL because the existing graph loops discovery to 50 calls.

- [ ] **Step 3: Write minimal implementation**

```python
graph.add_edge(START, "research")
graph.add_conditional_edges("research", route_mode, {
    "guide": "question_guide", "discovery": "discovery"
})
graph.add_conditional_edges("discovery", route_discovery_result, {
    "await_answer": "persist", "finalize": "architecture"
})
graph.add_edge("persist", END)
```

Use no `discovery -> discovery` edge. A finalization condition is true only after 30 questions and agent approval, or at 50; guide mode bypasses architecture/security/delivery/synthesis.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_workflow.py -q`

Expected: PASS.

### Task 6: Serviço de sessão e política de resumo

**Files:**
- Create: `src/boostprompt/services/__init__.py`
- Create: `src/boostprompt/services/discovery_workflow.py`
- Create: `tests/test_discovery_workflow_service.py`

**Interfaces:**
- Consumes: repositório de Task 2, agentes de Task 3 e workflow de Task 5.
- Produces `create_session(name, mode)`, `submit_answer(session_id, answer)` e `resume_session(session_id)`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_submit_answer_persists_the_answer_and_next_question(tmp_path) -> None:
    service = build_service(tmp_path, discovery=FakeDiscovery())
    session = await service.create_session("Pagamentos", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    result = await service.submit_answer(session.id, "Preciso cobrar clientes.")
    assert result.awaiting_user_answer is True
    assert service.repository.get_messages(session.id)[-2:][0]["content"] == "Preciso cobrar clientes."

@pytest.mark.asyncio
async def test_service_uses_structured_summary_after_threshold(tmp_path) -> None:
    service = build_service(tmp_path, summarizer=FakeSummaryAgent())
    # seed messages above the configured unsummarized threshold
    await service.submit_answer(session_id, "nova resposta")
    assert service.repository.get_latest_summary(session_id)["goal"] == "Objetivo preservado"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_discovery_workflow_service.py -q`

Expected: FAIL because the service and automatic durability do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
async def submit_answer(self, session_id: str, answer: str) -> TurnResult:
    resumed = self.repository.load_for_resume(session_id, self.recent_message_limit)
    state = self._state_from(resumed, answer)
    result = await self.workflow.run_turn(state)
    self.repository.append_turn(session_id, answer, result.display_message, result.context, result.questions_count)
    await self._summarize_if_needed(session_id)
    return result
```

Only the service decides whether research is required and saves returned references. If research fails, pass an explicit degraded flag to the agents and persist the status.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_discovery_workflow_service.py -q`

Expected: PASS.

### Task 7: Textual TUI delegates to the service

**Files:**
- Modify: `src/boostprompt/cli/tui_main.py`
- Create: `tests/test_tui.py`

**Interfaces:**
- Consumes: `DiscoveryWorkflowService` from Task 6.
- Produces: a TUI with mode selection, safe session refresh, automatic session creation and resumable chat.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_refreshing_sessions_twice_does_not_remove_loading_widget() -> None:
    app = BoostPromptApp(service=FakeService())
    async with app.run_test() as pilot:
        await pilot.click("#list_sessions")
        await pilot.click("#refresh")
        assert app.screen.query_one("#loading", LoadingIndicator).display is False

@pytest.mark.asyncio
async def test_new_session_collects_output_mode_before_opening_chat() -> None:
    app = BoostPromptApp(service=FakeService())
    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        await pilot.click("#mode-client-guide")
        await pilot.press("enter")
        assert app.service.created_mode is DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_tui.py -q`

Expected: FAIL because refresh removes `#loading` and no output mode exists.

- [ ] **Step 3: Write minimal implementation**

```python
def _set_loading(self, visible: bool) -> None:
    self.query_one("#loading", LoadingIndicator).display = visible

@work(exclusive=True)
async def _process_with_workflow(self, user_message: str) -> None:
    result = await self.app.service.submit_answer(self.session_id, user_message)
    self._render_turn(result)
```

Inject the service in `BoostPromptApp.__init__`; remove direct agent/workflow/store construction and make all render-only methods avoid appending data twice.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_tui.py -q`

Expected: PASS.

### Task 8: Skill parity, integration suite and quality gates

**Files:**
- Modify: `tests/test_skill_contract.py`
- Modify: `README.md`
- Modify: `pyproject.toml`
- Create: `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: all preceding tasks.
- Produces: executable evidence for skills, both modes, durability, degraded research and coverage reporting.

- [ ] **Step 1: Write the failing end-to-end test**

```python
@pytest.mark.asyncio
async def test_client_guide_is_persisted_without_running_final_scope_agents(tmp_path) -> None:
    service = build_service(tmp_path, guide=FakeQuestionGuide(count=30))
    session = await service.create_session("Portal", DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE)
    result = await service.submit_answer(session.id, "Portal de fornecedores")
    assert result.final_markdown.startswith("# Perguntas para Discovery com o Cliente")
    assert service.architecture.calls == service.security.calls == service.delivery.calls == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_end_to_end.py -q`

Expected: FAIL because guide mode is not implemented end-to-end.

- [ ] **Step 3: Complete implementation and documentation**

Add the exact skill-contract assertions for modes, 30–50 bounds, mandatory headings and DuckDuckGo policy. Document `uv sync --extra dev`, `boostprompt`, model configuration and how to install `ddg-search` with `install.py`.

- [ ] **Step 4: Run focused functional suite and coverage**

Run: `uv run --extra dev pytest tests/test_schemas.py tests/test_duckdb_store.py tests/test_agents_contract.py tests/test_duckduckgo_mcp.py tests/test_workflow.py tests/test_discovery_workflow_service.py tests/test_tui.py tests/test_end_to_end.py --cov=src/boostprompt --cov-report=term-missing -q`

Expected: PASS and a coverage report that identifies any externally-dependent branches not executable locally.

- [ ] **Step 5: Run full quality gates**

Run: `uv run --extra dev pytest -q && uv run --extra dev ruff check src tests && uv run --extra dev mypy src`

Expected: all tests pass, Ruff returns no violations, and mypy returns no errors.
