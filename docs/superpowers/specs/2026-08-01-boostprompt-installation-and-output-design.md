# BoostPrompt — Saída Única e Instalação Multiharness

## Contexto

BoostPrompt é uma skill pt-BR para Claude Code e Codex. Ela coleta contexto por meio de perguntas e, ao final, produz um documento Markdown para orientar uma necessidade de implementação, desenvolvimento ou pesquisa.

A revisão identificou que o instalador atual aponta para diretórios `commands/` inexistentes, enquanto o repositório contém skills. O README também descreve comandos legados e não explica uma instalação automática por harness.

## Objetivo

Preservar a entrevista atual e tornar sua entrega final mais acionável: um único Markdown autocontido com contexto, tarefas e validações. Tornar a instalação da skill e do MCP DuckDuckGo simples, selecionando Claude Code, Codex ou ambos.

## Decisões aprovadas

1. O documento final da skill continuará sendo um único Markdown e ganhará tarefas priorizadas, dependências, critérios de aceite e estratégia de validação.
2. Será criado um instalador Python, com `install.sh` como atalho compatível para macOS e Linux.
3. O README será reescrito para refletir a estrutura real, orientar a instalação por harness e registrar autoria.
4. A licença MIT será materializada em um arquivo `LICENSE`.
5. O instalador terá testes automatizados isolados da configuração real do usuário.

## Restrição de escopo

A entrevista de 30 a 50 perguntas permanece inalterada nesta entrega. Não será implementado um fluxo curto/adaptativo, nem uma metodologia SDD com múltiplos artefatos. O termo “plano” no Markdown final significa uma lista de tarefas de execução, não uma fase formal de SDD.

## Design da saída única

As duas cópias da skill (`.claude/skills/boostprompt/SKILL.md` e `.codex/skills/boostprompt/SKILL.md`) manterão o comportamento de entrevista, mas exigirão que o documento final contenha, além das seções já existentes:

1. **Decisões consolidadas** — decisão, justificativa e trade-off aceito.
2. **Plano de execução** — tarefas pequenas, priorizadas e independentes sempre que possível; cada uma terá objetivo, arquivos/áreas afetadas quando conhecidos, dependências e resultado esperado.
3. **Critérios de aceite** — condições observáveis para considerar a necessidade concluída.
4. **Estratégia de validação** — testes, verificações manuais, observabilidade ou critérios de pesquisa compatíveis com o tipo de necessidade.
5. **Pendências para execução** — somente lacunas que impeçam uma decisão segura.

Para uma demanda de pesquisa, o plano de execução usará hipóteses, fontes, método de comparação e sinais de validação em vez de inventar tarefas de código. Quando houver busca externa, as referências consultadas serão registradas no mesmo Markdown.

Os arquivos `references/best-pratices-mk.md` não serão alterados. Eles preservam orientações específicas de modelos e etapas para cada harness; o instalador continuará copiando-os junto com a skill.

## Design do instalador

### Interface

```text
python3 install.py --harness claude|codex|both [--skip-mcp] [--dry-run]
./install.sh --harness claude|codex|both [--skip-mcp] [--dry-run]
```

`--harness` é obrigatório para impedir instalação inesperada em ambos os ambientes. `--dry-run` apenas informa arquivos e comandos. `--skip-mcp` instala somente a skill.

### Cópia da skill

O instalador copiará a árvore da skill selecionada, incluindo `references/`:

| Harness | Origem no repositório | Destino no usuário |
| --- | --- | --- |
| Claude Code | `.claude/skills/boostprompt` | `~/.claude/skills/boostprompt` |
| Codex | `.codex/skills/boostprompt` | `~/.agents/skills/boostprompt` |

O destino do Codex segue a localização de skill de usuário documentada pelo Codex. Arquivos existentes daquele nome serão atualizados apenas após a seleção explícita do harness; arquivos de outras skills não serão tocados.

### Configuração do MCP

O MCP é opcional para a execução da skill, mas será instalado por padrão. A implementação exige `uvx` já disponível e usa `duckduckgo-mcp-server`, como a configuração MCP existente no repositório.

Para evitar editar arquivos de configuração manualmente, o instalador chamará o CLI do harness selecionado:

```text
claude mcp add --scope user ddg-search -- uvx duckduckgo-mcp-server
codex mcp add ddg-search -- uvx duckduckgo-mcp-server
```

Antes de adicionar, verificará a presença de `ddg-search` com `mcp get`. Se já existir, não o substituirá; exibirá a configuração atual e seguirá com a instalação da skill. Se `uvx` ou o CLI do harness escolhido não estiverem no `PATH`, o instalador encerrará com uma instrução objetiva de correção, sem baixar ou alterar ferramentas do sistema automaticamente.

### Segurança e portabilidade

O instalador usará somente `HOME` recebido pelo ambiente e executará comandos externos sem shell. Os testes substituirão `HOME` e `PATH` por diretórios temporários, de forma que nenhum teste modifique a configuração local de Claude, Codex ou MCP.

## README

O README terá:

- descrição clara da proposta e da saída única;
- aviso explícito de que a entrevista de 30–50 perguntas é mantida nesta versão;
- tabela de compatibilidade Claude Code/Codex;
- início rápido e referência de argumentos do instalador;
- configuração automática e manual do MCP;
- formas corretas de invocar a skill (`/boostprompt` no Claude e `$boostprompt` no Codex);
- estrutura real do repositório;
- verificação, desinstalação, limitações e roadmap;
- autoria de Airton Lira Junior e o link para o LinkedIn informado.

## Testes e validação

Será usado `unittest` da biblioteca padrão, sem nova dependência. Os testes cobrirão:

1. instalação Claude, incluindo cópia completa da skill e comando MCP esperado;
2. instalação Codex no destino de usuário oficial;
3. seleção `both`;
4. `--skip-mcp`;
5. `--dry-run`, sem cópias nem chamadas externas;
6. argumentos inválidos e dependências ausentes;
7. preservação de um MCP `ddg-search` preexistente.
8. contrato textual das skills: as duas variantes devem preservar a faixa de 30–50 perguntas e exigir plano, aceite e validação no Markdown final.

A validação final executará a suíte de testes, `bash -n install.sh`, compilação do Python e uma instalação simulada com executáveis falsos.

## Arquivos previstos

- Modificar: `.claude/skills/boostprompt/SKILL.md`
- Modificar: `.codex/skills/boostprompt/SKILL.md`
- Criar: `install.py`
- Modificar: `install.sh`
- Criar: `tests/test_install.py`
- Modificar: `README.md`
- Criar: `LICENSE`

## Fora de escopo

- Publicar um pacote npm, PyPI, plugin marketplace ou repositório remoto.
- Instalar `uv`, Python, Claude Code ou Codex automaticamente.
- Alterar configurações de MCP existentes.
- Mudar o número ou a estratégia de perguntas da entrevista.
