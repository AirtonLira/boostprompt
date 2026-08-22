# Pesquisa Exa e Garantia de Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Substituir DuckDuckGo por pesquisa Exa orientada a decisoes e entregar um unico prompt Markdown de implementacao, sem duplicar um escopo e um prompt mestre separados.

**Architecture:** Um ResearchPlannerAgent decide se e como pesquisar antes de cada pergunta; ExaResearchProvider e EvidencePolicy retornam evidencias normalizadas e auditaveis para o workflow. No fechamento, o workflow valida o Markdown, permite exatamente uma correcao pela sintese e persiste tanto o relatorio quanto a contagem real de respostas.

**Tech Stack:** Python 3.11+, Pydantic/PydanticAI, LangGraph, DuckDB, Textual, HTTPX, Exa Search API e MCP remoto Exa.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
| --- | --- |
| src/boostprompt/models/schemas.py | Contratos de pesquisa, validacao, contador de respostas e resultado de turno. |
| src/boostprompt/research/exa.py | Cliente HTTP Exa e normalizacao de falhas. |
| src/boostprompt/research/evidence.py | Deduplicacao, classificacao e limite de evidencias. |
| src/boostprompt/agents/research_planner.py | Planejamento de ate duas consultas por turno. |
| src/boostprompt/services/prompt_artifact.py | Validacao deterministica do prompt final unico. |
| src/boostprompt/graph/workflow.py | Ordem planner -> pesquisa -> entrevista e reparo unico. |
| src/boostprompt/{services/discovery_workflow.py,memory/duckdb_store.py} | Factories, estado, migracao e persistencia atomica. |
| src/boostprompt/agents/{architecture,security,delivery,synthesis}.py | Uso de evidencias, citacoes e reparo. |
| src/boostprompt/cli/{tui_main,prompt_quality_panel}.py | Limiar do rascunho e estado de validacao. |
| install.py, .env.example, README.md | Configuracao Exa do CLI e do MCP remoto. |
| .claude/skills/boostprompt/SKILL.md, .codex/skills/boostprompt/SKILL.md | Mesma politica Exa nos dois harnesses. |

### Task 1: Definir contratos tipados para evidencia, validacao e respostas efetivas

**Files:**
- Modify: src/boostprompt/models/schemas.py
- Modify: tests/test_schemas.py
- Create: tests/test_prompt_artifact.py

- [ ] **Step 1: Escrever os testes de contrato que devem falhar**

~~~~python
from boostprompt.models.schemas import (
    PromptValidationReport,
    ResearchPlan,
    ResearchRequest,
    ResearchTopic,
)


def test_research_plan_limits_each_turn_to_two_queries() -> None:
    plan = ResearchPlan(
        requests=[
            ResearchRequest(query="FastAPI security", topic=ResearchTopic.TECHNICAL),
            ResearchRequest(query="OAuth 2.1", topic=ResearchTopic.SECURITY),
        ]
    )
    assert len(plan.requests) == 2


def test_research_plan_rejects_three_queries() -> None:
    with pytest.raises(ValidationError):
        ResearchPlan(requests=[ResearchRequest(query=str(item) * 3) for item in range(3)])


def test_validation_report_serializes_a_repairable_failure() -> None:
    report = PromptValidationReport(
        valid=False,
        missing_sections=["## 17. Plano de execução"],
        missing_prompt_topics=["segurança"],
    )
    assert report.repaired is False
~~~~

- [ ] **Step 2: Executar os testes para confirmar a falha**

Run: uv run --extra dev pytest tests/test_schemas.py tests/test_prompt_artifact.py -q
Expected: FAIL porque os contratos ainda nao existem.

- [ ] **Step 3: Adicionar os modelos compartilhados**

Em schemas.py, importar uuid4 e declarar antes de ResearchFinding:

~~~~python
class ResearchTopic(StrEnum):
    TECHNICAL = "technical"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    MARKET = "market"
    NEWS = "news"


class SourceKind(StrEnum):
    OFFICIAL = "official"
    PRIMARY = "primary"
    REPUTABLE = "reputable"
    COMMUNITY = "community"
    UNKNOWN = "unknown"


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    decision_context: str = Field(default="discovery", min_length=1)
    topic: ResearchTopic = ResearchTopic.TECHNICAL
    freshness_days: int | None = Field(default=None, ge=1, le=365)
    include_domains: list[str] = Field(default_factory=list, max_length=4)
    max_results: int = Field(default=5, ge=1, le=10)


