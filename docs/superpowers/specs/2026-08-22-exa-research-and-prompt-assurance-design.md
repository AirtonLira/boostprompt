# Pesquisa Exa e Garantia de Prompt - Design

## Objetivo

Elevar a confiabilidade do artefato principal do BoostPrompt: um unico prompt
Markdown de implementacao, autocontido, que possa ser entregue a um agente sem
redescobrir requisitos nem reconciliar documentos duplicados. A melhoria deve
funcionar na TUI local e nas skills para Claude Code e Codex, substituindo
DuckDuckGo por Exa como fonte principal de pesquisa atual e rastreavel.

## Escopo desta iteracao

- Introduzir uma porta de pesquisa independente de fornecedor.
- Usar a API Exa no CLI/TUI e o MCP remoto oficial da Exa nas skills instaladas.
- Planejar pesquisas com base em decisoes tecnicas e lacunas do discovery, nao em
  uma lista fixa de palavras na ultima resposta.
- Normalizar, avaliar e persistir evidencias com proveniencia suficiente para
  auditoria.
- Garantir que a pesquisa alimente a proxima pergunta e os agentes finais de
  arquitetura, seguranca, entrega e sintese.
- Validar estruturalmente o unico prompt final; fazer uma unica tentativa de
  reparo quando o modelo omitir informacoes exigidas.
- Corrigir o limiar do prompt parcial para exigir dez respostas efetivas, e nao
  apenas dez perguntas exibidas.

Ficam fora de escopo redesenho da TUI, novos provedores pagos de busca, pesquisa
multi-idioma configuravel e avaliacao semantica feita por outro modelo. A porta
de pesquisa deixa esses incrementos possiveis sem acoplamento posterior.

## Decisao arquitetural

A aplicacao tera uma camada `research` com tres responsabilidades separadas:

1. `ResearchPlanner`: devolve no maximo duas consultas curtas quando uma resposta
   ou lacuna exige informacao externa atual. Ele classifica a intencao como
   `technical`, `security`, `compliance`, `market` ou `news`, define recencia e
   dominios preferenciais. Nao pesquisa para dados que devem vir do usuario,
   como prioridade de negocio, orcamento ou politica interna.
2. `ResearchProvider`: executa as consultas e devolve evidencias normalizadas. A
   implementacao de producao do CLI sera `ExaResearchProvider`; testes usam um
   provider falso. Falhas ficam encapsuladas em `ResearchUnavailableError` e nao
   interrompem a entrevista.
3. `EvidencePolicy`: remove duplicatas, exige URL, limita o volume enviado ao
   modelo e ordena fontes primarias, documentacao oficial e fontes recentes antes
   de conteudo opinativo. A politica nunca inventa data, autoridade ou trecho.

O CLI usa a API HTTP da Exa com `EXA_API_KEY`. Isso evita iniciar um subprocesso
MCP para toda busca, preserva respostas estruturadas e permite timeout, retry e
metricas consistentes. As skills configuram o MCP remoto `https://mcp.exa.ai/mcp`;
assim Claude Code e Codex usam a integracao oficial do mesmo provedor sem a
aplicacao depender do processo local do harness.

## Fluxo por turno

```text
resposta do usuario + contexto persistido
  -> ResearchPlanner (condicional, no maximo 2 consultas)
  -> ExaResearchProvider + EvidencePolicy
  -> DiscoveryAgent gera contexto atualizado e a proxima pergunta
  -> persistencia atomica de mensagem, contexto, plano e evidencias

quando a entrevista termina ou o usuario pede rascunho
  -> auditoria de cobertura de evidencias
  -> arquitetura -> seguranca -> entrega -> sintese
  -> PromptArtifactValidator
  -> reparo unico pela sintese, somente se necessario
  -> persistencia do prompt Markdown validado e do relatorio de qualidade
```

