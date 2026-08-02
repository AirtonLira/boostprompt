# Correção da CLI/TUI e fluxo de discovery — Design

## Objetivo

Transformar a CLI Textual em uma entrevista de discovery confiável: uma pergunta por resposta, entre 30 e 50 perguntas no modo de desenvolvimento, geração direta de roteiro no modo de perguntas ao cliente, pesquisa opcional via MCP DuckDuckGo e recuperação de sessões locais com resumo útil.

## Requisitos confirmados

- Manter Textual para a TUI, LangGraph para orquestração, PydanticAI para os agentes e DuckDB para persistência local.
- Implementar os mesmos contratos comportamentais das skills Claude e Codex: `prompt_desenvolvimento` e `roteiro_perguntas_cliente`, pt-BR, 30–50 perguntas, alternativas, trade-offs, recomendação e Markdown final.
- Persistir cada interação localmente e retomar uma sessão sem perder objetivo, decisões, restrições, respostas e pendências.
- Gerar um resumo de pontos essenciais antes que o contexto retomado fique grande.
- Usar o servidor MCP DuckDuckGo já configurado pelo instalador (`ddg-search`, comando `uvx duckduckgo-mcp-server`) como pesquisa opcional.

## Fluxos

### Modo `prompt_desenvolvimento`

1. A TUI coleta nome, demanda inicial e modo; a sessão DuckDB é criada antes da primeira chamada ao modelo.
2. Cada envio do usuário chama uma única execução LangGraph `intake -> research? -> discovery -> persist`.
3. `DiscoveryAgent` retorna somente a próxima pergunta estruturada e uma atualização de contexto. A pergunta possui texto explícito, categoria, justificativa, alternativas, trade-offs, recomendação e instrução de resposta.
4. A execução termina após persistir a pergunta. Não existe aresta `discovery -> discovery` no mesmo turno.
5. Ao atingir 30 respostas, o agente pode encerrar se não houver lacuna relevante; aos 50 encerra obrigatoriamente. O encerramento ativa `architecture -> security -> delivery -> synthesis -> persist` e exibe o Markdown final.

### Modo `roteiro_perguntas_cliente`

1. Após receber a demanda, o grafo executa `research? -> question_guide -> persist`.
2. `QuestionGuideAgent`, com saída Pydantic validada, produz de 30 a 50 perguntas adaptadas à demanda.
3. A TUI grava e abre um único Markdown com a estrutura da skill; não inicia entrevista interativa nem gera escopo técnico extra.

### Retomada e resumo

1. A sessão é recuperada por código ou pela lista de sessões.
2. O repositório monta um contexto de retomada com resumo persistido, decisões, contexto estruturado e apenas as mensagens recentes.
3. Quando o histórico ainda não resumido ultrapassar o limite definido, `SummaryAgent` recebe o resumo anterior, o contexto e o lote de mensagens antigas. Sua saída Pydantic preserva objetivo, fatos confirmados, decisões, restrições, riscos, blocos cobertos e pendências.
4. O resumo é salvo no DuckDB antes de descartar mensagens do prompt. O histórico completo permanece auditável no banco.

## Arquitetura

### Orquestração

`DiscoveryWorkflowService` é a única porta de entrada entre Textual e LangGraph. Ele cria agentes uma vez, monta o grafo e expõe operações de criar sessão, processar turno, retomar sessão e gerar roteiro.

O estado LangGraph é um `TypedDict` explícito, sem um redutor que replique todo o histórico em cada nó. Cada nó devolve apenas o delta que alterou. Campos essenciais: `session_id`, `mode`, `context`, `summary`, `recent_messages`, `questions_count`, `covered_topics`, `pending_topics`, `should_finalize`, `research_findings` e `final_markdown`.

Os agentes PydanticAI permanecem especializados:

- `DiscoveryAgent`: pergunta seguinte e atualização de contexto.
- `ResearchAgent`: consulta MCP apenas para decisões técnicas que exigem atualidade.
- `SummaryAgent`: resumo estruturado de retomada.
- `ArchitectureAgent`, `SecurityAgent`, `DeliveryAgent` e `SynthesisAgent`: etapas finais do modo de desenvolvimento.
- `QuestionGuideAgent`: roteiro direto para o cliente.