class ResearchPlan(BaseModel):
    requests: list[ResearchRequest] = Field(default_factory=list, max_length=2)
    reason: str = "Nenhuma pesquisa externa e necessaria neste turno."


class PromptValidationReport(BaseModel):
    valid: bool
    missing_sections: list[str] = Field(default_factory=list)
    missing_prompt_topics: list[str] = Field(default_factory=list)
    invalid_reference_urls: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    repaired: bool = False
~~~~

Estender ResearchFinding com source_id, query, published_at, source_kind e relevance_score. Estender Session e TurnResult com answered_questions_count; adicionar validation_report opcional a TurnResult e PromptQualityEvaluation. Defaults devem manter fakes e bancos existentes validos.

- [ ] **Step 4: Reexecutar os contratos**

Run: uv run --extra dev pytest tests/test_schemas.py tests/test_prompt_artifact.py -q
Expected: PASS.

- [ ] **Step 5: Commitar**

~~~~bash
git add src/boostprompt/models/schemas.py tests/test_schemas.py tests/test_prompt_artifact.py
git commit -m "feat: add research and prompt assurance contracts"
~~~~

### Task 2: Implementar Exa e a politica deterministica de evidencias

**Files:**
- Modify: pyproject.toml
- Modify: uv.lock
- Create: src/boostprompt/research/exa.py
- Create: src/boostprompt/research/evidence.py
- Modify: src/boostprompt/research/__init__.py
- Create: tests/test_exa_research.py
- Create: tests/test_evidence_policy.py

- [ ] **Step 1: Escrever testes de normalizacao, degradacao e deduplicacao**

~~~~python
@pytest.mark.asyncio
async def test_exa_provider_normalizes_dates_highlights_and_scores() -> None:
    provider = ExaResearchProvider(client=StaticExaClient())
    findings = await provider.search(
        ResearchRequest(
            query="FastAPI releases",
            freshness_days=30,
            include_domains=["fastapi.tiangolo.com"],
        )
    )
    assert findings[0].url == "https://fastapi.tiangolo.com/release-notes/"
    assert findings[0].published_at == datetime(2026, 8, 1, tzinfo=UTC)
    assert findings[0].source_kind is SourceKind.OFFICIAL


@pytest.mark.asyncio
async def test_exa_provider_hides_authentication_details_in_degraded_error() -> None:
    provider = ExaResearchProvider(client=FailingExaClient(http_status=401))
    with pytest.raises(ResearchUnavailableError, match="Exa") as error:
        await provider.search(ResearchRequest(query="OAuth"))
    assert "api-key" not in str(error.value).casefold()


def test_evidence_policy_keeps_the_best_fresh_finding_per_url() -> None:
    evidence = EvidencePolicy().select([old_duplicate, official_fresh_duplicate, other_source])
    assert [item.source_id for item in evidence] == [
        official_fresh_duplicate.source_id,
        other_source.source_id,
    ]
~~~~

StaticExaClient devolve results com publishedDate, highlights e highlightScores. FailingExaClient levanta httpx.HTTPStatusError em memoria. Nenhum teste usa a rede.

Definir os dois doubles no proprio modulo de teste: StaticExaClient.search retorna um dicionario com uma chave results e um unico resultado com url, title, publishedDate, highlights e highlightScores. FailingExaClient.search constroi um httpx.Request para https://api.exa.ai/search e levanta httpx.HTTPStatusError("erro", request=request, response=httpx.Response(http_status, request=request)). Os objetos old_duplicate, official_fresh_duplicate e other_source sao ResearchFinding completos criados no modulo, com URLs iguais para os dois primeiros e datas distintas.

- [ ] **Step 2: Confirmar a falha**

Run: uv run --extra dev pytest tests/test_exa_research.py tests/test_evidence_policy.py -q
Expected: FAIL porque ExaResearchProvider e EvidencePolicy ainda nao existem.

- [ ] **Step 3: Declarar HTTPX e criar o adaptador**

