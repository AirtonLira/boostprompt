# Geração antecipada de prompt e continuação de sessão Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir gerar o prompt de uma entrevista de desenvolvimento após dez respostas e iniciar uma nova entrevista compacta a partir de uma sessão concluída.

**Architecture:** O workflow recebe um sinal explícito para executar a cadeia de finalização sem discovery. O serviço valida os casos de uso e coordena o resumo; o DuckDB persiste estados, documentos e sessões semeadas; a TUI apenas expõe as ações e renderiza o resumo em bullets.

**Tech Stack:** Python 3.11+, Textual, LangGraph, PydanticAI, DuckDB, Pydantic, pytest e pytest-asyncio.

## Global Constraints

- Todo texto visível ao usuário e todo Markdown gerado permanece em pt-BR.
- A geração antecipada só vale para `DiscoveryMode.PROMPT_DESENVOLVIMENTO` e exige `questions_count >= 10`.
- Uma geração antecipada não insere uma mensagem vazia, não conclui a sessão e a marca como `in_progress`.
- Conclusões normais e roteiros para cliente ficam com status `completed`.
- A continuação cria uma sessão nova; não copia o histórico e injeta somente o `SessionSummary` persistido nela.
- A TUI exige selecionar LiteLLM ou OpenAI antes de criar o serviço padrão; serviços injetados seguem disponíveis para testes.
- Os comandos de terminal devem usar o prefixo `rtk`.

---

### Task 1: Configurar e selecionar o provedor de modelo

**Files:**

- Modify: `src/boostprompt/llm.py`
- Modify: `src/boostprompt/cli/tui_main.py`
- Modify: `tests/test_llm_configuration.py`
- Modify: `tests/test_agents_contract.py`
- Modify: `tests/test_final_agents.py`

**Interfaces:**

- Consumes: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LITELLM_BASE_URL`, `LLM_API_KEY`, `LITELLM_API_KEY`, `API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` e `OPENAI_API_KEY`.
- Produces: `ModelProvider` com valores `litellm` e `openai`; `OpenAICompatibleSettings.from_environment(provider)`; uma tela Textual de seleção que inicializa o `DiscoveryWorkflowService` apenas após a escolha.

- [ ] **Step 1: Write the failing tests**

Em `tests/test_llm_configuration.py`, acrescente um teste com arquivo temporário contendo `OPENAI_MODEL=gpt-4.1-mini` e `OPENAI_API_KEY=token-openai`; limpe as demais variáveis e verifique que `OpenAICompatibleSettings.from_environment(ModelProvider.OPENAI).build_model()` retorna `OpenAIChatModel` com o modelo configurado e sem `base_url` customizada.

Acrescente um teste equivalente para LiteLLM, chamando `from_environment(ModelProvider.LITELLM)` com `LITELLM_BASE_URL`, `API_KEY` e `LLM_MODEL`. O caso sem URL LiteLLM deve lançar `ValueError` contendo `LITELLM_BASE_URL`.

Em `tests/test_tui.py`, instancie `BoostPromptApp()` sem serviço injetado, confirme que a primeira tela contém `#select-litellm` e `#select-openai`, e que clicar sem configuração exibe erro sem abrir `MainMenu`. Crie um arquivo `.env` temporário LiteLLM, defina `BOOSTPROMPT_ENV_FILE`, clique `#select-litellm` e confirme que a tela seguinte é `MainMenu`.

Nos testes que instanciam agentes diretamente apenas para substituir `agent.agent` por um fake, passe `model="test"`; assim eles deixam de tentar inicializar OpenAI real. Não altere os testes que validam explicitamente a construção pelo ambiente.

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk pytest tests/test_llm_configuration.py tests/test_tui.py tests/test_agents_contract.py tests/test_final_agents.py -q`

Expected: FAIL porque `ModelProvider`, a tela de seleção e o argumento `provider` ainda não existem; os testes de agentes também reproduzem a dependência indevida de `OPENAI_API_KEY`.

- [ ] **Step 3: Write minimal implementation**

Em `src/boostprompt/llm.py`, crie:

```python
class ModelProvider(StrEnum):
    LITELLM = "litellm"
    OPENAI = "openai"
