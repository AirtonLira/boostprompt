export const product = {
  name: 'BoostPrompt',
  repositoryUrl: 'https://github.com/AirtonLira/boostprompt',
  questionRange: [30, 50] as const,
  features: [
    {
      id: 'adaptive-discovery',
      title: 'Discovery adaptativo',
      detail: 'Perguntas, alternativas e trade-offs que se adaptam ao contexto.',
    },
    {
      id: 'auditable-research',
      title: 'Pesquisa auditável',
      detail: 'Fontes preservadas quando uma decisão externa precisa de evidência.',
    },
    {
      id: 'validated-delivery',
      title: 'Entrega validada',
      detail: 'Prompt mestre com requisitos, critérios de aceite e plano de execução.',
    },
    {
      id: 'continuity',
      title: 'Memória e retomada',
      detail: 'Sessões persistidas, resumo estruturado e continuação de entrevistas.',
    },
    {
      id: 'quality',
      title: 'Qualidade observável',
      detail: 'Cobertura, clareza das decisões e prontidão do prompt.',
    },
    {
      id: 'harnesses',
      title: 'Pronto para o seu harness',
      detail: 'CLI/TUI local e skills para Claude Code e Codex.',
    },
  ],
} as const;
