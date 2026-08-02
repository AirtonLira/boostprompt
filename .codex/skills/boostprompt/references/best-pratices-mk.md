# Objetivo

Quero que você trabalhe em duas fases distintas:

1. **Fase de Planejamento**
   - Use **GPT 5.6 Sol** apenas para analisar o problema.
   - Estruture a solução.
   - Quebre o trabalho em tarefas pequenas, independentes e verificáveis.
   - Defina ordem, dependências, riscos e critérios de pronto.

2. **Fase de Execução**
   - Depois de concluir o planejamento, troque para **GPT 5.6 Terra** para executar.
   - Execute uma tarefa por vez.
   - Valide cada tarefa antes de seguir para a próxima.
   - Se surgir nova informação, atualize o plano e continue.

# Contexto

## Problema
[descreva o problema]

## Objetivo final
[descreva o resultado esperado]

## Restrições
- Não faça mudanças desnecessárias.
- Prefira alterações pequenas, seguras e fáceis de validar.
- Preserve compatibilidade quando possível.

# Formato obrigatório

## Fase 1 — Planejamento com Opus

Responda primeiro com:

### Resumo
[resumo do problema]

### Estratégia
[abordagem geral]

### Plano de tarefas
1. **Nome da tarefa**
   - Objetivo:
   - Arquivos afetados:
   - Abordagem:
   - Riscos:
   - Critério de pronto:

2. **Nome da tarefa**
   - Objetivo:
   - Arquivos afetados:
   - Abordagem:
   - Riscos:
   - Critério de pronto:

### Ordem de execução
[explique sequência e dependências]

## Fase 2 — Execução com GPT 5.6 Terra

Depois do planejamento, execute o plano tarefa por tarefa neste formato:

### Tarefa atual
[nome]

### Implementação
[o que está fazendo]

### Validação
[como verificou]

### Resultado
[o que mudou]

### Próxima tarefa
[o que vem depois]

# Regras adicionais

- Não execute antes de produzir o plano.
- Não misture planejamento e implementação na mesma etapa.
- Se uma tarefa for grande demais, subdivida antes de executar.
- Mantenha consistência entre plano e execução.
- Não faça nenhum commit sem eu aprovar.