```

Faça `OpenAICompatibleSettings.from_environment(provider: ModelProvider)` resolver somente as variáveis daquele provedor. Para LiteLLM, valide modelo, URL e chave; para OpenAI, valide modelo e `OPENAI_API_KEY`, e mantenha `OPENAI_BASE_URL` opcional. Preserve `build_model()` usando `OpenAIProvider` e `OpenAIChatModel`.

Em `DiscoveryWorkflowService.create_default`, exija e repasse `provider: ModelProvider`. Em `BoostPromptApp`, aceite um serviço injetado como hoje; quando ele não existir, comece em `ProviderSelectionScreen`. Essa tela chama `DiscoveryWorkflowService.create_default(provider=...)`, captura `ValueError` e só abre `MainMenu` quando o serviço foi construído. Os botões são `#select-litellm` e `#select-openai`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_llm_configuration.py tests/test_tui.py tests/test_agents_contract.py tests/test_final_agents.py -q`

Expected: PASS; nenhum teste usa segredo real e o fluxo LiteLLM do `.env` é validado sem depender do diretório atual.

- [ ] **Step 5: Commit**

```bash
rtk git add src/boostprompt/llm.py src/boostprompt/services/discovery_workflow.py src/boostprompt/cli/tui_main.py tests/test_llm_configuration.py tests/test_tui.py tests/test_agents_contract.py tests/test_final_agents.py
rtk git commit -m "feat: select LiteLLM or OpenAI in the TUI"
```

### Task 2: Sinalizar finalização antecipada no workflow


**Files:**

- Modify: `src/boostprompt/graph/workflow.py`
- Test: `tests/test_workflow.py`

**Interfaces:**

- Consumes: `TurnState` com `mode`, `context`, `messages`, `decisions` e `questions_count`.
- Produces: `TurnState["force_finalize"]: bool`; quando verdadeiro no modo de desenvolvimento, o workflow passa de `research` diretamente para `architecture` e retorna um `TurnResult` final.

- [ ] **Step 1: Write the failing test**

Adicione em `tests/test_workflow.py` o teste abaixo, usando os fakes já existentes. Ele prova que o sinal não chama discovery e ainda percorre synthesis:

```python
@pytest.mark.asyncio
async def test_workflow_finalizes_without_discovery_when_forced() -> None:
    discovery = FakeDiscovery(
        DiscoveryResponse(question=question(), should_continue=True, summary="Não usar.")
    )
    synthesis = FakeFinalAgent("# Escopo parcial")
    workflow = TurnWorkflow(
        WorkflowAgents(
            discovery=discovery,
            architecture=FakeFinalAgent(),
            security=FakeFinalAgent(),
            delivery=FakeFinalAgent(),
            synthesis=synthesis,
        )
    )
    state = turn_state(questions_count=10)
    state["force_finalize"] = True

    result = await workflow.run_turn(state)

    assert discovery.calls == 0
    assert synthesis.calls == 1
    assert result.final_markdown == "# Escopo parcial"
    assert result.awaiting_user_answer is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_workflow.py::test_workflow_finalizes_without_discovery_when_forced -q`

Expected: FAIL because discovery is called once; `force_finalize` is not yet routed to the finalization nodes.

- [ ] **Step 3: Write minimal implementation**

Em `src/boostprompt/graph/workflow.py`:

```python
class TurnState(TypedDict, total=False):
    # campos existentes
    force_finalize: bool

@staticmethod
def _route_after_research(state: TurnState) -> str:
    if state.get("force_finalize", False):
        return "finalize"
    if state["mode"] is DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE:
        return "guide"
    return "discovery"
```

