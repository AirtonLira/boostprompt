# Final fix report — prompt quality panel

## Status

Os três findings **Important** da revisão final foram corrigidos por TDD. Os findings
**Minor** foram relidos e mantidos sem alteração, conforme o escopo desta onda.

## Findings e correções

### Important 1 — nove grupos de cobertura

- Causa: o avaliador separava `objetivo` de problema/necessidade, unia requisitos
  funcionais e não funcionais e omitia campos aprovados de dados, arquitetura e
  restrições/riscos.
- Correção: `_COVERAGE_GROUPS` agora reproduz exatamente os nove grupos da especificação.
- Proteção: vetores independentes comprovam que todos os campos de cada grupo contam uma
  única vez (`11`) e que um campo de cada um dos nove grupos produz cobertura `100`.
- Fórmula preservada: `round(grupos_cobertos / 9 * 100)`.

### Important 2 — clareza por item

- Causa: listas presentes contavam como um único booleano tanto nas evidências quanto em
  `pendencias` e `riscos`.
- Correção: `_item_count` soma cada item não vazio dos campos de evidência e incerteza;
  escalares não vazios continuam contando uma vez. Evidências permanecem limitadas a dez.
- Proteção: teste exato com sete evidências e quatro incertezas espera `39`; outro vetor
  comprova que doze perfis são limitados a dez evidências e produzem `100`.
- Fórmula preservada: `round(100 * evidencias / (10 + 2 * incertezas))`, limitada a 0–100.
- Contrato não aplicável preservado e agora protegido integralmente: três scores `None` e
  texto exato `Avaliação não aplicável ao roteiro gerado diretamente.`.

### Important 3 — layout estreito

- Causa: `max-height: 4` reduzia a região útil do painel a zero linhas; apenas remover o
  limite fazia o `chat-container` encolher e seus controles extrapolarem sobre o painel em
  `80×24`.
- Correção: removido `max-height: 4`; o breakpoint `<=100` continua vertical, o chat mantém
  altura mínima suficiente para o input e o contêiner do layout ganha rolagem vertical quando
  chat e painel completo não cabem simultaneamente.
- Proteção: teste Textual real em `80×24` comprova classe estreita, rolagem disponível,
  nove linhas úteis no painel e geometria sem sobreposição entre input, painel e ações.

## Findings Minor avaliados

- Seleção do mais recente entre dois snapshots e uma linha de histórico por sessão:
  nenhum teste novo nesta onda.
- Igualdade do snapshot retomado depois de geração parcial: nenhum teste novo nesta onda.
- Cobertura de todos os estados/fallbacks da TUI: nenhum teste novo nesta onda.
- Cabeçalho interno `BLOCKED` do relatório da Task 6: não alterado.

Esses itens permanecem contexto de revisão e não bloqueiam as três correções Important.

## Evidência TDD

### RED

1. `rtk proxy .venv/bin/pytest -q tests/test_prompt_quality.py`
   - Resultado: `6 failed, 8 passed`.
   - Falhas causais incluíram `22 != 11`, `67 != 100`, `36 != 39` e `10 != 100`.
2. `rtk proxy .venv/bin/pytest -q tests/test_tui.py::test_narrow_chat_reflows_quality_panel_without_compressing_metrics`
   - Resultado inicial: `1 failed`; com `max-height: 4`, a região de conteúdo tinha altura
     zero para conteúdo virtual de quatro linhas.
   - O vetor foi endurecido para o viewport padrão `80×24`: `1 failed`, pois o input terminava
     em `y=14` enquanto o painel começava em `y=5`, comprovando sobreposição.
3. Primeira execução da suíte completa depois de apenas remover a compressão:
   - Resultado: `4 failed, 100 passed`; os quatro fluxos Textual não conseguiam acionar o
     envio/geração no viewport curto. Essa regressão orientou a altura mínima e a rolagem.

### GREEN

1. `rtk proxy .venv/bin/pytest -q tests/test_prompt_quality.py tests/test_tui.py`
   - Resultado: `28 passed in 13.94s`.
2. `rtk proxy .venv/bin/pytest -q`
   - Resultado final: `104 passed in 15.92s`.
3. `rtk proxy .venv/bin/ruff check src tests`
   - Resultado final: `All checks passed!`.
4. `rtk proxy .venv/bin/mypy src`
   - Resultado final: `Success: no issues found in 34 source files`.

## Self-review

- Mapeamento dos nove grupos comparado campo a campo com a especificação aprovada.
- Valores esperados dos testes derivados manualmente, sem reutilizar helpers do avaliador.
- Mutações mentais cobertas: separar objetivo, fundir tipos de requisito, omitir dados,
  plataformas ou premissas, voltar a somar listas como booleanos, ignorar itens vazios de
  forma incorreta, remover o cap de dez e restaurar `max-height: 4` quebram ao menos um teste.
- Fórmulas de clareza e prontidão não foram alteradas; apenas suas entradas aprovadas.
- Nenhuma mudança em schema de persistência, workflow, roteamento ou API pública.
- `git diff --check` passou antes da verificação final.

## Commit

- Commit desta correção: `fix: align prompt quality scoring and narrow layout`.
- O hash final é informado no handoff externo, pois um arquivo versionado não pode conter o
  hash do próprio commit sem alterá-lo.

## Concerns

- Em terminais estreitos e baixos como `80×24`, preservar o painel completo e o input exige
  rolagem vertical entre as duas faixas; isso é intencional e evita compressão ou sobreposição.
- Os quatro findings Minor permanecem sem cobertura adicional, por determinação explícita
  desta onda final.
- Nenhum blocker conhecido para os findings Important.
