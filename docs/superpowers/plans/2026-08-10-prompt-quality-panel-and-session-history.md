# Painel de qualidade do prompt e histórico enriquecido — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exibir e persistir métricas determinísticas de qualidade do prompt durante entrevistas de discovery e apresentá-las no histórico de sessões da TUI.

**Architecture:** Um avaliador puro converte o contexto estruturado, decisões e progresso da entrevista em um `PromptQualityEvaluation`. O serviço calcula esse snapshot após cada turno e o DuckDB o persiste junto ao turno ou ao rascunho gerado. A TUI consome apenas o snapshot retornado, em um painel responsivo, e a lista de sessões consulta a última prontidão salva.

**Tech Stack:** Python 3.11+, Pydantic 2, Textual, DuckDB, LangGraph, PydanticAI, pytest, pytest-asyncio, Ruff e mypy.

## Global Constraints

- Manter PydanticAI, LangGraph, Textual e DuckDB nas responsabilidades atuais; a avaliação não faz chamada ao LLM.
- Aplicar avaliação somente ao modo `prompt_desenvolvimento`; `roteiro_perguntas_cliente` deve informar avaliação não aplicável e continuar gerando o roteiro em um turno.
- Métricas devem ser inteiros de 0 a 100 quando aplicáveis, calculadas localmente e explicáveis pelas fórmulas da especificação.
- Não quebrar bancos DuckDB existentes; a migração de schema deve ser apenas aditiva.
- Preservar a persistência atômica de um turno, o limite de 30–50 perguntas e a geração antecipada após 10 respostas.
- Toda alteração de comportamento deve receber teste automatizado; todos os comandos shell deste plano usam `rtk`.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| `src/boostprompt/models/schemas.py` | Contrato Pydantic da avaliação e campo opcional no resultado do turno. |
| `src/boostprompt/services/prompt_quality.py` | Cálculo puro e testável de cobertura, clareza e prontidão. |
| `src/boostprompt/memory/duckdb_store.py` | Schema, gravação, recuperação e listagem do último snapshot por sessão. |
| `src/boostprompt/services/discovery_workflow.py` | Orquestra avaliação e persistência no ciclo de resposta e de rascunho. |
| `src/boostprompt/cli/prompt_quality_panel.py` | Widget Textual dedicado à apresentação acessível das três métricas. |
| `src/boostprompt/cli/tui_main.py` | Posiciona e atualiza o painel; mostra prontidão e atualização no histórico. |
| `tests/test_prompt_quality.py` | Unidade das fórmulas, limites e modo não aplicável. |
| `tests/test_duckdb_store.py` | Persistência, retomada, listagem e exclusão do snapshot. |
| `tests/test_discovery_workflow_service.py` | Avaliação adicionada ao resultado e persistida em cada caminho do serviço. |
| `tests/test_tui.py` | Painel após envio/retomada e conteúdo enriquecido da lista de sessões. |
| `README.md` | Documenta painel, significado dos valores e histórico enriquecido. |

---

### Task 1: Modelo e avaliador determinístico

**Files:**
- Modify: `src/boostprompt/models/schemas.py`
- Create: `src/boostprompt/services/prompt_quality.py`
- Create: `tests/test_prompt_quality.py`

**Interfaces:**
- Produces: `PromptQualityEvaluation` com `applicable: bool`, `coverage: int | None`, `decision_clarity: int | None`, `prompt_readiness: int | None`, `questions_count: int`, `status_text: str` e `evaluated_at: datetime`.
- Produces: `PromptQualityEvaluator.evaluate(*, mode: DiscoveryMode, context: Mapping[str, Any], decisions: Sequence[Mapping[str, Any]], questions_count: int) -> PromptQualityEvaluation`.
- Consumes: `DiscoveryMode` e os campos já serializados de `ContextState`.

- [ ] **Step 1: Escrever os testes que falham para a avaliação**