O planejador ve a resposta mais recente, o resumo compactado e o contexto
estruturado. A pesquisa concluida entra no `research_context` antes da proxima
pergunta, portanto recomendacoes sobre frameworks, seguranca, cloud e integracoes
podem citar fatos atuais. No encerramento, os agentes especializados recebem a
mesma evidencia filtrada, e a sintese recebe referencias identificadas.

Se a Exa estiver indisponivel, a proxima pergunta continua em modo degradado,
exibindo isso na TUI e registrando o motivo. A sintese deve declarar a ausencia de
pesquisa em "Referencias consultadas" e nao sugerir que uma fonte foi usada.

## Contratos de dados

`ResearchRequest` tera `query`, `decision_context`, `topic`, `freshness`,
`include_domains` e `max_results`. A aplicacao aceitara apenas requests produzidos
pelo planejador, com no maximo dois por turno e dez resultados por request.

`ResearchFinding` sera estendido de forma compativel com:

- `source_id`: identificador estavel usado nas citacoes;
- `query`: consulta que encontrou a fonte;
- `published_at`: data publicada ou atualizada, quando o provedor a informar;
- `source_kind`: `official`, `primary`, `reputable`, `community` ou `unknown`;
- `relevance_score`: valor opcional devolvido pelo provedor;
- `retrieved_at`: instante local de recuperacao.

O DuckDB recebera apenas colunas aditivas em `research_findings`. Sessoes antigas
continuam validas: campos desconhecidos sao nulos e fontes legadas ficam com
`source_kind=unknown`. As tabelas de mensagens, contextos, resumos e Markdown
nao serao reescritas.

`PromptValidationReport` registrara `valid`, `missing_sections`,
`missing_prompt_topics`, `invalid_reference_urls`, `warnings` e `repaired`.
O snapshot de qualidade existente passa a incluir o resultado da validacao, sem
converter uma avaliacao visual de prontidao em afirmacao de garantia semantica.

## Politica de fontes

- Para recomendacoes de tecnologia, preferir documentacao oficial, repositorios
  mantidos, especificacoes e provedores do produto.
- Para seguranca e compliance, priorizar legislacao, orgaos reguladores, normas e
  documentacao oficial; conteudo de blog nao fundamenta requisito normativo.
- Para fatos atuais, aplicar filtro de recencia definido pelo planejador. Busca
  generica sem necessidade temporal nao deve descartar documentacao estavel.
- Toda fonte persistida precisa ter URL absoluta, titulo e trecho; data e score
  sao opcionais, nunca sintetizados pela aplicacao.
- A sintese recebe no maximo oito fontes distintas e deve associar cada uma a uma
  decisao. Ela nao recebe URL sem o identificador da evidencia correspondente.

## Prompt final unico

O resultado final nao tera um documento de escopo seguido de uma secao que repete
o mesmo conteudo como "prompt mestre". Ele tera o titulo
`# Prompt Mestre de Implementacao - <nome do projeto>` e sera, por inteiro, a
instrucao dirigida ao agente que implementara o sistema.

O prompt conserva as 22 areas de informacao necessarias, mas a ultima deixa de
ser uma copia do artefato. A hierarquia canonica sera: contexto e objetivo,
problema, resultados de negocio, usuarios, premissas, requisitos funcionais e
nao funcionais, arquitetura e stack, dados e fluxos, seguranca, entrega,
operacao, riscos, roadmap, decisoes, plano de execucao, criterios de aceite,
estrategia de validacao, pendencias, referencias e, por fim, instrucoes diretas
ao agente implementador. Assim, a secao final complementa as especificacoes
anteriores em vez de resumi-las ou reescreve-las.

O Markdown deve usar apenas uma hierarquia de titulos, listas para requisitos e
criterios observaveis, tabelas para mapeamentos com tres ou mais campos, cercas de
codigo com linguagem para contratos tecnicos e citacoes identificadas junto da
decisao que fundamentam. Nao pode conter secoes vazias, instrucoes contraditorias,
URL sem contexto ou referencias a um "documento acima" ou "prompt abaixo".

