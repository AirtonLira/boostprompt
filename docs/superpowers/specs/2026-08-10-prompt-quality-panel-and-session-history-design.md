# Painel de qualidade do prompt e histórico enriquecido — Design

## Objetivo

Tornar a entrevista de discovery mais orientada a progresso: a TUI Textual exibirá, durante toda sessão interativa de desenvolvimento, um painel fixo no canto inferior direito com três métricas que estimam a qualidade do prompt que poderá ser gerado. A lista de sessões passará a apresentar o último retrato de qualidade salvo para cada sessão.

O recurso reutiliza a arquitetura atual: PydanticAI produz perguntas e atualizações de contexto, LangGraph executa um turno por resposta, `DiscoveryWorkflowService` coordena o caso de uso, DuckDB é a fonte de verdade e Textual apenas renderiza e interage.

## Escopo e decisões

- O painel é exibido dentro da `ChatScreen`, à direita da área de conversa e ancorado ao fim da tela; em terminais estreitos ele ocupa uma faixa abaixo do chat para preservar a legibilidade.
- As métricas são recalculadas ao término bem-sucedido de cada turno e persistidas como um snapshot da sessão. A abertura de uma sessão recupera o último snapshot disponível.
- Os cálculos são determinísticos, locais e explicáveis; não acionam o modelo nem aumentam o custo ou a latência do turno.
- O modo `prompt_desenvolvimento` recebe a avaliação completa. O modo `roteiro_perguntas_cliente` permanece de geração direta, como previsto no comportamento atual; seu painel e histórico informam que a avaliação de prontidão não se aplica porque não há entrevista respondida.
- Sessões anteriores à mudança continuam utilizáveis. Sem snapshot salvo, a lista e o chat mostram `Sem avaliação` até que a sessão receba uma nova resposta.

## Experiência da TUI

### Painel “Qualidade do prompt”

Depois de cada resposta, o painel mostra:

1. **Cobertura do contexto** — percentual dos blocos essenciais do discovery que já contêm informação registrada. Indica se o prompt terá abrangência suficiente.
2. **Clareza das decisões** — percentual que confronta fatos e decisões confirmados com riscos e pendências abertas. Indica o quanto o prompt evitará suposições ambíguas.
3. **Prontidão do prompt** — composição de cobertura, clareza e avanço até o mínimo de 30 perguntas. Indica se já há base para produzir um rascunho útil.

Cada cartão exibe valor de 0 a 100, descrição em uma linha e uma mensagem curta de estado. O cabeçalho informa o progresso da entrevista, por exemplo, `12/30 respostas mínimas`. O painel usa rótulos textuais além de cor para continuar acessível em terminais sem suporte confiável a cores.

Enquanto não existir resposta, as três métricas mostram `0` e explicam que dependem do contexto inicial. O painel não bloqueia o envio, a geração antecipada ou a conclusão normal.

### Fórmulas

O avaliador lê somente o `ContextState` serializado e o contador de perguntas. Um bloco está coberto quando ao menos um dos campos abaixo tem conteúdo:

| Bloco | Campos |
| --- | --- |
| Problema e objetivo | `necessidade`, `problema`, `objetivo` |
| Pessoas | `usuarios`, `stakeholders` |
| Escopo funcional | `tipo_solucao`, `requisitos_funcionais` |
| Requisitos não funcionais | `requisitos_nao_funcionais` |
| Dados e integrações | `dados`, `integracoes` |
| Arquitetura | `arquitetura`, `plataformas`, `dominio` |
| Segurança | `seguranca` |
| Entrega e operação | `entrega`, `operacao` |
| Restrições e riscos | `restricoes`, `premissas`, `riscos` |

`cobertura = round(blocos_cobertos / 9 * 100)`.