Não altere `_discovery`; o fluxo forçado deve pular esse nó por completo. Mantenha a rota para `question_guide` como está quando `force_finalize` não for fornecido.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_workflow.py -q`

Expected: PASS, incluindo o novo teste e os fluxos de pesquisa, entrevista normal e roteiro de cliente.

- [ ] **Step 5: Commit**

```bash
rtk git add src/boostprompt/graph/workflow.py tests/test_workflow.py
rtk git commit -m "feat: allow forced workflow finalization"
```

### Task 3: Persistir estado de geração e sessões de continuação

**Files:**

- Modify: `src/boostprompt/memory/duckdb_store.py`
- Test: `tests/test_duckdb_store.py`

**Interfaces:**

- Consumes: `Session`, `SessionSummary`, contexto mínimo da origem e Markdown final.
- Produces: `DuckDBStore.save_generated_markdown(session_id, context, questions_count, status)`, `DuckDBStore.set_session_status(session_id, status)`, `DuckDBStore.create_continuation(source, summary)` e sessões com status `active`, `in_progress` ou `completed`.

- [ ] **Step 1: Write the failing tests**

Adicione testes que exercitem o armazenamento sem depender de agentes:

```python
def test_partial_markdown_is_persisted_without_new_messages_and_marks_in_progress(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    store.append_turn(session.id, "Criar portal", "Pergunta 1", {"objetivo": "Portal"}, 10)
    before = store.get_messages(session.id)

    store.save_generated_markdown(session.id, {"objetivo": "Portal"}, 10, "in_progress", "# Rascunho")

    assert store.get_messages(session.id) == before
    assert store.get_final_markdown(session.id) == "# Rascunho"
    assert store.get_session(session.id)["status"] == "in_progress"


def test_continuation_has_new_identity_and_only_seeded_summary(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    source = store.create_session("Portal", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    summary = SessionSummary(goal="Portal de fornecedores", decisions=["Entregar MVP"])

    continuation = store.create_continuation(source, summary)
    resumed = store.load_for_resume(continuation.id)

    assert continuation.id != source.id
    assert continuation.codigo != source.codigo
    assert continuation.status == "active"
    assert resumed.messages == []
    assert resumed.summary == summary
    assert resumed.context["sessao_origem"]["id"] == source.id
```

Inclua ainda um teste de migração que cria uma sessão `active`, salva um Markdown final, fecha e reabre o banco; a sessão legada deve aparecer como `completed`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk pytest tests/test_duckdb_store.py -q`

Expected: FAIL com `AttributeError` para as duas operações novas e com o status legado ainda `active`.

- [ ] **Step 3: Write minimal implementation**

Em `DuckDBStore`:

```python
def set_session_status(self, session_id: str, status: str) -> None:
    self.conn.execute(
        "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
        [status, _utc_now(), session_id],
    )

def save_generated_markdown(
    self, session_id: str, context: dict[str, Any], questions_count: int,
    status: str, markdown: str,
) -> None:
    with self.transaction():
        self._save_context_snapshot(session_id, context, questions_count)
        self._save_final_markdown(session_id, markdown)
        self.set_session_status(session_id, status)
```

Implemente `create_continuation(source, summary)` em uma única transação: insira uma nova sessão com nome `f"{source.nome} — continuação"`, modo da origem e status `active`; persista `summary`; e salve o snapshot `{"sessao_origem": {"id": source.id, "codigo": source.codigo, "nome": source.nome}}` com zero perguntas. Não copie mensagens, decisões, referências ou o documento da origem.

No final de `_migrate_existing_schema`, execute uma migração idempotente que converta para `completed` somente sessões legadas `active` com registro em `final_documents`. As gerações antecipadas serão `in_progress` e permanecem intactas.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_duckdb_store.py -q`

Expected: PASS, sem regressão de persistência, resumo, retomada ou exclusão.

- [ ] **Step 5: Commit**

```bash
rtk git add src/boostprompt/memory/duckdb_store.py tests/test_duckdb_store.py
rtk git commit -m "feat: persist partial prompts and continuation sessions"
```

### Task 4: Expor geração antecipada e continuação no serviço

**Files:**

- Modify: `src/boostprompt/services/discovery_workflow.py`
- Test: `tests/test_discovery_workflow_service.py`

**Interfaces:**

- Consumes: identificador da sessão, `questions_count`, `ResumedSession`, `SessionSummarizer` e `TurnRunner`.
- Produces: `async generate_partial_prompt(session_id) -> TurnResult` e `async continue_completed_session(session_id) -> Session`.

- [ ] **Step 1: Write the failing tests**

Crie um `PartialFinalWorkflow` que registra o estado recebido e devolve um `TurnResult` com `display_message="Rascunho gerado."`, `context=state["context"]`, `questions_count=state["questions_count"]`, `awaiting_user_answer=False` e `final_markdown="# Rascunho"`. Acrescente estes testes:

```python
@pytest.mark.asyncio
async def test_partial_prompt_requires_ten_answered_questions(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db", workflow=FakeWorkflow(), summary_agent=FakeSummaryAgent()
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    with pytest.raises(ValueError, match="pelo menos 10"):
        await service.generate_partial_prompt(session.id)


@pytest.mark.asyncio
async def test_partial_prompt_finalizes_without_appending_a_user_message(tmp_path) -> None:
    workflow = PartialFinalWorkflow()
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db", workflow=workflow, summary_agent=FakeSummaryAgent()
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.append_turn(session.id, "Demanda", "Pergunta 10", {"objetivo": "CRM"}, 10)

    result = await service.generate_partial_prompt(session.id)

    assert workflow.states[0]["force_finalize"] is True
    assert result.final_markdown == "# Rascunho"
    assert [item["content"] for item in service.repository.get_messages(session.id)] == ["Demanda", "Pergunta 10"]
    assert service.resume_session(session.id).session.status == "in_progress"
```

Crie também um resumidor fake que registra `messages` e devolve decisões. Teste que `continue_completed_session` rejeita sessão não concluída, usa todas as mensagens da sessão concluída, cria uma sessão com outro código e que o primeiro `submit_answer` recebe `context["resumo_da_sessao"]["decisions"]` sem as mensagens antigas.

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk pytest tests/test_discovery_workflow_service.py -q`

Expected: FAIL com `AttributeError` para `generate_partial_prompt` e `continue_completed_session`.

- [ ] **Step 3: Write minimal implementation**

Adicione a constante `MINIMUM_PARTIAL_PROMPT_QUESTIONS = 10`. Em `generate_partial_prompt`:

```python
resumed = self.repository.load_for_resume(session_id, self.recent_message_limit)
if resumed.session.mode is not DiscoveryMode.PROMPT_DESENVOLVIMENTO:
    raise ValueError("A geração antecipada está disponível apenas para entrevistas de desenvolvimento.")
if resumed.session.questions_count < MINIMUM_PARTIAL_PROMPT_QUESTIONS:
    raise ValueError("Responda pelo menos 10 perguntas antes de gerar o prompt.")
state = self._build_turn_state(resumed, answer=None, force_finalize=True)
result = await self.workflow.run_turn(state)
if result.final_markdown is None:
    raise RuntimeError("Não foi possível gerar o prompt parcial.")
self.repository.save_generated_markdown(
    session_id, result.context, result.questions_count, "in_progress", result.final_markdown
)
return result
```

Atualize `_build_turn_state` para aceitar `answer: str | None` e `force_finalize: bool = False`. Quando `answer` for `None`, mantenha `messages` e `last_user_message` da sessão sem anexar mensagem; sempre propague `force_finalize` no estado.

No fluxo já existente de `submit_answer`, passe `status="completed"` à persistência somente se `result.final_markdown is not None` e `not result.awaiting_user_answer`; mantenha `active` nos demais turnos.

Em `continue_completed_session`, carregue a origem com o limite normal, valide `status == "completed"`, converta `repository.get_messages(session_id)` em `Message` e rejeite a lista vazia. Execute `summary_agent.summarize(previous=resumed.summary, messages=all_messages, context=resumed.context)` e somente depois chame `repository.create_continuation(resumed.session, summary)`. A ordem garante que falhas de resumo não criem sessão parcial.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_discovery_workflow_service.py -q`

Expected: PASS, incluindo os testes de resumo periódico, referências e persistência do Markdown final.

- [ ] **Step 5: Commit**

```bash
rtk git add src/boostprompt/services/discovery_workflow.py tests/test_discovery_workflow_service.py
rtk git commit -m "feat: generate partial prompts and continue completed sessions"
```

### Task 5: Disponibilizar os fluxos na TUI

**Files:**

- Modify: `src/boostprompt/cli/tui_main.py`
- Test: `tests/test_tui.py`

**Interfaces:**

- Consumes: os novos métodos assíncronos do `SessionService`, `Session.status`, `Session.questions_count` e `SessionSummary`.
- Produces: botões `#generate-partial` e `#continue-session`; resumo Markdown em bullets e abertura de um novo `ChatScreen` para a continuação.

- [ ] **Step 1: Write the failing tests**

Amplie `FakeService` com `generate_partial_prompt` e `continue_completed_session`. Adicione estes testes Textual:

```python
@pytest.mark.asyncio
async def test_partial_prompt_button_stays_disabled_before_ten_answers() -> None:
    app = BoostPromptApp(service=FakeService())

    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "API"
        await pilot.click("#create")

        assert app.screen.query_one("#generate-partial", Button).disabled is True


@pytest.mark.asyncio
async def test_completed_session_can_start_a_compact_continuation() -> None:
    service = ResumingFinalService()
    app = BoostPromptApp(service=service)

    async with app.run_test() as pilot:
        await pilot.click("#list_sessions")
        app.screen.query_one("#sessions-list-view", ListView).index = 0
        await pilot.pause()
        await pilot.click("#continue-session")
        await pilot.pause()

        assert service.continued_from == "session-final"
        assert isinstance(app.screen, ChatScreen)
        assert "continuação" in app.screen.session.nome
```

Inclua um teste com sessão de dez perguntas que clica `#generate-partial`, verifica a chamada ao serviço e confirma que `#generate` abre o Markdown retornado.

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk pytest tests/test_tui.py -q`

Expected: FAIL porque os botões e os métodos do protocolo não existem.

- [ ] **Step 3: Write minimal implementation**

No `SessionService`, declare os métodos assíncronos `generate_partial_prompt(self, session_id: str) -> TurnResult` e `continue_completed_session(self, session_id: str) -> Session`, cada um com corpo de protocolo vazio conforme os métodos já existentes no arquivo.

Em `ChatScreen.compose`, acrescente o botão `Button("Gerar prompt agora", id="generate-partial", variant="success")`. Na montagem, desabilite-o salvo quando `session.mode is DiscoveryMode.PROMPT_DESENVOLVIMENTO`, `session.questions_count >= 10` e `session.status != "completed"`. Após cada `_send_message`, atualize `self.session` com `questions_count=result.questions_count` e ajuste a disponibilidade do botão.

No mesmo painel, acrescente `Button("Continuar em nova entrevista", id="continue-session")`, disponível apenas para `session.status == "completed"`. Para sessões concluídas, renderize a `SessionSummary` com uma função privada que produz Markdown de bullets, por exemplo:

```python
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
```

No clique de `#generate-partial`, trate `ValueError` e `RuntimeError` como os demais erros, guarde `result.final_markdown` e notifique que o rascunho foi salvo. No clique de `#continue-session`, aguarde o novo serviço e faça `self.app.push_screen(ChatScreen(session=continuation, is_new=False))`. A tela nova carregará apenas o resumo persistido pela camada de serviço.

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_tui.py -q`

Expected: PASS, incluindo criação, envio, exportação, exclusão, retomada e os três testes novos.

- [ ] **Step 5: Commit**

```bash
rtk git add src/boostprompt/cli/tui_main.py tests/test_tui.py
rtk git commit -m "feat: expose partial prompt and continuation actions"
```

### Task 6: Verificação integrada e regressão

**Files:**

- Modify: `README.md` somente se a interface documentada mencionar a lista de ações da sessão.
- Test: `tests/test_workflow.py`, `tests/test_duckdb_store.py`, `tests/test_discovery_workflow_service.py`, `tests/test_tui.py` e suíte completa.

**Interfaces:**

- Consumes: comportamento entregue nas quatro tarefas anteriores.
- Produces: evidência de que os modos existentes, a persistência e a TUI permanecem funcionais.

- [ ] **Step 1: Write the cross-layer regression test**

Em `tests/test_discovery_workflow_service.py`, acrescente este fake e teste; eles provam que a sessão permanece utilizável após salvar o rascunho:

```python
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


@pytest.mark.asyncio
async def test_session_accepts_new_answers_after_partial_prompt_generation(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db",
        workflow=PartialThenQuestionWorkflow(),
        summary_agent=FakeSummaryAgent(),
    )
    session = await service.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    service.repository.append_turn(session.id, "Demanda", "Pergunta 10", {"objetivo": "CRM"}, 10)

    await service.generate_partial_prompt(session.id)
    await service.submit_answer(session.id, "A nova feature terá auditoria.")

    resumed = service.resume_session(session.id)
    assert resumed.session.status == "in_progress"
    assert resumed.session.questions_count == 11
    assert service.repository.get_messages(session.id)[-1]["content"] == "### Pergunta 11 — Escopo"
```

- [ ] **Step 2: Run the focused regression suite**

Run: `rtk pytest tests/test_workflow.py tests/test_duckdb_store.py tests/test_discovery_workflow_service.py tests/test_tui.py -q`

Expected: PASS sem warnings ou erros.

- [ ] **Step 3: Run all automated checks**

Run:

```bash
rtk pytest -q
rtk ruff check .
rtk mypy src
```

Expected: todos os comandos passam; qualquer falha preexistente deve ser reportada separadamente, sem atribuí-la ao recurso.

- [ ] **Step 4: Review the final diff**

Run:

```bash
rtk git diff main...HEAD
rtk git status
```

Expected: mudanças restritas ao workflow, persistência, serviço, TUI, testes e documentação necessária; árvore limpa após os commits das tarefas.

- [ ] **Step 5: Commit documentation update if one was needed**

```bash
rtk git add README.md
rtk git commit -m "docs: document partial prompt generation"
```

Pule este commit somente se `README.md` não necessitar alteração; não crie commit vazio.