### Persistência DuckDB

`SessionRepository` substitui gravações de todo o estado e fornece operações transacionais de append.

- `sessions`: id, código, nome, modo, status, timestamps e contadores.
- `messages`: id estável, sequência por sessão, papel, conteúdo e timestamp; cada mensagem é inserida uma única vez.
- `context_snapshots`: contexto, contagem, blocos cobertos e pendências.
- `session_summaries`: resumo estruturado, até qual sequência foi condensada e timestamp.
- `decisions`: mantém decisões e trade-offs já existentes.

Migrações são aditivas e preservam bancos atuais. A criação, resposta, pergunta e snapshot de um turno usam uma transação; não há botão "Salvar" como requisito de durabilidade.

### MCP DuckDuckGo

`DuckDuckGoMCPResearchProvider` implementa uma porta `ResearchProvider`. Ele inicia/usa o servidor stdio configurado como `ddg-search` e normaliza resultados em título, URL, excerto e data de consulta. `ResearchAgent` só o chama quando a pergunta demanda tecnologia, arquitetura, segurança, compliance, modelos, infraestrutura ou outra informação sujeita a atualização.

Se o MCP ou o comando `uvx` não estiver disponível, a aplicação não inventa fontes: registra pesquisa indisponível, continua em modo degradado e informa isso no Markdown em "Referências consultadas". Resultados são persistidos com URL e decisão que fundamentaram. Não são enviados histórico ou dados sensíveis além da consulta mínima necessária.

### TUI Textual

- A tela de nova sessão inclui seleção do modo e cria a sessão imediatamente.
- `ChatScreen` recebe o serviço de aplicação; não instancia agentes, workflows ou conexões DuckDB por mensagem.
- A tela atualiza apenas as mensagens retornadas pelo turno, bloqueia o envio enquanto há worker e mostra erros recuperáveis.
- A lista de sessões mantém o `LoadingIndicator` montado, alternando visibilidade em vez de removê-lo.
- Retomar mostra contexto resumido e histórico recente, preservando o histórico completo no banco.

## Paridade de skills

Uma fonte canônica de contrato será usada para prompts e verificações. Os arquivos `.claude/skills/boostprompt/SKILL.md` e `.codex/skills/boostprompt/SKILL.md` devem permanecer semanticamente equivalentes, e testes garantirão modos, faixa de perguntas, cabeçalhos obrigatórios e política de pesquisa. Prompts do aplicativo reutilizam essas regras em vez de manter uma versão reduzida e divergente.

## Erros e limites

- Falhas de modelo, MCP ou banco são apresentadas em pt-BR e preservam a sessão já gravada.
- O código não chama provedores externos durante importação, listagem ou retomada.
- Nenhuma pergunta é gerada sem texto explícito e sem validação Pydantic.
- `questions_count` conta perguntas exibidas, não chamadas internas de agente.
- O Markdown só é oferecido no modo de desenvolvimento após a condição de encerramento; o roteiro é oferecido imediatamente no modo cliente.

## Testes de aceitação

- O refresh de sessões não lança `NoMatches`.
- Um envio ao modo desenvolvimento aciona um único nó discovery e persiste exatamente a resposta do usuário e a próxima pergunta.
- A entrevista não finaliza antes de 30 respostas, pode finalizar entre 30–49 com justificativa do agente e finaliza até 50.
- Não há mensagens duplicadas após múltiplos turnos ou retomada.
- Retomada usa resumo estruturado e preserva decisões, riscos e pendências.
- O modo cliente produz Markdown válido com 30–50 perguntas, sem acionar o fluxo de síntese de escopo.
- Falha do MCP mantém a sessão utilizável e marca pesquisa em modo degradado; êxito persiste referências.
- As skills Codex e Claude atendem ao mesmo contrato testado pela CLI.

## Fora de escopo

- Sincronização remota de sessões.
- Autenticação de usuários.
- Troca de framework TUI, banco ou orquestrador.
- Pesquisa automática para cada pergunta; ela será seletiva e fundamentada.
