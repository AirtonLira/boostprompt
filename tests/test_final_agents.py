import pytest

from boostprompt.agents.architecture import (
    ArchitectureAgent,
    ArchitectureDecision,
    ArchitectureResponse,
)
from boostprompt.agents.delivery import DeliveryAgent, DeliveryPlan, DeliveryResponse
from boostprompt.agents.security import SecurityAgent, SecurityResponse
from boostprompt.agents.synthesis import SynthesisAgent, SynthesisResponse
from boostprompt.models.schemas import Message


class StaticRunAgent:
    """Substitui somente a chamada remota, preservando a transformação local do agente."""

    def __init__(self, data) -> None:
        self.output = data
        self.prompts: list[str] = []

    async def run(self, prompt: str):
        self.prompts.append(prompt)
        return type("RunResult", (), {"output": self.output})()


@pytest.mark.asyncio
async def test_architecture_agent_merges_decisions_context_and_recommendations() -> None:
    agent = ArchitectureAgent(model="test")
    agent.agent = StaticRunAgent(
        ArchitectureResponse(
            decisions=[
                ArchitectureDecision(
                    category="api",
                    decision="REST com FastAPI",
                    alternatives=["GraphQL"],
                    rationale="Time já domina Python.",
                    tradeoffs="Menos flexível para consultas ad hoc.",
                )
            ],
            recommendations=["Começar com monólito modular."],
            context_update={"arquitetura": ["FastAPI", "PostgreSQL"]},
            summary="A arquitetura inicial foi definida.",
        )
    )

    result = await agent.execute(
        {
            "context": {"necessidade": "Portal"},
            "decisions": [{"category": "escopo", "decision": "MVP"}],
            "research_context": "- [source-1] FastAPI\n  URL: https://fastapi.tiangolo.com/",
            "messages": [{"role": "user", "content": "Criar portal."}],
        }
    )

    assert result["decisions"][-1]["decision"] == "REST com FastAPI"
    assert result["context"]["arquitetura"] == ["FastAPI", "PostgreSQL"]
    assert result["architecture_recommendations"] == ["Começar com monólito modular."]
    assert result["messages"][-1]["content"].endswith("A arquitetura inicial foi definida.")
    assert "source-1" in agent.agent.prompts[0]


@pytest.mark.asyncio
async def test_security_agent_keeps_context_updates_even_without_new_requirements() -> None:
    """Evita descartar fatos de segurança quando o agente não cria um requisito formal."""

    agent = SecurityAgent(model="test")
    agent.agent = StaticRunAgent(
        SecurityResponse(
            requirements=[],
            compliance_frameworks=["LGPD"],
            risks=["Base legal ainda não confirmada"],
            context_update={"retencao": "Definir prazo com o jurídico"},
            summary="Há uma pendência regulatória.",
        )
    )

    result = await agent.execute(
        {
            "context": {"necessidade": "CRM"},
            "research_context": "- [source-1] LGPD\n  URL: https://www.gov.br/",
            "messages": [{"role": "user", "content": "Precisamos de um CRM."}],
        }
    )

    assert result["context"]["retencao"] == "Definir prazo com o jurídico"
    assert result["risks"] == ["Base legal ainda não confirmada"]
    assert result["compliance_frameworks"] == ["LGPD"]
    assert "source-1" in agent.agent.prompts[0]


@pytest.mark.asyncio
async def test_synthesis_formats_pydantic_messages_received_from_the_session_service() -> None:
    """Evita erro ao finalizar sessões cujo histórico vem do repositório tipado."""

    agent = SynthesisAgent(model="test")
    runner = StaticRunAgent(
        SynthesisResponse(markdown_document="# Escopo", summary="Escopo consolidado.")
    )
    agent.agent = runner

    await agent.execute(
        {"messages": [Message(role="user", content="Precisamos de um portal.")]}
    )

    assert "**Usuário:** Precisamos de um portal." in runner.prompts[0]


@pytest.mark.asyncio
async def test_delivery_agent_persists_the_operational_plan_in_context() -> None:
    agent = DeliveryAgent(model="test")
    agent.agent = StaticRunAgent(
        DeliveryResponse(
            plan=DeliveryPlan(
                environments=["desenvolvimento", "produção"],
                ci_cd_tool="GitHub Actions",
                deploy_strategy="rolling update",
                monitoring_stack=["OpenTelemetry", "Grafana"],
                phases=["MVP", "Evolução"],
            ),
            tasks=["Configurar pipeline de testes."],
            context_update={"slo": "99,5%"},
            summary="Plano de entrega definido.",
        )
    )

    result = await agent.execute(
        {
            "context": {"necessidade": "Portal"},
            "research_context": "- [source-1] OpenTelemetry\n  URL: https://opentelemetry.io/",
            "messages": [],
        }
    )

    assert result["context"]["entrega"] == [
        "Ambientes: desenvolvimento, produção",
        "CI/CD: GitHub Actions",
        "Deploy: rolling update",
        "Monitoramento: OpenTelemetry, Grafana",
    ]
    assert result["context"]["slo"] == "99,5%"
    assert result["delivery_tasks"] == ["Configurar pipeline de testes."]
    assert result["delivery_plan"]["ci_cd_tool"] == "GitHub Actions"
    assert "source-1" in agent.agent.prompts[0]


@pytest.mark.asyncio
async def test_synthesis_returns_the_final_markdown_and_a_download_message() -> None:
    agent = SynthesisAgent(model="test")
    agent.agent = StaticRunAgent(
        SynthesisResponse(
            markdown_document="# Prompt Mestre de Implementação - Portal\n\n## 1. Contexto e objetivo",
            summary="Prompt pronto para implementação.",
        )
    )

    result = await agent.execute({"messages": []})

    assert result["final_markdown"].startswith("# Prompt Mestre de Implementação")
    assert result["synthesis_summary"] == "Prompt pronto para implementação."
    assert "prompt mestre de implementação foi gerado" in result["messages"][-1]["content"]
