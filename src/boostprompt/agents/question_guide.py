"""Agente PydanticAI para o modo de roteiro de perguntas ao cliente."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic_ai import Agent
from pydantic_ai.models import Model

from boostprompt.models.schemas import QuestionGuide

GuideRunner = Callable[..., Awaitable[QuestionGuide]]

QUESTION_GUIDE_SYSTEM_PROMPT = """Você é o BoostPrompt no modo roteiro_perguntas_cliente.

Com base em uma demanda, gere exatamente um documento Markdown em português do Brasil que
comece com `# Perguntas para Discovery com o Cliente`. Retorne de 30 a 50 perguntas
estruturadas. Cada pergunta deve ter enunciado, contexto, alternativas quando úteis,
trade-offs e como responder. Não gere escopo técnico, plano de execução ou prompt mestre.
Não invente fatos sobre a demanda.
"""


class QuestionGuideAgent:
    """Produz diretamente o roteiro destinado ao cliente ou demandante."""

    def __init__(
        self,
        model: Model | str = "openai:gpt-4o-mini",
        runner: GuideRunner | None = None,
    ) -> None:
        self._runner = runner
        self._agent = (
            None
            if runner is not None
            else Agent(model, output_type=QuestionGuide, system_prompt=QUESTION_GUIDE_SYSTEM_PROMPT)
        )

    async def create_guide(self, *, demand: str, research_context: str) -> QuestionGuide:
        prompt = f"""## Demanda informada
{demand}

## Referências de pesquisa
{research_context or "Pesquisa indisponível; trabalhe em modo degradado."}

Gere o único Markdown e as perguntas estruturadas exigidos pelo contrato."""
        if self._runner is not None:
            return await self._runner(prompt)
        if self._agent is None:  # pragma: no cover - protege o type checker
            raise RuntimeError("QuestionGuideAgent sem executor configurado")
        result = await self._agent.run(prompt)
        return result.output
