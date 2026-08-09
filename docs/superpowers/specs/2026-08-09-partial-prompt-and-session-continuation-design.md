# Geração antecipada de prompt e continuação de sessão — Design

## Objetivo

Permitir que uma entrevista de discovery gere um prompt antes de ser concluída, após pelo menos dez respostas, e permitir que uma sessão concluída seja continuada por uma nova entrevista baseada em um resumo compacto de suas decisões.

## Escopo

O recurso se aplica ao modo `prompt_desenvolvimento`. O modo `roteiro_perguntas_cliente` continua gerando seu documento em uma única interação, como já acontece.

## Seleção de provedor de modelo

Antes de abrir o menu principal, a TUI exibirá duas ações: `Usar LiteLLM` e `Usar OpenAI`. A escolha cria o serviço padrão somente depois de o provedor ser definido; por isso, a opção escolhida realmente determina o modelo usado nos agentes da sessão.

`Usar LiteLLM` exige `LLM_MODEL` e uma URL em `LLM_BASE_URL` ou `LITELLM_BASE_URL`; a chave é lida de `LLM_API_KEY`, `LITELLM_API_KEY` ou `API_KEY`. `Usar OpenAI` exige `OPENAI_API_KEY`, usa `OPENAI_MODEL` quando existir (ou `LLM_MODEL` como fallback) e pode usar `OPENAI_BASE_URL` opcional. Ambos os caminhos usam o mesmo adaptador OpenAI-compatible do PydanticAI, pois LiteLLM expõe esse contrato.

Configuração ausente ou incompleta mantém a pessoa na tela de seleção e apresenta uma mensagem acionável, sem mostrar valores de credenciais. A escolha vale enquanto a aplicação estiver aberta; ao reiniciar, a pessoa seleciona o provedor novamente. Serviços injetados nos testes continuam sendo usados diretamente e não mostram a seleção.

Os testes não dependem de `.env` local ou de chave real: testes de agentes usam o modelo de teste do PydanticAI, e testes de configuração criam arquivos de ambiente temporários para validar LiteLLM e OpenAI.

## Geração antecipada

Na tela de chat de uma sessão de desenvolvimento, será exibida uma ação separada para gerar o prompt atual. Ela permanece indisponível até que a sessão tenha dez perguntas respondidas.

Ao acioná-la, o serviço executa as etapas especializadas já usadas na conclusão normal (arquitetura, segurança, entrega e síntese), usando o contexto, as decisões, os resumos e as referências de pesquisa já persistidos. A ação não acrescenta uma resposta vazia ao histórico e não pede uma nova pergunta de discovery.

O Markdown resultante é salvo como documento da sessão e pode ser aberto ou exportado pela ação existente. A sessão permanece em andamento e pode receber novas respostas; uma conclusão posterior substitui o documento salvo pelo resultado mais completo.

O limite de dez respostas é aplicado em duas camadas:

- a TUI deixa a ação de geração antecipada indisponível antes do limite e informa o motivo;
- o serviço rejeita chamadas programáticas antes do limite com uma mensagem clara.

## Estados de sessão

Uma sessão sem documento final permanece `active`. Quando há geração antecipada, passa a `in_progress`; isso registra que há um rascunho sem confundir esse estado com a conclusão da entrevista. A conclusão natural da entrevista, e o roteiro de perguntas para cliente, marcam a sessão como `completed`.

Para preservar sessões criadas antes deste recurso, a migração tratará documentos finais já existentes em sessões `active` como concluídos. Sessões que receberam geração antecipada usam `in_progress`, portanto não serão convertidas indevidamente em inicializações futuras.

## Continuação de sessão concluída

Ao selecionar uma sessão `completed`, a TUI continua permitindo abrir seu documento, mas também mostra uma ação para iniciar uma continuação. Antes da nova entrevista, o serviço sintetiza a sessão original usando todo o histórico, o último contexto estruturado e o resumo anterior, se houver.

O resumo exibido usa bullets e agrupa os pontos relevantes em:

- objetivo e fatos confirmados;
- decisões tomadas;
- restrições e riscos;
- tópicos cobertos e pendências.

A continuação cria uma nova sessão no mesmo modo, com nome derivado da sessão original, código próprio e estado `active`. O histórico da sessão anterior não é copiado. Em vez disso, a nova sessão recebe apenas o `SessionSummary` atualizado e um contexto mínimo que identifica a origem. No primeiro turno, o serviço reinjeta esse resumo no estado do workflow, para que o agente de discovery preserve as decisões anteriores e avance sobre a nova feature.

A sessão concluída e seu documento nunca são alterados pela continuação. A ligação entre as sessões é registrada como metadado de contexto para rastreabilidade, sem expandir o esquema relacional além do necessário.

## Arquitetura

`TurnWorkflow` receberá um sinal explícito para pular discovery e seguir para as etapas finais. `DiscoveryWorkflowService` será o único ponto que valida o mínimo de respostas, monta o estado do workflow, persiste documentos e altera o status da sessão.

`DuckDBStore` continuará sendo o proprietário de mensagens, snapshots, resumos, documentos e estado da sessão. Ele acrescentará operações pequenas para atualizar o status e para criar a sessão de continuação já semeada com resumo e contexto mínimo.

A TUI apenas renderiza a disponibilidade das ações, apresenta o resumo em Markdown com bullets e delega geração/continuação ao serviço.

## Fluxos e erros

Se a síntese ou o resumo falhar, nenhuma nova sessão é criada e a sessão original não é modificada. A TUI apresenta o erro retornado pelo serviço.

Uma sessão que não está concluída não oferece continuação; ela é retomada normalmente. Uma sessão concluída sem mensagens ainda pode ser retomada para abrir seu documento, mas a continuação falha de forma explícita, pois não há conteúdo suficiente para resumir.

## Testes de aceitação

- Com nove respostas, a geração antecipada é rejeitada pelo serviço e permanece indisponível na TUI.
- Com dez respostas, o serviço produz e persiste o Markdown sem criar uma mensagem de usuário vazia e mantém a sessão em andamento.
- A conclusão normal marca a sessão como `completed`.
- Selecionar uma sessão concluída mostra seu resumo em bullets e permite iniciar continuação.
- A continuação cria outra sessão com novo código, mantém a original inalterada e injeta apenas o resumo, não o histórico integral, no primeiro turno.
- Falhas ao resumir ou sintetizar não deixam dados parcialmente persistidos.