```python
from boostprompt.models.schemas import DiscoveryMode
from boostprompt.services.prompt_quality import PromptQualityEvaluator


def test_empty_development_context_has_zero_scores() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context={}, decisions=[], questions_count=0,
    )
    assert (evaluation.coverage, evaluation.decision_clarity, evaluation.prompt_readiness) == (0, 0, 0)


def test_covered_blocks_and_unresolved_items_change_the_scores() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.PROMPT_DESENVOLVIMENTO,
        context={
            "necessidade": "Portal", "objetivo": "Reduzir prazo", "usuarios": ["lojistas"],
            "requisitos_funcionais": ["Cadastrar pedido"], "seguranca": ["OAuth"],
            "pendencias": ["Definir SLA"], "riscos": ["Dependência externa"],
        },
        decisions=[{"decision": "Entregar MVP"}], questions_count=15,
    )
    assert evaluation.coverage == 56
    assert 0 < evaluation.decision_clarity < 100
    assert 0 < evaluation.prompt_readiness < 100


def test_client_guide_marks_quality_as_not_applicable() -> None:
    evaluation = PromptQualityEvaluator().evaluate(
        mode=DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE,
        context={"necessidade": "Portal"}, decisions=[], questions_count=30,
    )
    assert evaluation.applicable is False
    assert evaluation.prompt_readiness is None
```

- [ ] **Step 2: Executar o teste para confirmar a falha**

Run: `rtk proxy uv run --extra dev pytest tests/test_prompt_quality.py -q`  
Expected: FAIL porque `boostprompt.services.prompt_quality` e `PromptQualityEvaluation` ainda não existem.

- [ ] **Step 3: Criar o contrato e a implementação mínima**

Em `schemas.py`, adicionar o modelo com validação de faixa para os valores opcionais:

```python
class PromptQualityEvaluation(BaseModel):
    applicable: bool = True
    coverage: int | None = Field(default=None, ge=0, le=100)
    decision_clarity: int | None = Field(default=None, ge=0, le=100)
    prompt_readiness: int | None = Field(default=None, ge=0, le=100)
    questions_count: int = Field(default=0, ge=0, le=50)
    status_text: str = "Aguardando contexto inicial."
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

Em `prompt_quality.py`, declarar os nove grupos de cobertura da especificação, considerar coleções vazias como ausentes e implementar `evaluate`. Para desenvolvimento: calcular `coverage = round(covered_blocks / 9 * 100)`; contar no máximo 10 evidências confirmadas entre objetivo, problema, tipo, listas de pessoas, requisitos, integrações, arquitetura e `decisions`; calcular `decision_clarity = clamp(round(100 * evidence / (10 + 2 * uncertainty)))`; e calcular `prompt_readiness = round(0.50 * coverage + 0.35 * clarity + 0.15 * min(questions_count / 30, 1) * 100)`. Para roteiro de cliente, retornar `applicable=False`, três valores `None` e texto `Avaliação não aplicável ao roteiro gerado diretamente.`. Os textos de estado devem separar `Aguardando contexto inicial.`, `Contexto em consolidação.` e `Base suficiente para um rascunho de prompt.` por faixas de prontidão 0, 1–69 e 70–100.

- [ ] **Step 4: Executar a unidade do avaliador**

Run: `rtk proxy uv run --extra dev pytest tests/test_prompt_quality.py -q`  
Expected: PASS.

- [ ] **Step 5: Commitar o componente isolado**

```bash
rtk git add src/boostprompt/models/schemas.py src/boostprompt/services/prompt_quality.py tests/test_prompt_quality.py
rtk git commit -m "feat: add deterministic prompt quality evaluator"
```

### Task 2: Persistir e recuperar snapshots de qualidade no DuckDB

**Files:**
- Modify: `src/boostprompt/memory/duckdb_store.py`
- Modify: `tests/test_duckdb_store.py`

**Interfaces:**
- Consumes: `PromptQualityEvaluation` de `boostprompt.models.schemas`.
- Produces: `DuckDBStore.save_quality_evaluation(session_id: str, evaluation: PromptQualityEvaluation) -> None`.
- Produces: `DuckDBStore.get_latest_quality_evaluation(session_id: str) -> PromptQualityEvaluation | None`.
- Extends: `DuckDBStore.append_turn(..., quality_evaluation: PromptQualityEvaluation | None = None) -> None` e `DuckDBStore.save_generated_markdown(..., quality_evaluation: PromptQualityEvaluation | None = None) -> None`.
- Extends: `ResumedSession` com `quality_evaluation: PromptQualityEvaluation | None` e cada item de `list_sessions()` com `prompt_readiness`, `quality_applicable` e `quality_evaluated_at`.

- [ ] **Step 1: Escrever os testes de persistência e compatibilidade**

```python
def test_quality_snapshot_is_persisted_with_a_turn_and_restored_on_resume(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal")
    quality = PromptQualityEvaluation(coverage=44, decision_clarity=36, prompt_readiness=39, questions_count=1)
    store.append_turn(session.id, "Criar portal", "Pergunta 1", {"objetivo": "Portal"}, 1, quality_evaluation=quality)
    restored = store.load_for_resume(session.id).quality_evaluation
    assert restored is not None
    assert (restored.coverage, restored.decision_clarity, restored.prompt_readiness) == (44, 36, 39)


def test_list_sessions_exposes_the_latest_readiness_without_breaking_legacy_sessions(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    legacy = store.create_session("Legada")
    rated = store.create_session("Avaliada")
    store.save_quality_evaluation(rated.id, PromptQualityEvaluation(prompt_readiness=61, questions_count=12))
    sessions = {item["nome"]: item for item in store.list_sessions()}
    assert sessions["Legada"]["prompt_readiness"] is None
    assert sessions["Avaliada"]["prompt_readiness"] == 61


def test_delete_session_removes_quality_snapshots(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal")
    store.save_quality_evaluation(session.id, PromptQualityEvaluation(prompt_readiness=20))
    store.delete_session(session.id)
    assert store.get_latest_quality_evaluation(session.id) is None
```

- [ ] **Step 2: Executar os testes para confirmar a falha**

Run: `rtk proxy uv run --extra dev pytest tests/test_duckdb_store.py -q`  
Expected: FAIL porque os argumentos, campos de retomada e métodos de qualidade não existem.

- [ ] **Step 3: Implementar schema e operações transacionais**

Criar, dentro de `_init_schema`, a tabela aditiva abaixo antes de `_migrate_existing_schema`:

```sql
CREATE TABLE IF NOT EXISTS session_quality_evaluations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    applicable BOOLEAN NOT NULL,
    coverage INTEGER,
    decision_clarity INTEGER,
    prompt_readiness INTEGER,
    questions_count INTEGER NOT NULL,
    status_text TEXT NOT NULL,
    evaluated_at TIMESTAMP NOT NULL
)
```

Adicionar `_save_quality_evaluation` sem abrir transação, e `save_quality_evaluation` como wrapper transacional. Chamar a variante privada dentro das transações existentes de `append_turn` e `save_generated_markdown` somente quando o argumento for fornecido. Carregar o último registro por `evaluated_at DESC, id DESC` e converter para `PromptQualityEvaluation`; registrar datas DuckDB sem timezone, como o restante do repositório. Acrescentar `session_quality_evaluations` antes de `context_snapshots` na exclusão manual. Na consulta de `list_sessions`, usar `LEFT JOIN` com subconsulta correlacionada para trazer somente o último snapshot e retornar `None` para sessões legadas; não alterar as oito colunas consumidas por `get_session`.

- [ ] **Step 4: Executar os testes do repositório**

Run: `rtk proxy uv run --extra dev pytest tests/test_duckdb_store.py -q`  
Expected: PASS.

- [ ] **Step 5: Commitar a persistência**

```bash
rtk git add src/boostprompt/memory/duckdb_store.py tests/test_duckdb_store.py
rtk git commit -m "feat: persist prompt quality snapshots"
```

### Task 3: Integrar avaliação ao serviço de discovery

**Files:**
- Modify: `src/boostprompt/models/schemas.py`
- Modify: `src/boostprompt/services/discovery_workflow.py`
- Modify: `tests/test_discovery_workflow_service.py`

**Interfaces:**
- Consumes: `PromptQualityEvaluator.evaluate(...)`, `TurnResult` e os métodos de qualidade do repositório definidos na Task 2.
- Extends: `TurnResult` com `quality_evaluation: PromptQualityEvaluation | None = None`.
- Produces: `DiscoveryWorkflowService._evaluate_quality(resumed: ResumedSession, context: dict[str, Any], questions_count: int) -> PromptQualityEvaluation`.

- [ ] **Step 1: Escrever os testes de integração do serviço**

```python
@pytest.mark.asyncio
async def test_submit_answer_returns_and_persists_quality_evaluation(tmp_path) -> None:
    service = DiscoveryWorkflowService.with_database(
        db_path=tmp_path / "sessions.db", workflow=FakeWorkflow(), summary_agent=FakeSummaryAgent()
    )
    session = await service.create_session("Pagamentos", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    result = await service.submit_answer(session.id, "Preciso cobrar clientes.")
    assert result.quality_evaluation is not None
    assert service.resume_session(session.id).quality_evaluation == result.quality_evaluation


@pytest.mark.asyncio
async def test_partial_prompt_refreshes_quality_without_creating_messages(tmp_path) -> None:
    service = build_service_with_ten_answers(tmp_path)
    before = service.repository.get_messages(service.session.id)
    result = await service.generate_partial_prompt(service.session.id)
    assert result.quality_evaluation is not None
    assert service.repository.get_messages(service.session.id) == before


@pytest.mark.asyncio
async def test_client_guide_result_is_marked_not_applicable(tmp_path) -> None:
    service = build_service_for_client_guide(tmp_path)
    session = await service.create_session("Portal", DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE)
    result = await service.submit_answer(session.id, "Preciso de perguntas para o cliente.")
    assert result.quality_evaluation is not None
    assert result.quality_evaluation.applicable is False
```

Na preparação dos helpers, declarar `build_service_with_ten_answers` e `build_service_for_client_guide` no próprio módulo de teste, cada um com workflow falso que retorna `TurnResult` compatível; não usar modelo ou rede.

- [ ] **Step 2: Executar os testes para confirmar a falha**

Run: `rtk proxy uv run --extra dev pytest tests/test_discovery_workflow_service.py -q`  
Expected: FAIL porque o resultado e o serviço ainda não carregam avaliação.

- [ ] **Step 3: Calcular antes de persistir e devolver o mesmo snapshot**

Adicionar `quality_evaluation` a `TurnResult`. Injetar um `PromptQualityEvaluator` opcional em `DiscoveryWorkflowService.__init__`, inicializando `PromptQualityEvaluator()` quando não fornecido para preservar as factories atuais. Em `submit_answer`, após `workflow.run_turn`, chamar `_evaluate_quality` com `resumed.context` atualizado por `result.context`, `resumed.decisions` e `result.questions_count`; criar `result = result.model_copy(update={"quality_evaluation": evaluation})`; e passá-lo a `repository.append_turn(..., quality_evaluation=evaluation)`. Em `generate_partial_prompt`, repetir o mesmo cálculo e passá-lo a `save_generated_markdown(..., quality_evaluation=evaluation)`. O modo é obtido de `resumed.session.mode`; assim a geração direta recebe explicitamente o estado não aplicável. Não modificar `TurnWorkflow`, pois ele permanece responsável somente pela entrevista e síntese.

- [ ] **Step 4: Executar os testes de serviço**

Run: `rtk proxy uv run --extra dev pytest tests/test_discovery_workflow_service.py -q`  
Expected: PASS.

- [ ] **Step 5: Commitar a integração do caso de uso**

```bash
rtk git add src/boostprompt/models/schemas.py src/boostprompt/services/discovery_workflow.py tests/test_discovery_workflow_service.py
rtk git commit -m "feat: evaluate prompt quality after discovery turns"
```

### Task 4: Construir o widget e o layout responsivo do painel

**Files:**
- Create: `src/boostprompt/cli/prompt_quality_panel.py`
- Modify: `src/boostprompt/cli/tui_main.py`
- Modify: `tests/test_tui.py`

**Interfaces:**
- Consumes: `PromptQualityEvaluation` de `boostprompt.models.schemas`.
- Produces: `PromptQualityPanel(evaluation: PromptQualityEvaluation | None = None)` e `PromptQualityPanel.update_evaluation(evaluation: PromptQualityEvaluation | None) -> None`.
- Consumes: `ResumedSession.quality_evaluation` e `TurnResult.quality_evaluation`.

- [ ] **Step 1: Escrever testes funcionais do painel**

```python
@pytest.mark.asyncio
async def test_chat_updates_the_fixed_quality_panel_after_a_turn() -> None:
    app = BoostPromptApp(service=QualityReturningService())
    async with app.run_test() as pilot:
        await pilot.click("#new_session")
        app.screen.query_one("#session-name-input", Input).value = "API"
        await pilot.click("#create")
        app.screen.query_one("#chat-input", Input).value = "Criar API."
        await pilot.click("#send")
        assert "Cobertura do contexto" in str(app.screen.query_one("#prompt-quality-panel").render())
        assert "42/100" in str(app.screen.query_one("#prompt-quality-panel").render())


@pytest.mark.asyncio
async def test_resumed_chat_renders_the_persisted_quality_panel() -> None:
    app = BoostPromptApp(service=ResumingQualityService())
    async with app.run_test() as pilot:
        await pilot.click("#resume_session")
        app.screen.query_one("#session-code-input", Input).value = "BP-2026-050"
        await pilot.click("#resume")
        assert "Prontidão do prompt" in str(app.screen.query_one("#prompt-quality-panel").render())
```

`QualityReturningService` retorna no `TurnResult` uma avaliação aplicável com `coverage=42`, e `ResumingQualityService` constrói `ResumedSession` com a mesma avaliação. Ajustar todos os fakes existentes para que o novo campo opcional continue dispensável.

- [ ] **Step 2: Executar os testes para confirmar a falha**

Run: `rtk proxy uv run --extra dev pytest tests/test_tui.py -q`  
Expected: FAIL porque o widget e o seletor `#prompt-quality-panel` não existem.

- [ ] **Step 3: Criar o widget e conectá-lo ao chat**

Em `prompt_quality_panel.py`, implementar um `Static` com id `prompt-quality-panel`. O método `update_evaluation` deve renderizar, com texto simples e markup Rich, o título, `N/30 respostas mínimas`, os três nomes, seus valores no formato `NN/100`, suas descrições e `status_text`; se `applicable` for falso, renderizar apenas `Avaliação não aplicável` e a explicação do snapshot. Se a avaliação for `None`, construir uma visualização transitória de desenvolvimento com três valores `0/100` e `Aguardando contexto inicial.`.

Em `ChatScreen.compose`, encapsular `#chat-container` e o novo widget em `Horizontal(id="chat-layout")`; manter ações e `Footer` fora desse contêiner. Em `on_mount`, atualizar o painel com `resumed.quality_evaluation`; em `_send_message` e `_generate_partial_prompt`, atualizar o painel com `result.quality_evaluation` antes de reabilitar o input. Acrescentar CSS: `#chat-layout { height: 1fr; }`, `#chat-container { width: 1fr; }`, `#prompt-quality-panel { width: 34; min-width: 28; border: solid $primary; padding: 1; }`, e uma media query Textual para `max-width: 100` que muda `#chat-layout` para vertical, fixa o painel abaixo do chat com altura automática e não sobrepõe `#chat-input-area` ou `#chat-actions`.

- [ ] **Step 4: Executar os testes da TUI**

Run: `rtk proxy uv run --extra dev pytest tests/test_tui.py -q`  
Expected: PASS.

- [ ] **Step 5: Commitar a experiência de chat**

```bash
rtk git add src/boostprompt/cli/prompt_quality_panel.py src/boostprompt/cli/tui_main.py tests/test_tui.py
rtk git commit -m "feat: display prompt quality panel in chat"
```

### Task 5: Enriquecer o histórico de sessões e documentar a funcionalidade

**Files:**
- Modify: `src/boostprompt/cli/tui_main.py`
- Modify: `tests/test_tui.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: dicionários de `SessionService.list_sessions()` com `updated_at`, `prompt_readiness`, `quality_applicable` e `quality_evaluated_at` definidos na Task 2.
- Produces: uma linha de sessão com metadados e prontidão legíveis, preservando o item id `session-<id>` usado para abrir/excluir.

- [ ] **Step 1: Escrever o teste que falha para a lista enriquecida**

```python
@pytest.mark.asyncio
async def test_session_list_shows_update_timestamp_and_last_prompt_readiness() -> None:
    service = SessionsWithQualityService()
    app = BoostPromptApp(service=service)
    async with app.run_test() as pilot:
        await pilot.click("#list_sessions")
        rendered = str(app.screen.query_one("#sessions-list-view", ListView).children[0].render())
        assert "Prontidão: 73/100" in rendered
        assert "Atualizada em:" in rendered
```

`SessionsWithQualityService.list_sessions()` deve retornar uma sessão de desenvolvimento com `prompt_readiness=73`, `quality_applicable=True` e `updated_at=datetime(2026, 8, 10, tzinfo=UTC)`. Adicionar segundo item de roteiro para cliente e verificar que sua linha contém `Prontidão: não aplicável`.

- [ ] **Step 2: Executar o teste para confirmar a falha**

Run: `rtk proxy uv run --extra dev pytest tests/test_tui.py::test_session_list_shows_update_timestamp_and_last_prompt_readiness -q`  
Expected: FAIL porque o texto atual não contém avaliação nem data formatada.

- [ ] **Step 3: Renderizar metadados sem alterar os fluxos existentes**

Em `SessionsListScreen._load_sessions`, criar um método estático `_format_session_item(session: dict[str, Any]) -> str`. Formatar `updated_at` com `strftime("%d/%m/%Y %H:%M")` quando for `datetime`; para valores ausentes, usar `Atualizada em: não disponível`. Renderizar modo, status, `questions_count`, atualização e uma linha de prontidão: `Prontidão: {score}/100` quando `quality_applicable is True` e houver inteiro; `Prontidão: não aplicável` quando `quality_applicable is False`; caso contrário `Prontidão: sem avaliação`. Manter `id=item_id`, seleção, confirmação de exclusão e refresh intactos.

No README, acrescentar uma linha em “O que o BoostPrompt oferece” e uma subseção curta em “Fluxo de uma sessão” explicando as três métricas, que são locais/determinísticas e que o histórico mostra a última prontidão; declarar que o roteiro para cliente não recebe nota porque não executa entrevista.

- [ ] **Step 4: Executar teste focal e regressão da TUI**

Run: `rtk proxy uv run --extra dev pytest tests/test_tui.py -q`  
Expected: PASS.

- [ ] **Step 5: Commitar histórico e documentação**

```bash
rtk git add src/boostprompt/cli/tui_main.py tests/test_tui.py README.md
rtk git commit -m "feat: enrich session history with prompt readiness"
```

### Task 6: Verificação final integrada

**Files:**
- Modify: nenhum, salvo correções necessárias reveladas pelas verificações abaixo.

**Interfaces:**
- Consumes: todos os contratos e comportamentos criados nas Tasks 1–5.
- Produces: evidência de testes, lint, tipos e cobertura completa da alteração.

- [ ] **Step 1: Executar toda a suíte de testes**

Run: `rtk proxy uv run --extra dev pytest -q`  
Expected: PASS, incluindo testes novos e regressões de agentes, workflow, DuckDB e TUI.

- [ ] **Step 2: Executar cobertura**

Run: `rtk proxy uv run --extra dev pytest --cov=src/boostprompt --cov-report=term-missing -q`  
Expected: PASS; revisar linhas não cobertas nos arquivos novos e adicionar somente testes que cubram ramificações observáveis do avaliador, persistência ou painel.

- [ ] **Step 3: Executar verificações estáticas**

Run: `rtk proxy uv run --extra dev ruff check src tests && rtk proxy uv run --extra dev mypy src`  
Expected: PASS sem erros de lint ou tipagem.

- [ ] **Step 4: Conferir o diff final e a ausência de segredos/dados gerados**

Run: `rtk git diff --check && rtk git status`  
Expected: nenhum erro de whitespace; apenas arquivos fonte, testes, README e documentação deliberadamente versionados.

- [ ] **Step 5: Commitar eventuais correções de verificação**

```bash
rtk git add src tests README.md
rtk git commit -m "test: verify prompt quality experience"
```

Só executar este commit se as etapas 1–4 exigirem modificações; se não houver mudança, não criar commit vazio.
