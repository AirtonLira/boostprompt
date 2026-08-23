# BoostPrompt — landing page imersiva

**Data:** 2026-08-23  
**Status:** Aprovada para planejamento

## Objetivo

Criar uma landing page estática, profissional e imersiva para o BoostPrompt. A página deve explicar o produto a partir da documentação existente, converter a visita em abertura do repositório GitHub e ser publicável por GitHub Pages.

O design deriva do logo: base preto-azulada, tipografia branca, azul elétrico, ciano e violeta. A metáfora visual é uma ideia difusa que, por meio de discovery estruturado, se torna um prompt mestre validado.

## Contexto do produto

BoostPrompt transforma uma demanda inicial em um prompt de implementação autocontido. O fluxo conduz discovery adaptativo, registra decisões e pode fazer pesquisa técnica auditável antes de produzir um Markdown com requisitos, decisões, critérios de aceite e plano de execução.

Os diferenciais que a página deve comunicar são:

- 30–50 perguntas adaptativas, feitas uma por vez, com alternativas, trade-offs e recomendação;
- dois modos de saída: `prompt_desenvolvimento` e `roteiro_perguntas_cliente`;
- sessões locais persistidas em DuckDB, retomada e continuação a partir de resumo estruturado;
- painel determinístico de cobertura, clareza de decisões e prontidão do prompt;
- pesquisa opcional via Exa com fontes preservadas e modo degradado explícito;
- integração com endpoints compatíveis com OpenAI, LiteLLM e OpenAI;
- skills instaláveis para Claude Code e Codex.

## Publicação

O site fica em `site/`, separado do pacote Python em `src/`. Um workflow GitHub Actions constrói o site e publica o diretório gerado no GitHub Pages a cada push em `main`.

Com o repositório atual `AirtonLira/boostprompt`, o endereço publicado será `https://airtonlira.github.io/boostprompt`. O domínio `https://boostprompt.github.io` só será possível depois da transferência para uma conta ou organização chamada `boostprompt` e de um repositório de site com o mesmo nome.

## Stack

- Astro para conteúdo estático e componentes da landing;
- React somente nas ilhas interativas;
- React Three Fiber e Three.js para a cena tridimensional;
- GSAP com ScrollTrigger para sequências de scroll, pin e progresso;
- CSS para navegação, hovers e transições simples;
- GitHub Actions e GitHub Pages para publicação.

O canvas 3D e as bibliotecas pesadas devem ser carregados apenas no cliente. O site não terá backend, API ou coleta de dados em tempo de execução.

## Jornada e layout

1. **Navegação fixa:** marca BoostPrompt, âncoras para funcionamento e diferenciais, CTA “Abrir o repositório”. A navegação passa a ser compacta no celular.
2. **Hero assimétrico:** mensagem “Descubra antes. Construa certo.”, CTA primário para o repositório e cena 3D baseada no balão de fala e raio do logo. O objeto responde sutilmente ao mouse em dispositivos com ponteiro fino.
3. **Faixa de capacidades:** sequência horizontal de termos do produto que mantém energia entre o hero e a narrativa.
4. **Narrativa sticky:** três capítulos revelados pelo scroll: discovery adaptativo, pesquisa com evidência e entrega validada. Cada capítulo tem um diagrama de transformação simples.
5. **Diferenciais:** painéis assimétricos com profundidade no hover para números e capacidades: perguntas adaptativas, modos de saída, retomada, qualidade, pesquisa e compatibilidade com harnesses.
6. **Fechamento:** CTA direto para `https://github.com/AirtonLira/boostprompt` e uma síntese curta do valor entregue.

Uma barra de progresso discreta acompanha o scroll. O layout evita um hero centralizado, grades de três cards iguais, emojis e imagens externas. A tipografia será uma sans contemporânea disponível localmente ou por arquivo distribuído com o site; Inter não será usada.

## Movimento e 3D

- GSAP ScrollTrigger controla a seção sticky e a barra de progresso; GSAP fica isolado de qualquer componente que use animações Framer, e Framer não é necessário neste escopo.
- A cena R3F contém geometria abstrata leve, partículas limitadas e iluminação azul/ciano/violeta. Ela muda a rotação e o estado visual entre os capítulos de narrativa.
- O hover e a resposta ao mouse usam `transform`; o scroll usa transform, opacity, filter ou clip-path. Não animar dimensões ou margens.
- Desativar parallax, pin e interação 3D em telas menores que 768px ou ponteiro impreciso. Limitar partículas e reduzir carga em tablets.
- Respeitar `prefers-reduced-motion`: sem animações contínuas, sem pin e com a narrativa apresentada linearmente.

## Acessibilidade e resiliência

- Todo conteúdo essencial existe em HTML fora do canvas.
- Navegação por teclado, foco visível e âncoras semânticas são obrigatórios.
- A cena 3D é decorativa e recebe uma alternativa estática com o mesmo significado quando JavaScript/WebGL falhar, em movimento reduzido ou em dispositivos móveis.
- O CTA GitHub é um link normal; não depende de JavaScript.
- Não haverá conteúdo que pisque mais de três vezes por segundo.

## Componentes propostos

- `BaseLayout.astro`: metadados, fontes locais e estrutura global;
- `Header.astro`: navegação fixa e CTA;
- `HeroSection.astro`: texto de valor e fallback estático;
- `PromptScene.tsx`: ilha React que carrega dinamicamente o canvas R3F;
- `ScrollNarrative.astro`: capítulos semânticos e diagramas;
- `ScrollNarrativeMotion.ts`: comportamento GSAP isolado e com limpeza;
- `FeatureGrid.astro`: diferenciais e fatos de produto;
- `FinalCta.astro`: link ao repositório;
- `site/src/data/product.ts`: único local para texto, URLs e diferenciais verificáveis.

## Testes e verificação

Antes de cada componente de produção, criar um teste que falhe pela ausência do comportamento. Cobrir ao menos:

- CTA principal aponta para o repositório correto;
- diferenciais essenciais da documentação aparecem no HTML;
- modo reduzido não ativa o canvas ou sequência de scroll;
- fallback da cena permanece quando a ilha 3D não é carregada;
- configuração Astro gera os caminhos corretos para o Pages de projeto.

Executar a suíte de testes do site, o build de produção e uma inspeção do diretório de saída. O workflow de Pages deve passar pelo build do site e publicar somente o artefato estático resultante.

## Fora de escopo

- formulário de captura, newsletter ou analytics;
- demonstração conectada ao modelo, criação de sessões ou API;
- domínio próprio e alterações de DNS;
- alteração das capacidades da CLI/TUI ou das skills existentes.