Adicionar httpx>=0.27.0 a dependencies e rodar uv lock. Em exa.py, o cliente real faz POST para https://api.exa.ai/search com x-api-key somente no header:

~~~~python
payload: dict[str, Any] = {
    "query": request.query,
    "numResults": request.max_results,
    "includeDomains": request.include_domains or None,
    "contents": {
        "highlights": {"maxCharacters": 1000},
        "text": {"maxCharacters": 2000},
    },
}
if request.freshness_days is not None:
    payload["startPublishedDate"] = (
        datetime.now(UTC) - timedelta(days=request.freshness_days)
    ).isoformat()
~~~~

EXA_API_KEY ausente, timeout, 401, 429, 5xx e resposta sem URL levantam apenas ResearchUnavailableError em pt-BR, sem token ou corpo HTTP. Converter publishedDate para UTC; usar primeiro highlight, depois text, para excerpt; usar primeiro highlightScore para relevance_score. Fonte e OFFICIAL somente se o host estiver em include_domains; .gov e .edu sao PRIMARY; os demais sao UNKNOWN.

EvidencePolicy remove fragmento e slash final para comparar URLs, conserva um resultado por URL, ordena OFFICIAL, PRIMARY, data mais recente e score, e limita a oito fontes. Exportar os novos tipos no __init__.py e remover exportacao DuckDuckGo depois que nenhum consumidor restar.

- [ ] **Step 4: Executar unidades da pesquisa**

Run: uv run --extra dev pytest tests/test_exa_research.py tests/test_evidence_policy.py -q
Expected: PASS.

- [ ] **Step 5: Commitar**

~~~~bash
git add pyproject.toml uv.lock src/boostprompt/research tests/test_exa_research.py tests/test_evidence_policy.py
git commit -m "feat: add Exa research provider and evidence policy"
~~~~

### Task 3: Planejar pesquisa antes da proxima pergunta e propagar evidencias no grafo

**Files:**
- Create: src/boostprompt/agents/research_planner.py
- Modify: src/boostprompt/agents/__init__.py
- Modify: src/boostprompt/graph/workflow.py
- Modify: src/boostprompt/services/discovery_workflow.py
- Modify: tests/test_workflow.py
- Modify: tests/test_llm_configuration.py
- Create: tests/test_research_planner.py

- [ ] **Step 1: Caracterizar a ordem planner -> pesquisa -> discovery**

~~~~python
@pytest.mark.asyncio
async def test_workflow_researches_planned_decision_before_generating_question() -> None:
    calls: list[str] = []
    workflow = TurnWorkflow(
        agents=WorkflowAgents(
            research_planner=FakePlanner([ResearchRequest(query="FastAPI security")], calls),
            discovery=CapturingDiscovery(calls),
            architecture=FakeFinalAgent(),
            security=FakeFinalAgent(),
            delivery=FakeFinalAgent(),
            synthesis=FakeFinalAgent("# Escopo"),
        ),
        research_provider=CapturingResearchProvider(calls),
    )
    await workflow.run_turn(turn_state(questions_count=1))
    assert calls == ["plan", "search:FastAPI security", "discovery"]


@pytest.mark.asyncio
async def test_workflow_continues_when_one_planned_search_is_unavailable() -> None:
    result = await workflow_with_unavailable_research().run_turn(turn_state(questions_count=1))
    assert result.awaiting_user_answer is True
    assert result.research_degraded is True
~~~~

Definir FakePlanner.plan para acrescentar plan em calls e retornar ResearchPlan(requests=requests, reason="Teste"). CapturingResearchProvider.search acrescenta search:<request.query> e devolve uma lista com um ResearchFinding. CapturingDiscovery.ask_next acrescenta discovery e devolve a DiscoveryResponse que a fixture question() ja usa. A variante indisponivel levanta ResearchUnavailableError no provider, mantendo o mesmo discovery.

- [ ] **Step 2: Rodar para verificar a falha**

Run: uv run --extra dev pytest tests/test_research_planner.py tests/test_workflow.py -q
Expected: FAIL porque WorkflowAgents nao recebe research_planner e o grafo ainda inicia em research.

- [ ] **Step 3: Criar o planner e reorganizar o LangGraph**