Para clareza, cada informação relevante confirmada (`objetivo`, `problema`, `tipo_solucao`, usuários, requisitos, integrações, arquitetura e decisões) acrescenta evidência até o limite de 10. Cada item em `pendencias` ou `riscos` reduz a pontuação. A fórmula é `round(100 * evidencias / (10 + 2 * incertezas))`, limitada entre 0 e 100. Isso evita pontuação alta para uma sessão vazia que simplesmente ainda não registrou pendências.

`prontidao = round(0.50 * cobertura + 0.35 * clareza + 0.15 * min(perguntas / 30, 1) * 100)`.

As fórmulas e textos do painel ficam concentrados em um avaliador puro, para serem testáveis e ajustáveis sem mudar a TUI ou o workflow.

### Histórico de sessões

A lista de sessões exibe, para cada item:

- código e nome;
- modo, status e respostas registradas;
- data/hora da última atualização;
- último valor de prontidão, ou `Sem avaliação`/`Não aplicável`.

A seleção, abertura, retomada, atualização e exclusão continuam com o comportamento atual. Exibir a avaliação no histórico não executa agentes nem atualiza dados.

## Arquitetura e dados

Um novo modelo Pydantic `PromptQualityEvaluation` representa os três valores, o total de perguntas, uma descrição de estado e a data de avaliação. Um serviço puro `PromptQualityEvaluator` transforma contexto e contador em esse modelo.

`TurnResult` carregará opcionalmente a avaliação para a TUI renderizar imediatamente. `DiscoveryWorkflowService.submit_answer` calcula a avaliação após o workflow retornar e a persiste na mesma unidade lógica do turno. `generate_partial_prompt` também recalcula e persiste o retrato mais recente. `resume_session` recupera o snapshot mais novo junto aos dados já retornados.

DuckDB recebe a tabela `session_quality_evaluations`, com identificador, sessão, valores numéricos, descrição, contador de perguntas e data. Uma nova leitura obtém o snapshot mais recente por sessão; `list_sessions` faz junção com esse snapshot sem multiplicar linhas. A exclusão em cascata manual inclui a tabela nova.

O contrato de `SessionService` expõe a avaliação ao retomar e listar sessões. Fakes de teste retornam avaliações controladas, mantendo testes Textual independentes de banco e modelo.

## Tratamento de erros

- O avaliador aceita contexto parcial ou vazio e sempre retorna uma avaliação válida, sem lançar exceções por chaves ausentes ou tipos inesperados.
- Uma falha de banco durante a persistência mantém a semântica atual: o turno não é anunciado como concluído se seus dados duráveis não puderem ser gravados.
- Dados legados sem avaliação continuam abrindo normalmente e não recebem valores inventados.
- O modo de roteiro para cliente não tenta calcular prontidão nem mostra percentuais potencialmente enganosos.

## Testes e critérios de aceite

- O avaliador produz 0 para contexto vazio, aumenta cobertura ao preencher blocos e reduz clareza ao registrar riscos ou pendências.
- A prontidão respeita as ponderações e não alcança a parcela de progresso antes de 30 perguntas.
- Cada resposta de uma entrevista persiste e devolve uma avaliação; a retomada recupera o último snapshot.
- Geração antecipada atualiza o snapshot sem adicionar uma mensagem de usuário vazia.
- A TUI mostra os três valores e suas descrições depois de um envio e restaura-os ao abrir uma sessão existente.
- A lista de sessões mostra metadados enriquecidos e a última prontidão sem alterar o comportamento de abrir, retomar ou excluir.
- Em largura reduzida, o painel não sobrepõe o campo de resposta nem as ações do chat.
- O modo de roteiro para cliente continua produzindo um documento em uma interação e indica avaliação não aplicável.
- A suíte existente continua verde, acompanhada por testes unitários do avaliador e funcionais da TUI/persistência.

## Fora de escopo

- Não haverá chamada adicional a LLM para avaliar respostas.
- Não haverá gráficos históricos, tendência por pergunta ou ranking entre sessões nesta alteração.
- Não será alterada a entrevista de 30 a 50 perguntas nem o formato do Markdown final.
