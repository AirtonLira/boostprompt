# BoostPrompt

BoostPrompt é uma skill em português do Brasil para transformar uma necessidade de implementação, desenvolvimento ou pesquisa em um único Markdown acionável. Ela permite escolher entre conduzir um discovery para gerar um prompt de desenvolvimento ou receber um roteiro de perguntas para alinhar o contexto com o cliente ou demandante.

## O que é

Em vez de espalhar decisões entre vários arquivos, o BoostPrompt organiza o resultado em uma única entrega. O usuário escolhe o `modo_saida` mais adequado:

- `prompt_desenvolvimento`: conduz uma entrevista de 30 a 50 perguntas e gera escopo, decisões, tarefas, critérios de aceite, estratégia de validação e prompt mestre para implementação.
- `roteiro_perguntas_cliente`: gera um único Markdown com 30 a 50 perguntas contextualizadas que devem ser feitas ao cliente ou demandante antes do desenvolvimento.

Nos dois modos, a saída fica consolidada em um único documento Markdown.

## O que você recebe ao final

### `prompt_desenvolvimento`

O Markdown final inclui:

- contexto, objetivo, público, restrições e requisitos;
- arquitetura, stack, dados, segurança e operação;
- decisões consolidadas com justificativas e trade-offs;
- plano de execução priorizado, com dependências, entregáveis e validação;
- critérios de aceite e pendências que realmente bloqueiam a execução;
- estratégia de testes, validações manuais, métricas ou avaliação de pesquisa;
- referências consultadas, quando houver busca externa;
- prompt mestre para implementação, baseado no próprio documento.

### `roteiro_perguntas_cliente`

O Markdown final inclui:

- a demanda informada, sem premissas inventadas;
- instruções breves para usar o roteiro;
- de 30 a 50 perguntas adaptadas à demanda;
- contexto, alternativas e trade-offs quando ajudarem a reduzir ambiguidades;
- orientação clara sobre como o cliente ou demandante deve responder.

## Compatibilidade

| Harness | Instalação da skill | Planejamento | Execução |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/boostprompt` | Opus | Sonnet |
| Codex | `~/.agents/skills/boostprompt` | GPT 5.6 Sol | GPT 5.6 Terra |

As orientações de modelo são mantidas nas referências específicas de cada harness e são copiadas sem alteração pelo instalador.

## Instalação rápida

Pré-requisitos:

- Python 3;
- o CLI do harness escolhido (`claude` e/ou `codex`);
- `uvx`, caso queira instalar também o MCP DuckDuckGo.

Na raiz deste repositório, escolha o harness:

```bash
python3 install.py --harness claude
python3 install.py --harness codex
python3 install.py --harness both
```

Também há um atalho compatível com macOS e Linux:

```bash
./install.sh --harness codex --skip-mcp
./install.sh --harness both --dry-run
```

O instalador copia somente a skill `boostprompt` do harness selecionado. Por padrão, ele também configura o MCP DuckDuckGo; use `--skip-mcp` para instalar apenas a skill.

## Opções do instalador

| Opção | Efeito |
| --- | --- |
| `--harness claude` | Instala somente a skill para Claude Code. |
| `--harness codex` | Instala somente a skill para Codex. |
| `--harness both` | Instala as duas variantes. |
| `--skip-mcp` | Não configura o servidor de busca. |
| `--dry-run` | Mostra cópias e comandos previstos sem escrever arquivos ou chamar CLIs. |

Se `uvx`, `claude` ou `codex` não estiverem disponíveis para a opção escolhida, o instalador encerra com uma mensagem de correção. Ele não baixa nem altera ferramentas do sistema automaticamente.

## MCP DuckDuckGo

O MCP é opcional: sem ele, o BoostPrompt continua funcionando em modo degradado, com boas práticas gerais. Com ele, a skill pode pesquisar alternativas atuais e fundamentar decisões técnicas.

O instalador usa [`uvx`](https://docs.astral.sh/uv/guides/tools/) para executar `duckduckgo-mcp-server` e chama o CLI nativo do harness. Antes, verifica se `ddg-search` já existe e nunca o substitui.

```bash
# Claude Code
claude mcp get ddg-search
claude mcp add --scope user ddg-search -- uvx duckduckgo-mcp-server

# Codex
codex mcp get ddg-search
codex mcp add ddg-search -- uvx duckduckgo-mcp-server
```

Para instalar o MCP manualmente, execute apenas o comando `mcp add` correspondente. O arquivo [`.mcp.json`](.mcp.json) permanece como referência de configuração por projeto.

## Como usar

Após a instalação, abra uma nova sessão do harness para garantir que a lista de skills seja atualizada.

### Claude Code

```text
/boostprompt "Quero criar uma plataforma de IA para análise de contratos"
```

Para obter o roteiro de perguntas para o cliente, informe o modo junto da demanda:

```text
/boostprompt "roteiro_perguntas_cliente: preciso criar uma plataforma de IA para análise de contratos"
```

### Codex

```text
$boostprompt Quero criar uma plataforma de IA para análise de contratos
```

Para obter o roteiro de perguntas para o cliente:

```text
$boostprompt roteiro_perguntas_cliente: preciso criar uma plataforma de IA para análise de contratos
```

A skill também pode ser selecionada pelo menu de skills quando a necessidade descrita corresponder ao seu objetivo. Caso o modo não seja informado no início, a skill pedirá a escolha entre `prompt_desenvolvimento` e `roteiro_perguntas_cliente`.

## Estrutura do repositório

```text
BoostPrompt/
├── .claude/skills/boostprompt/       # Skill e referência do Claude Code
├── .codex/skills/boostprompt/        # Skill e referência do Codex
├── .mcp.json                         # Exemplo de MCP DuckDuckGo por projeto
├── install.py                        # Instalador Python multiharness
├── install.sh                        # Atalho para o instalador Python
├── tests/                            # Testes isolados do instalador e das skills
├── README.md
└── LICENSE
```

## Verificação e desinstalação

Confira a configuração MCP:

```bash
claude mcp get ddg-search
codex mcp get ddg-search
```

Para remover a skill, exclua somente o diretório correspondente:

```bash
rm -rf "$HOME/.claude/skills/boostprompt"
rm -rf "$HOME/.agents/skills/boostprompt"
```

Para remover o MCP que você instalou para este projeto:

```bash
claude mcp remove --scope user ddg-search
codex mcp remove ddg-search
```

Remova o MCP apenas se ele não for usado por outra configuração sua.

## Limitações e escopo

- No modo `prompt_desenvolvimento`, a entrevista continua entre 30 e 50 perguntas respondidas.
- No modo `roteiro_perguntas_cliente`, a saída contém entre 30 e 50 perguntas para o cliente ou demandante; não há entrevista interativa nesse modo.
- A qualidade das recomendações externas depende do MCP de busca estar disponível.
- O instalador não substitui uma configuração existente de `ddg-search`.
- O projeto não publica pacote npm, PyPI ou marketplace nesta etapa.

## Roadmap

- Tornar o número de perguntas adaptativo para reduzir ainda mais o custo de tokens.
- Adicionar outros provedores de busca.
- Oferecer perfis especializados por domínio.
- Empacotar a distribuição para marketplaces quando houver um canal de publicação definido.

## Autor

Criado por [Airton Lira Junior](https://www.linkedin.com/in/airton-de-souza-lira-junior-6b81a661/).

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