## Garantia do prompt

`PromptArtifactValidator` e deterministico. Ele exige o titulo canonico e as 22
secoes do prompt unico, conteudo nao vazio nas secoes 16 a 22, URLs validas nas
referencias quando houver evidencia e instrucoes ao implementador que cubram
objetivo, escopo, restricoes, requisitos funcionais e nao funcionais, arquitetura,
dados e integracoes, seguranca, testes, observabilidade, entrega e criterio de
aceite.

O validador nao infere fatos e nao aprova alegacoes por plausibilidade. Quando
falhar, a sintese recebe somente a lista de lacunas e o Markdown gerado para fazer
uma unica correcao. Se a segunda validacao falhar, o documento e salvo como
rascunho com alertas explicitos; nunca como escopo final validado.

O prompt parcial usa o mesmo formato unico e a mesma validacao, mas pode retornar
alertas de cobertura esperados. Ele so fica disponivel apos dez respostas de
discovery confirmadas, separadas da descricao inicial da demanda.

## Alteracoes nas skills e no instalador

As duas copias de `SKILL.md` devem trocar DuckDuckGo por Exa e incluir a politica
de fontes, o uso de `web_search_exa` seguido de `web_fetch_exa` quando o trecho
nao bastar, a obrigacao de apontar a decisao sustentada por cada referencia e o
modo degradado quando o MCP nao estiver disponivel.

O instalador passa a registrar o MCP remoto Exa para Claude Code e Codex, sem
inserir chave em arquivos versionados. A chave do CLI e lida apenas de
`EXA_API_KEY`; a documentacao deve explicar a autenticacao OAuth ou por chave do
MCP remoto, conforme o harness suportar.

## Tratamento de falhas e seguranca

- Timeout por chamada, retry somente para erros temporarios e limites de
  concorrencia impedem que pesquisa bloqueie a TUI indefinidamente.
- Erros de autenticacao, limite de uso, resposta invalida e ausencia de resultados
  viram eventos auditaveis de modo degradado, sem expor segredos ao usuario.
- Consultas sao derivadas de contexto de produto; elas nao incluem credenciais,
  dados pessoais ou historico inteiro da sessao.
- O log e o banco guardam somente metadados e conteudo ja retornado pelo provedor;
  a chave da Exa nao e persistida nem exibida.

## Testes e criterios de aceite

Os testes devem cobrir:

- planejamento de pesquisa para decisoes tecnicas e ausencia de pesquisa para
  informacoes exclusivamente internas;
- normalizacao de respostas Exa, deduplicacao, classificacao e modo degradado;
- migracao DuckDB e recuperacao de evidencias antigas e novas;
- propagacao das evidencias a discovery, agentes finais e sintese;
- contrato das skills e configuracao correta do instalador nos dois harnesses;
- validacao de Markdown completo, reparo unico e salvamento como rascunho quando
  o reparo tambem falhar;
- limiar de exatamente dez respostas antes da opcao de rascunho;
- regressao de 30 a 50 perguntas, roteiro de cliente, continuacao de sessao e
  persistencia atomica.

A entrega sera aceita quando uma decisao que exija dados atuais produzir pesquisa
antes da proxima pergunta, cada referencia final for auditavel e vinculada a uma
decisao, um Markdown incompleto nao for marcado como final validado e uma sessao
antiga continuar abrindo sem migracao manual.

## Alternativas descartadas

Tavily oferece busca, filtro temporal e extracao adequados, mas a Exa atende os
dois harnesses-alvo com MCP remoto oficial e tambem oferece busca, fetch, filtros
por data e pesquisa avancada. Uma composicao Exa + Brave aumenta cobertura e
resiliencia, mas exige custo, operacao e politicas de reconciliacao que nao se
justificam nesta primeira entrega.
