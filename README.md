# BoostPrompt

O BoostPrompt pode ser usado de duas formas independentes:

1. **CLI/TUI local** — aplicação Textual com sessões persistidas no DuckDB, LangGraph, PydanticAI e geração de arquivo Markdown.
2. **Skills para Claude Code e Codex** — discovery conduzido diretamente pelo seu harness, com a mesma estrutura de perguntas, modos de saída e política de pesquisa.

Nos dois casos, há dois modos de saída:

- `prompt_desenvolvimento`: faz de 30 a 50 perguntas, uma por resposta, e gera um escopo completo com prompt mestre de implementação.
- `roteiro_perguntas_cliente`: recebe a demanda e gera diretamente um único Markdown com 30 a 50 perguntas para enviar ao cliente ou demandante.

## Escolha rápida

| Necessidade | Caminho recomendado |
| --- | --- |
| Quero sessões locais, retomada, resumo e arquivo `.md` persistido | CLI/TUI local |
| Quero fazer o discovery dentro de uma conversa do Claude Code | Skill Claude Code |
| Quero fazer o discovery dentro de uma conversa do Codex | Skill Codex |

---

## 1. Uso pela CLI/TUI local

### Pré-requisitos

- Python 3.11 ou superior;
- [uv](https://docs.astral.sh/uv/);
- um endpoint compatível com a API OpenAI e sua credencial, como LiteLLM,
  OpenRouter, vLLM ou a própria OpenAI.

### Instalação e configuração

Na raiz do repositório:

```bash
uv sync --extra dev
cp .env.example .env
```

A CLI carrega `.env` automaticamente sem sobrescrever variáveis já exportadas no shell.
Para usar LiteLLM, configure por exemplo:

```dotenv
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=http://localhost:4000/v1
LLM_API_KEY=sua-chave-litellm
```

Também são aceitos os nomes legados `LITELLM_BASE_URL` e `API_KEY`. Para apontar
para outro arquivo, exporte `BOOSTPROMPT_ENV_FILE=/caminho/para/arquivo.env` antes
de executar a CLI. `DUCKDB_PATH` é opcional e define o banco local.

Para usar OpenAI diretamente, configure `OPENAI_API_KEY` e, opcionalmente,
`OPENAI_MODEL` e `OPENAI_BASE_URL`.

### Iniciar a aplicação

```bash
uv run boostprompt
```

Ao iniciar, escolha **Usar LiteLLM** ou **Usar OpenAI**. A aplicação valida as
variáveis correspondentes no `.env` antes de abrir o menu, que permite criar uma
sessão, listar sessões salvas ou retomar uma sessão pelo código `BP-AAAA-NNN`.

### Fluxo de uma sessão

1. Escolha o provedor de modelo.
2. Escolha **Nova sessão**.
3. Informe um nome identificável.
4. Escolha o modo de saída.
5. Descreva a demanda inicial.
6. No modo `prompt_desenvolvimento`, responda uma pergunta por vez. A aplicação faz entre 30 e 50 perguntas, adaptadas às respostas anteriores.
7. Depois de dez respostas, selecione **Gerar prompt agora** para salvar um rascunho sem encerrar a entrevista. Continue respondendo para refiná-lo.
8. Ao final, selecione **Gerar/abrir Markdown** para visualizar e salvar o arquivo.

Cada interação é persistida automaticamente. Não há botão de salvar.

### Persistência, resumo e retomada

O banco padrão é `data/boostprompt.db`. Ele armazena:

- metadados da sessão e contador de perguntas;
- respostas do usuário e perguntas/respostas dos agentes;
- snapshots de contexto e decisões;
- referências de pesquisa;
- resumo estruturado do histórico antigo;
- Markdown final gerado.

Ao retomar uma sessão, a aplicação carrega as mensagens recentes e um resumo com objetivo, fatos confirmados, decisões, restrições, riscos e pendências. O Markdown final também fica disponível novamente para abrir ou salvar.

Ao abrir uma sessão concluída, a aplicação exibe esse resumo em bullets e oferece
**Continuar em nova entrevista**. A continuação cria outra sessão com novo código
e usa apenas o resumo estruturado da anterior, preservando o histórico original e
mantendo o contexto do modelo compacto.

O arquivo exportado fica em:

```text
output/<nome_da_sessão>_escopo.md
```

### Pesquisa DuckDuckGo por MCP

Para pesquisas técnicas, a CLI inicia sob demanda o MCP DuckDuckGo por meio de:

```bash
uvx duckduckgo-mcp-server
```

Não é necessário registrar esse MCP manualmente para usar a TUI; é necessário apenas que `uvx` esteja disponível no `PATH` e consiga obter o pacote. O cliente usa timeout e, se o servidor falhar, continua em modo degradado sem inventar fontes. Referências válidas, com URL, são persistidas e usadas na seção **Referências consultadas** do Markdown.

---

## 2. Uso somente pelas skills

As skills mantêm a mesma regra de discovery e os mesmos modos da CLI, mas funcionam inteiramente na conversa do harness. Elas não usam o banco DuckDB da TUI nem recuperam sessões locais: o histórico é o da própria conversa do Claude Code ou Codex.

### Instalação automática

O instalador copia a skill correta e configura o MCP `ddg-search` para o harness escolhido:

```bash
# Claude Code e Codex
uv run python install.py --harness both

# Somente Claude Code
uv run python install.py --harness claude

# Somente Codex
uv run python install.py --harness codex
```

O instalador exige que o executável do harness e o `uvx` estejam no `PATH`. Para instalar ou atualizar somente a skill, sem alterar a configuração MCP:

```bash
uv run python install.py --harness both --skip-mcp
```

Para conferir as ações sem modificar nada:

```bash
uv run python install.py --harness both --dry-run
```

### Onde cada skill é instalada

| Harness | Origem no repositório | Destino no usuário |
| --- | --- | --- |
| Claude Code | `.claude/skills/boostprompt/` | `~/.claude/skills/boostprompt/` |
| Codex | `.codex/skills/boostprompt/` | `~/.agents/skills/boostprompt/` |

O instalador preserva um MCP `ddg-search` que já exista. Quando precisa criá-lo, ele registra `uvx duckduckgo-mcp-server` como servidor MCP do harness.

### Usar no Claude Code

Após instalar, abra o Claude Code no projeto ou em qualquer diretório e peça explicitamente, por exemplo:

```text
Use a skill boostprompt no modo prompt_desenvolvimento.
Quero definir o escopo de um portal de fornecedores.
```

Para o fluxo inverso:

```text
Use a skill boostprompt no modo roteiro_perguntas_cliente.
Preciso de perguntas para entender uma integração de pagamentos.
```

O Claude Code usa o modelo e as credenciais já configurados no próprio harness. Não é necessário definir `OPENAI_API_KEY` para a skill, a menos que a sua configuração do Claude Code explicitamente dependa dela.

### Usar no Codex

Após instalar, inicie uma conversa no Codex e solicite a skill com a demanda e o modo:

```text
Use a skill boostprompt no modo prompt_desenvolvimento.
Quero planejar uma plataforma de análise de dados.
```

Ou, para receber somente o roteiro:

```text
Use a skill boostprompt no modo roteiro_perguntas_cliente.
Gere perguntas para levantar o escopo de um aplicativo de campo.
```

O Codex também usa o modelo, autenticação e permissões configurados no próprio harness. Quando o MCP `ddg-search` estiver disponível, a skill o usa para decisões técnicas atuais; se não estiver, continua com recomendações em modo degradado.

### Comportamento esperado das skills

- A skill pede ou reconhece `modo_saida`.
- Em `prompt_desenvolvimento`, não encerra antes de 30 respostas e encerra no máximo na pergunta 50.
- Cada pergunta apresenta contexto, alternativas, trade-offs, recomendação e forma de resposta.
- Em `roteiro_perguntas_cliente`, entrega diretamente um único Markdown com 30 a 50 perguntas, sem iniciar a entrevista interativa.
- O documento de escopo inclui decisões, plano de execução, critérios de aceite, estratégia de validação, pendências, referências e prompt mestre.

---

## Desenvolvimento e validação

```bash
uv run --extra dev pytest -q
uv run --extra dev pytest --cov=src/boostprompt --cov-report=term-missing -q
uv run --extra dev ruff check src tests
uv run --extra dev mypy src
```

Os testes evitam chamadas externas: agentes e MCP são substituídos por adaptadores controlados, preservando a validação funcional de TUI, DuckDB, resumo, LangGraph, pesquisa degradada e exportação Markdown.
