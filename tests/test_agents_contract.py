import pytest
from pydantic import ValidationError

from boostprompt.agents.discovery import DiscoveryAgent, DiscoveryResponse, format_question
from boostprompt.agents.question_guide import QuestionGuideAgent
from boostprompt.agents.summary import SummaryAgent
from boostprompt.agents.synthesis import SynthesisAgent, SynthesisResponse
from boostprompt.models.schemas import (
    Message,
    Question,
    QuestionGuide,
    ResearchFinding,
    SessionSummary,
)


def sample_question() -> Question:
    return Question(
        number=1,
        category="Objetivos",
        prompt="Qual resultado deve definir o sucesso da iniciativa?",
        why_it_matters="A resposta orienta escopo e critérios de aceite.",
        alternatives=["Reduzir custo", "Aumentar conversão"],
        tradeoffs="Custo e velocidade podem exigir prioridades diferentes.",
        ai_recommendation="Definir uma métrica primária mensurável.",
        how_to_respond="Escolha uma alternativa ou responda livremente.",
    )


def test_discovery_formats_the_explicit_question_text_and_tradeoffs() -> None:
    formatted = format_question(sample_question())

    assert formatted.startswith("### Pergunta 1 — Objetivos")
    assert "Qual resultado deve definir o sucesso da iniciativa?" in formatted
    assert "**Trade-offs a esclarecer:**" in formatted


def test_client_guide_rejects_an_invalid_question_count() -> None:
    with pytest.raises(ValidationError):
        QuestionGuide(markdown="# Perguntas", questions=[sample_question()] * 29)


@pytest.mark.asyncio
async def test_summary_agent_preserves_decisions_risks_and_pending_topics() -> None:
    async def fake_runner(*_args, **_kwargs) -> SessionSummary:
        return SessionSummary(
            goal="Centralizar o relacionamento com clientes",
            decisions=["Priorizar LGPD desde o desenho"],
            risks=["Dados pessoais sem base legal"],
            pending_topics=["Definir prazo de retenção"],
        )

    summary = await SummaryAgent(runner=fake_runner).summarize(
        previous=None,
        messages=[Message(role="user", content="Precisamos de um CRM.")],
        context={"necessidade": "CRM"},
    )

    assert summary.decisions == ["Priorizar LGPD desde o desenho"]
    assert summary.pending_topics == ["Definir prazo de retenção"]


@pytest.mark.asyncio
async def test_question_guide_agent_returns_the_single_client_markdown() -> None:
    async def fake_runner(*_args, **_kwargs) -> QuestionGuide:
        return QuestionGuide(
            markdown="# Perguntas para Discovery com o Cliente\n",
            questions=[sample_question()] * 30,
        )

    guide = await QuestionGuideAgent(runner=fake_runner).create_guide(
        demand="Portal de fornecedores",
        research_context="",
    )

    assert guide.markdown.startswith("# Perguntas para Discovery com o Cliente")
    assert len(guide.questions) == 30


@pytest.mark.asyncio
async def test_synthesis_includes_persisted_research_references_in_its_input() -> None:
    """Evita gerar a seção 21 sem as fontes auditáveis já consultadas."""

    class CapturingAgent:
        def __init__(self) -> None:
            self.prompt = ""

        async def run(self, prompt: str):
            self.prompt = prompt
            return type(
                "RunResult",
                (),
                {
                    "output": SynthesisResponse(
                        markdown_document="# Escopo da Solução",
                        summary="Escopo consolidado.",
                    )
                },
            )()

    synthesis = SynthesisAgent(model="test")
    runner = CapturingAgent()
    synthesis.agent = runner

    await synthesis.execute(
        {
            "context": {"necessidade": "Criar uma API"},
            "research_references": [
                ResearchFinding(
                    title="Documentação LangGraph",
                    url="https://langchain-ai.github.io/langgraph/",
                    excerpt="Referência para orquestração.",
                    decision_context="arquitetura",
                )
            ],
        }
    )

    assert "https://langchain-ai.github.io/langgraph/" in runner.prompt


@pytest.mark.asyncio
async def test_discovery_compatibility_execution_adds_exactly_one_question_to_state() -> None:
    class StaticAgent:
        async def run(self, _prompt: str):
            return type(
                "RunResult",
                (),
                {
                    "output": DiscoveryResponse(
                        question=sample_question(),
                        should_continue=True,
                        context_update={"objetivo": "Reduzir custo"},
                        summary="Objetivo registrado.",
                    )
                },
            )()

    discovery = DiscoveryAgent(model="test")
    discovery.agent = StaticAgent()

    result = await discovery.execute(
        {
            "context": {"necessidade": "Portal"},
            "messages": [{"role": "user", "content": "Criar portal."}],
            "questions_count": 3,
        }
    )

    assert result["questions_count"] == 4
    assert result["context"]["objetivo"] == "Reduzir custo"
    assert result["next_question"]["prompt"] == sample_question().prompt
    assert result["messages"][-1]["content"].startswith("### Pergunta 1")


@pytest.mark.asyncio
async def test_discovery_compatibility_execution_marks_the_interview_complete() -> None:
    class StaticAgent:
        async def run(self, _prompt: str):
            return type(
                "RunResult",
                (),
                {
                    "output": DiscoveryResponse(
                        question=None,
                        should_continue=False,
                        summary="Lacunas encerradas.",
                    )
                },
            )()

    discovery = DiscoveryAgent(model="test")
    discovery.agent = StaticAgent()

    result = await discovery.execute({"messages": [], "questions_count": 30})

    assert result["next_question"] is None
    assert result["should_continue"] is False
    assert result["messages"][-1]["content"] == "Discovery concluído. Vou consolidar o escopo final."


@pytest.mark.asyncio
async def test_summary_agent_uses_its_pydantic_ai_output_when_no_custom_runner_is_given() -> None:
    class StaticAgent:
        async def run(self, _prompt: str):
            return type(
                "RunResult",
                (),
                {"output": SessionSummary(goal="Portal de fornecedores")},
            )()

    summary_agent = SummaryAgent(model="test")
    summary_agent._agent = StaticAgent()

    summary = await summary_agent.summarize(
        previous=None,
        messages=[Message(role="user", content="Criar portal.")],
        context={},
    )

    assert summary.goal == "Portal de fornecedores"


@pytest.mark.asyncio
async def test_question_guide_uses_its_pydantic_ai_output_when_no_custom_runner_is_given() -> None:
    class StaticAgent:
        async def run(self, _prompt: str):
            return type(
                "RunResult",
                (),
                {
                    "output": QuestionGuide(
                        markdown="# Perguntas para Discovery com o Cliente\n",
                        questions=[sample_question()] * 30,
                    )
                },
            )()

    guide_agent = QuestionGuideAgent(model="test")
    guide_agent._agent = StaticAgent()

    guide = await guide_agent.create_guide(demand="Portal", research_context="")

    assert len(guide.questions) == 30
