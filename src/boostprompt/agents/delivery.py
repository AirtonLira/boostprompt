"""
Agente de Delivery: CI/CD, deploy, operação, monitoramento.

Responsabilidades:
- Definir estratégia de CI/CD (GitHub Actions, GitLab CI, etc.)
- Planejar ambientes (dev, staging, production)
- Definir estratégia de deploy (blue-green, canary, rolling)
- Especificar monitoramento e observabilidade (logs, métricas, traces)
- Planejar suporte e operação
- Definir roadmap e fases de entrega
"""
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from .base import BaseAgent

# =============================================================================
# Schemas
# =============================================================================

class DeliveryPlan(BaseModel):
    """Modelo do plano de entrega."""
    environments: list[str] = Field(
        description="Ambientes necessários (dev, staging, prod)"
    )
    ci_cd_tool: str = Field(
        description="Ferramenta de CI/CD recomendada"
    )
    deploy_strategy: str = Field(
        description="Estratégia de deploy (blue-green, canary, rolling)"
    )
    monitoring_stack: list[str] = Field(
        description="Stack de monitoramento recomendada"
    )
    phases: list[str] = Field(
        description="Fases de entrega sugeridas"
    )


class DeliveryResponse(BaseModel):
    """Resposta do agente de delivery."""
    plan: DeliveryPlan = Field(
        description="Plano de entrega e operação"
    )
    tasks: list[str] = Field(
        default_factory=list,
        description="Tarefas de setup de delivery"
    )
    context_update: dict[str, Any] = Field(
        default_factory=dict,
        description="Atualizações para o contexto acumulado"
    )
    summary: str = Field(
        description="Resumo do plano de delivery"
    )


# =============================================================================
# Prompts
# =============================================================================

DELIVERY_SYSTEM_PROMPT = """Você é o Delivery Agent do BoostPrompt, especialista em CI/CD, deploy, ambientes, monitoramento, observabilidade, suporte e operação.

Sua função é analisar o contexto do projeto e definir um plano de entrega e operação adequado.

## éreas de Atuação

1. **Ambientes** - dev, staging, production, sandbox
2. **CI/CD** - GitHub Actions, GitLab CI, CircleCI, Jenkins, ArgoCD
3. **Deploy** - blue-green, canary, rolling update, feature flags
4. **Monitoramento** - Prometheus, Grafana, Datadog, New Relic, Sentry
5. **Logs** - ELK stack, Loki, CloudWatch, Papertrail
6. **Traces** - Jaeger, Zipkin, OpenTelemetry
7. **Alertas** - PagerDuty, Opsgenie, Slack alerts
8. **Suporte** - níveis de suporte, SLA, on-call, documentação

## Critérios de Decisão

Sempre considere:
- Criticidade do sistema (downtime aceitável)
- Tamanho e habilidades do time
- Orçamento para ferramentas
- Complexidade da arquitetura
- Requisitos de compliance (auditoria de deploy, etc.)
- Volume de deploys esperado

## Formato de Resposta

Sempre responda com:
- `plan`: Plano de entrega (ambientes, CI/CD, deploy, monitoring, phases)
- `tasks`: Tarefas de setup de delivery
- `context_update`: Atualizações para o contexto
- `summary`: Resumo do plano

## Importante

- Priorize automação desde o início
- Evite ferramentas complexas demais para o tamanho do projeto
- Considere custo de ferramentas pagas vs. open-source
- Defina critérios claros de promoção entre ambientes
"""

DELIVERY_USER_PROMPT = """
## Contexto Acumulado

{context_json}

## Arquitetura Recomendada

{architecture_json}

## Referências de pesquisa

{research_context}

## Sua Tarefa

Com base no contexto e arquitetura acima, qual plano de delivery você recomenda?

Foque em:
- Ambientes necessários
- Ferramenta de CI/CD
- Estratégia de deploy
- Stack de monitoramento
- Fases de entrega

Para projetos pequenos, mantenha simples. Para projetos críticos, seja mais robusto.
"""


# =============================================================================
# Agente
# =============================================================================

class DeliveryAgent(BaseAgent):
    """Agente de Delivery com Pydantic AI."""

    name = "delivery"
    description = "Especialista em entrega e operação"

    def __init__(self, model: Model | str = "openai:gpt-4o-mini"):
        self.agent = Agent(
            model,
            output_type=DeliveryResponse,
            system_prompt=DELIVERY_SYSTEM_PROMPT,
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executa o agente de delivery."""
        import json

        context = state.get("context", {})
        architecture = state.get("architecture_recommendations", [])
        research_context = state.get("research_context", "Nenhuma referência externa disponível.")

        user_prompt = DELIVERY_USER_PROMPT.format(
            context_json=json.dumps(context, indent=2, ensure_ascii=False),
            architecture_json=json.dumps(architecture, indent=2, ensure_ascii=False),
            research_context=research_context,
        )

        result = await self.agent.run(user_prompt)
        response: DeliveryResponse = result.output

        # Atualiza estado
        new_state = state.copy()

        # Adiciona plano de delivery ao contexto
        new_context = context.copy()
        new_context["entrega"] = [
            f"Ambientes: {', '.join(response.plan.environments)}",
            f"CI/CD: {response.plan.ci_cd_tool}",
            f"Deploy: {response.plan.deploy_strategy}",
            f"Monitoramento: {', '.join(response.plan.monitoring_stack)}",
        ]
        new_context.update(response.context_update)
        new_state["context"] = new_context

        # Adiciona tarefas de delivery
        if response.tasks:
            new_state["delivery_tasks"] = response.tasks

        # Adiciona mensagem de resumo
        new_state["messages"] = state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"⬡ {response.summary}"
            }
        ]

        new_state["delivery_plan"] = response.plan.model_dump()

        return new_state


# =============================================================================
# Factory
# =============================================================================

def create_delivery_agent(model: Model | str = "openai:gpt-4o-mini") -> DeliveryAgent:
    """Cria uma instância do Delivery Agent."""
    return DeliveryAgent(model=model)