ResearchPlannerAgent.plan recebe context, ultimas mensagens e contador. Seu system prompt permite no maximo duas consultas, exige recencia apenas para fatos mutaveis e proibe busca para prioridades, orcamento e regras internas que o usuario precisa responder.

Em workflow.py, substituir research_query por research_plan em TurnState e inserir research_plan entre START e research. O protocolo passa a ser search(request: ResearchRequest). Executar requests sequencialmente, conservar referencias persistidas, aplicar EvidencePolicy e marcar research_degraded se uma falhar, sem descartar as demais. Renderizar fontes assim:

~~~~text
- [<source_id>] <title> (<published_at ou "data não informada">)
  <excerpt>
  URL: <url>
  Fundamenta: <decision_context>
~~~~

O modo roteiro_perguntas_cliente tambem passa pelo planner. Em DiscoveryWorkflowService.create_default, instanciar planner com o mesmo modelo e ExaResearchProvider; remover technical_terms e _research_query. Ajustar fakes e factory sem rede.

- [ ] **Step 4: Rodar regressao do grafo**

Run: uv run --extra dev pytest tests/test_research_planner.py tests/test_workflow.py tests/test_llm_configuration.py -q
Expected: PASS.

- [ ] **Step 5: Commitar**

~~~~bash
git add src/boostprompt/agents src/boostprompt/graph/workflow.py src/boostprompt/services/discovery_workflow.py tests/test_research_planner.py tests/test_workflow.py tests/test_llm_configuration.py
git commit -m "feat: plan Exa research before discovery questions"
~~~~

### Task 4: Persistir evidencias enriquecidas e respostas confirmadas sem quebrar bancos antigos

**Files:**
- Modify: src/boostprompt/memory/duckdb_store.py
- Modify: src/boostprompt/services/discovery_workflow.py
- Modify: tests/test_duckdb_store.py
- Modify: tests/test_discovery_workflow_service.py

- [ ] **Step 1: Escrever casos de migracao e limiar de resposta**

~~~~python
def test_legacy_database_loads_missing_research_fields_and_answer_counter(tmp_path) -> None:
    legacy = create_legacy_store(tmp_path / "legacy.db")
    resumed = DuckDBStore(legacy.db_path).load_for_resume(legacy.session_id)
    assert resumed.session.answered_questions_count == 0


