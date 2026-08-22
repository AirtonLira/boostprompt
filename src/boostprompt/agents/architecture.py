"""
Agente de Arquitetura: foca em arquitetura, stack, integrações, dados.

Responsabilidades:
- Definir arquitetura (monolito, microsserviços, serverless, etc.)
- Escolher stack tecnológica (linguagens, frameworks, bibliotecas)
- Definir modelo de dados e persistência
- Planejar integrações e APIs
- Recomendar infraestrutura (cloud, on-premise, híbrido)
"""
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from .base import BaseAgent

# =============================================================================
# Schemas
# =============================================================================

class ArchitectureDecision(BaseModel):
    """Modelo de uma decisão de arquitetura."""
    category: str = Field(
        description="Categoria da decisão (ex: 'arquitetura', 'banco_de_dados', 'api')"
    )
    decision: str = Field(
        description="Decisão tomada (ex: 'microsserviços com FastAPI')"
    )
    alternatives: list[str] = Field(
        description="Alternativas consideradas"
    )
    rationale: str = Field(
        description="Justificativa da decisão"
    )
    tradeoffs: str = Field(
        description="Trade-offs aceitos"
    )


class ArchitectureResponse(BaseModel):
    """Resposta do agente de arquitetura."""
    decisions: list[ArchitectureDecision] = Field(
        default_factory=list,
        description="Decisões de arquitetura tomadas"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recomendações gerais de arquitetura"
    )
    context_update: dict[str, Any] = Field(
        default_factory=dict,
        description="Atualizações para o contexto acumulado"
    )
    summary: str = Field(
        description="Resumo das decisões de arquitetura"
    )


# =============================================================================
# Prompts
# =============================================================================

ARCHITECTURE_SYSTEM_PROMPT = """Você é o Architecture Agent do BoostPrompt, especialista em arquitetura de software, stack tecnológica, bancos de dados, APIs, integrações e infraestrutura.

Sua função é analisar o contexto acumulado do discovery e tomar decisões de arquitetura bem fundamentadas.

## Áreas de Atuação

1. **Arquitetura** - monolito, microsserviços, serverless, event-driven, SOA
2. **Stack** - linguagens, frameworks, bibliotecas, ferramentas
3. **Dados** - bancos relacionais, NoSQL, data warehouse, lakehouse, cache
4. **APIs** - REST, GraphQL, gRPC, WebSocket, mensageria
5. **Infraestrutura** - cloud (AWS, GCP, Azure), on-premise, híbrido, containers, Kubernetes
6. **Integrações** - APIs externas, webhooks, ETL/ELT, streaming

## Critérios de Decisão

Sempre considere:
- Requisitos funcionais e não funcionais do projeto
- Volume de dados e usuários
- Performance e latência exigidos
- Custo e orçamento
- Habilidades do time
- Complexidade de operação
- Escalabilidade futura
- Vendor lock-in

## Formato de Resposta

Sempre responda com:
- `decisions`: Lista de decisões tomadas (categoria, decisão, alternativas, justificativa, trade-offs)
- `recommendations`: Recomendações gerais de arquitetura
- `context_update`: Atualizações para o contexto (ex: {"arquitetura": ["microsserviços", "FastAPI"]})
- `summary`: Resumo das decisões

## Importante

- Seja pragmático: evite over-engineering
- Justifique cada decisão com base no contexto
- Liste alternativas descartadas e o motivo
- Priorize tecnologias maduras e bem documentadas
- Considere custo total de propriedade (TCO)
"""

ARCHITECTURE_USER_PROMPT = """
## Contexto Acumulado

{context_json}

## Decisões Já Tomadas

{decisions_json}

## Referências de pesquisa

{research_context}

## Sua Tarefa

Com base no contexto acima, quais decisões de arquitetura você recomenda?

Foque em:
- Arquitetura geral do sistema
- Stack tecnológica principal
- Modelo de dados e persistência
- Estratégia de APIs e integrações
- Infraestrutura e deploy

Se já houver decisões suficientes, você pode retornar uma lista vazia de decisions.
"""


# =============================================================================
# Agente
# =============================================================================

class ArchitectureAgent(BaseAgent):
    """Agente de Arquitetura com Pydantic AI."""

    name = "architecture"
    description = "Especialista em arquitetura e stack tecnológica"

    def __init__(self, model: Model | str = "openai:gpt-4o-mini"):
        self.agent = Agent(
            model,
            output_type=ArchitectureResponse,
            system_prompt=ARCHITECTURE_SYSTEM_PROMPT,
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executa o agente de arquitetura."""
        import json

        context = state.get("context", {})
        decisions = state.get("decisions", [])
        research_context = state.get("research_context", "Nenhuma referência externa disponível.")

        user_prompt = ARCHITECTURE_USER_PROMPT.format(
            context_json=json.dumps(context, indent=2, ensure_ascii=False),
            decisions_json=json.dumps(decisions, indent=2, ensure_ascii=False),
            research_context=research_context,
        )

        result = await self.agent.run(user_prompt)
        response: ArchitectureResponse = result.output

        # Atualiza estado
        new_state = state.copy()

        # Adiciona decisões ao estado
        if response.decisions:
            current_decisions = new_state.get("decisions", [])
            new_state["decisions"] = current_decisions + [
                {
                    "category": d.category,
                    "decision": d.decision,
                    "alternatives": d.alternatives,
                    "rationale": d.rationale,
                    "tradeoffs": d.tradeoffs,
                }
                for d in response.decisions
            ]

        # Atualiza contexto
        if response.context_update:
            new_context = context.copy()
            new_context.update(response.context_update)
            new_state["context"] = new_context

        # Adiciona mensagem de resumo
        new_state["messages"] = state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"⬡ {response.summary}"
            }
        ]

        new_state["architecture_recommendations"] = response.recommendations

        return new_state


# =============================================================================
# Factory
# =============================================================================

def create_architecture_agent(model: Model | str = "openai:gpt-4o-mini") -> ArchitectureAgent:
    """Cria uma instância do Architecture Agent."""
    return ArchitectureAgent(model=model)