def test_research_finding_round_trips_with_stable_id_and_date(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("API")
    store.save_research_findings(session.id, [finding_with_metadata])
    restored = store.get_research_findings(session.id)[0]
    assert restored["source_id"] == finding_with_metadata.source_id
    assert restored["source_kind"] == "official"


@pytest.mark.asyncio
async def test_partial_prompt_requires_ten_confirmed_answers(tmp_path) -> None:
    service = service_with_answer_counter(tmp_path, questions=10, answers=9)
    with pytest.raises(ValueError, match="10 respostas"):
        await service.generate_partial_prompt(service.session.id)
~~~~

create_legacy_store deve criar um DuckDB com as tabelas sessions, context_snapshots e final_documents no schema anterior, inserir uma sessao e um snapshot, e devolver um objeto simples com db_path e session_id. finding_with_metadata e um ResearchFinding construído no modulo com source_id="source-1", published_at em UTC, source_kind=SourceKind.OFFICIAL e relevance_score=0.9. service_with_answer_counter deve instanciar DiscoveryWorkflowService com o FakeWorkflow e FakeSummaryAgent ja usados neste arquivo, criar a sessao e ajustar sessions.questions_count e sessions.answered_questions_count pela API do store antes de devolver o servico e a sessao.

- [ ] **Step 2: Confirmar que a persistencia ainda falha**

Run: uv run --extra dev pytest tests/test_duckdb_store.py tests/test_discovery_workflow_service.py -q
Expected: FAIL porque answered_questions_count e campos Exa nao sao gravados.

- [ ] **Step 3: Fazer migracao aditiva e atualizacao atomica**

Acrescentar answered_questions_count INTEGER NOT NULL DEFAULT 0 em sessions; published_at TIMESTAMP, source_kind TEXT NOT NULL DEFAULT 'unknown' e relevance_score DOUBLE em research_findings; validation_report TEXT em session_quality_evaluations. Usar somente ALTER TABLE ... ADD COLUMN IF NOT EXISTS em _migrate_existing_schema.

append_turn recebe answered_questions_count e o grava na transacao das mensagens, contexto, Markdown e qualidade. save_research_findings recebe Sequence[ResearchFinding], usa finding.source_id como id e persiste os campos. get_research_findings seleciona id AS source_id.

Em submit_answer, calcular e persistir:

~~~~python
answered_questions_count = resumed.session.answered_questions_count + int(
    resumed.session.questions_count > 0
)
~~~~

generate_partial_prompt compara answered_questions_count com MINIMUM_PARTIAL_PROMPT_ANSWERS = 10. A descricao inicial nao incrementa esse numero.

- [ ] **Step 4: Executar regressao de armazenamento**

Run: uv run --extra dev pytest tests/test_duckdb_store.py tests/test_discovery_workflow_service.py tests/test_memory_agent.py -q
Expected: PASS.

- [ ] **Step 5: Commitar**

~~~~bash
git add src/boostprompt/memory/duckdb_store.py src/boostprompt/services/discovery_workflow.py tests/test_duckdb_store.py tests/test_discovery_workflow_service.py
git commit -m "feat: persist Exa evidence and confirmed discovery answers"
~~~~

### Task 5: Gerar, validar e reparar o prompt final unico

**Files:**
- Create: src/boostprompt/services/prompt_artifact.py
- Modify: src/boostprompt/graph/workflow.py
- Modify: src/boostprompt/agents/synthesis.py
- Modify: src/boostprompt/agents/architecture.py
- Modify: src/boostprompt/agents/security.py
- Modify: src/boostprompt/agents/delivery.py
- Modify: tests/test_prompt_artifact.py
- Modify: tests/test_workflow.py
- Modify: tests/test_final_agents.py

- [ ] **Step 1: Escrever testes do validador e limite de reparo**

~~~~python
def test_validator_reports_absent_sections_and_master_prompt_topics() -> None:
    report = PromptArtifactValidator().validate(
        "# Prompt Mestre de Implementação - Portal\n\n## 1. Contexto e objetivo\nTexto"
    )
    assert "## 17. Plano de execução" in report.missing_sections
    assert "segurança" in report.missing_prompt_topics
    assert report.valid is False


@pytest.mark.asyncio
async def test_workflow_repairs_an_invalid_document_once() -> None:
    synthesis = RepairingSynthesis(first="# Escopo da Solução", repaired="# Ainda incompleto")
    result = await workflow_with_validator(synthesis).run_turn(turn_state(questions_count=30))
    assert synthesis.repair_calls == 1
    assert result.validation_report is not None
    assert result.validation_report.valid is False
    assert result.validation_report.repaired is True
~~~~

RepairingSynthesis implementa execute e repair, incrementa repair_calls e devolve primeiro ou repaired em final_markdown. workflow_with_validator constroi WorkflowAgents com os fakes existentes e document_validator=PromptArtifactValidator(); o documento de teste omite uma secao para garantir a segunda validacao invalida.

- [ ] **Step 2: Executar para provar a falha**

Run: uv run --extra dev pytest tests/test_prompt_artifact.py tests/test_workflow.py tests/test_final_agents.py -q
Expected: FAIL porque synthesis vai direto a complete.

- [ ] **Step 3: Implementar validacao e reparo unico**

PromptArtifactValidator declara o titulo # Prompt Mestre de Implementação e os 22 cabecalhos canonicos como constantes e localiza cada um por regex multiline. Um cabecalho inexistente ou sem conteudo ate o proximo ## e uma lacuna. Nas secoes 16 a 22, corpo vazio tambem invalida. Na secao 21, validar todas as URLs encontradas com urllib.parse.urlparse. Na secao 22, normalizar caixa e acentos e exigir os grupos: objetivo/escopo, restricao, requisito funcional, requisito nao funcional, arquitetura, dados/integracao, seguranca, teste, observabilidade, entrega e criterio de aceite. Rejeitar os titulos legados # Escopo da Solução e ## 22. Prompt mestre para implementação e qualquer instrucao que dependa de outro documento.

No grafo, inserir validate_document e repair_document apos synthesis. validate_document escreve validation_report; a rota vai para complete se valido ou se repair_attempted ja existir, e vai para repair_document somente uma vez. repair_document chama SynthesisAgent.repair(markdown, report, state), troca final_markdown e marca repair_attempted=True antes de validar outra vez.

SynthesisAgent.repair recebe o Markdown e as listas do relatorio, preserva fatos e fontes e retorna SynthesisResponse. O prompt normal exige o titulo e os 22 cabecalhos do prompt unico, citacoes [source_id], linhas de referencia com URL, data de consulta e decisao sustentada e instrucao direta ao agente na secao 22 sem repetir as secoes anteriores. Passar research_context tambem para arquitetura, seguranca e delivery.

DiscoveryWorkflowService marca completed somente se validation_report.valid; caso contrario, needs_review. O rascunho antecipado permanece in_progress.

- [ ] **Step 4: Rodar validacao e agentes finais**

Run: uv run --extra dev pytest tests/test_prompt_artifact.py tests/test_workflow.py tests/test_final_agents.py -q
Expected: PASS.

- [ ] **Step 5: Commitar**

~~~~bash
git add src/boostprompt/services/prompt_artifact.py src/boostprompt/graph/workflow.py src/boostprompt/agents tests/test_prompt_artifact.py tests/test_workflow.py tests/test_final_agents.py
git commit -m "feat: validate and repair generated implementation prompts"
~~~~

### Task 6: Mostrar validacao e habilitar rascunho somente na decima resposta

**Files:**
- Modify: src/boostprompt/cli/tui_main.py
- Modify: src/boostprompt/cli/prompt_quality_panel.py
- Modify: tests/test_tui.py

- [ ] **Step 1: Escrever as assercoes da interface**

~~~~python
@pytest.mark.asyncio
async def test_partial_button_stays_disabled_after_nine_answers() -> None:
    app = BoostPromptApp(service=NineAnswerService())
    async with app.run_test() as pilot:
        await open_chat_and_submit_initial_demand(app, pilot)
        assert app.screen.query_one("#generate-partial", Button).disabled is True


@pytest.mark.asyncio
async def test_quality_panel_exposes_an_invalid_final_document() -> None:
    app = BoostPromptApp(service=NeedsReviewService())
    async with app.run_test() as pilot:
        await open_chat_and_submit_initial_demand(app, pilot)
        assert "Documento requer revisão" in str(
            app.screen.query_one("#prompt-quality-panel").render()
        )
~~~~

NineAnswerService e NeedsReviewService devem herdar os fakes de SessionService ja presentes no modulo e devolver TurnResult com answered_questions_count=9 e validation_report invalido, respectivamente. open_chat_and_submit_initial_demand deve clicar em new_session, preencher session-name-input, clicar create, preencher chat-input e clicar send; mantê-lo como helper no mesmo modulo de teste para as duas assercoes.

- [ ] **Step 2: Confirmar que a UI usa o contador errado**

Run: uv run --extra dev pytest tests/test_tui.py -q
Expected: FAIL porque o botao ainda usa questions_count e o painel nao tem validation_report.

- [ ] **Step 3: Atualizar ChatScreen e PromptQualityPanel**

Trocar condicoes de #generate-partial para self.session.answered_questions_count >= 10. Apos cada TurnResult, atualizar esse campo no model_copy da sessao; na retomada, usar o valor persistido.

No painel, renderizar:
- Validacao do documento: aguardando geração. quando nao houver relatorio;
- Documento validado. quando valid for true;
- Documento requer revisão: <primeira lacuna>. quando valid for false.

Manter as tres metricas. Quando status for needs_review, notificar que o arquivo nao foi concluido em vez de apresentá-lo como resultado final.

- [ ] **Step 4: Rodar testes Textual**

Run: uv run --extra dev pytest tests/test_tui.py -q
Expected: PASS.

- [ ] **Step 5: Commitar**

~~~~bash
git add src/boostprompt/cli/tui_main.py src/boostprompt/cli/prompt_quality_panel.py tests/test_tui.py
git commit -m "feat: show prompt validation and count confirmed answers"
~~~~

### Task 7: Atualizar MCP Exa, skills e documentacao

**Files:**
- Modify: install.py
- Modify: tests/test_install.py
- Modify: tests/test_skill_contract.py
- Modify: .claude/skills/boostprompt/SKILL.md
- Modify: .codex/skills/boostprompt/SKILL.md
- Modify: .env.example
- Modify: README.md

- [ ] **Step 1: Escrever contratos de instalacao e skills**

~~~~python
def test_installs_claude_skill_and_adds_remote_exa_mcp(self) -> None:
    result = self.run_installer("--harness", "claude")
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertIn("claude mcp get exa", self.commands())
    self.assertIn(
        "claude mcp add --scope user --transport http exa https://mcp.exa.ai/mcp",
        self.commands(),
    )


def test_installs_codex_skill_and_adds_remote_exa_mcp(self) -> None:
    result = self.run_installer("--harness", "codex")
    self.assertIn("codex mcp add exa --url https://mcp.exa.ai/mcp", self.commands())
~~~~

Em test_skill_contract.py, exigir web_search_exa, web_fetch_exa, modo degradado, fonte primária, qual decisão a referência fundamentou e # Prompt Mestre de Implementação nas duas skills.

- [ ] **Step 2: Executar para confirmar a falha**

Run: uv run --extra dev pytest tests/test_install.py tests/test_skill_contract.py -q
Expected: FAIL porque ainda ha ddg-search e DuckDuckGo.

- [ ] **Step 3: Alterar configuracao e instrucoes**

Em install.py, usar SERVER_NAME = "exa" e SERVER_URL = "https://mcp.exa.ai/mcp". Para Claude, executar claude mcp add --scope user --transport http exa https://mcp.exa.ai/mcp; para Codex, codex mcp add exa --url https://mcp.exa.ai/mcp. Remover require_command("uvx"), preservar quaisquer configuracoes ddg-search ja pertencentes ao usuario.

Nas duas skills, usar web_search_exa antes de perguntas tecnicas atuais e web_fetch_exa quando o trecho nao bastar. Priorizar fonte oficial, primaria e recente; gravar URL, data e decisao sustentada; declarar modo degradado se MCP estiver indisponivel. No modo prompt_desenvolvimento, instruir que a resposta final e somente um # Prompt Mestre de Implementação autocontido, com 22 secoes e sem duplicar um escopo anterior. Preservar ambos os modos e os limites de 30 a 50 perguntas.

Adicionar EXA_API_KEY= a .env.example. README descreve chave para CLI e MCP remoto autenticado pelo harness. Remover uvx como pre-requisito de pesquisa.

- [ ] **Step 4: Executar os contratos**

Run: uv run --extra dev pytest tests/test_install.py tests/test_skill_contract.py -q
Expected: PASS.

- [ ] **Step 5: Commitar**

~~~~bash
git add install.py tests/test_install.py tests/test_skill_contract.py .claude/skills/boostprompt/SKILL.md .codex/skills/boostprompt/SKILL.md .env.example README.md
git commit -m "feat: configure Exa MCP for BoostPrompt skills"
~~~~

### Task 8: Executar a regressao completa e encerrar com evidencia

**Files:**
- Modify only files required to correct a regression proven by this task.

- [ ] **Step 1: Executar a suite completa**

Run: uv run --extra dev pytest -q
Expected: PASS, incluindo entrevista de 30 a 50 perguntas, roteiro de cliente, memoria, Exa falso, reparo unico, DuckDB antigo, TUI e instalador.

- [ ] **Step 2: Executar cobertura, lint e tipagem**

Run: uv run --extra dev pytest --cov=src/boostprompt --cov-report=term-missing -q && uv run --extra dev ruff check . && uv run --extra dev mypy src
Expected: todos os testes passam, Ruff nao encontra os imports de install.py e Mypy termina sem erros.

- [ ] **Step 3: Confirmar que DuckDuckGo nao e mais operacional**

Run: rg -n "duckduckgo|ddg-search|duckduckgo-mcp-server" README.md install.py .claude .codex src tests
Expected: nenhum resultado operacional; testes de migracao podem mencionar dados legados explicitamente.

- [ ] **Step 4: Verificar o diff**

Run: git diff HEAD~7..HEAD --check && git status --short
Expected: sem whitespace errors e worktree limpo depois dos commits de cada tarefa.
