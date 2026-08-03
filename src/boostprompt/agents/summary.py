"""Agente PydanticAI para resumir sessões sem perder decisões importantes."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model

from boostprompt.models.schemas import Message, SessionSummary

SummaryRunner = Callable[..., Awaitable[SessionSummary]]

SUMMARY_SYSTEM_PROMPT = """Você resume uma entrevista de discovery em português do Brasil.

Preserve somente fatos confirmados e os pontos que permitem retomar a conversa: objetivo,
decisões, restrições, riscos, blocos já cobertos e pendências. Não invente informação.
"""


class SummaryAgent:
    """Condensa histórico antigo e produz um resumo Pydantic persistível."""

    def __init__(
        self,
        model: Model | str = "openai:gpt-4o-mini",
        runner: SummaryRunner | None = None,
    ) -> None:
        self._runner = runner
        self._agent = (
            None
            if runner is not None
            else Agent(model, output_type=SessionSummary, system_prompt=SUMMARY_SYSTEM_PROMPT)
        )

    async def summarize(
        self,
        *,
        previous: SessionSummary | None,
        messages: Sequence[Message],
        context: dict[str, Any],
    ) -> SessionSummary:
        prompt = self._render_prompt(previous, messages, context)
        if self._runner is not None:
            return await self._runner(prompt)
        if self._agent is None:  # pragma: no cover - protege o type checker
            raise RuntimeError("SummaryAgent sem executor configurado")
        result = await self._agent.run(prompt)
        return result.output

    @staticmethod
    def _render_prompt(
        previous: SessionSummary | None,
        messages: Sequence[Message],
        context: dict[str, Any],
    ) -> str:
        history = "\n".join(f"{message.role}: {message.content}" for message in messages)
        return f"""## Resumo anterior
{previous.model_dump_json(indent=2) if previous else "Nenhum"}

## Contexto estruturado
{json.dumps(context, ensure_ascii=False, indent=2)}

## Mensagens a condensar
{history or "Nenhuma"}

Produza `SessionSummary` com os principais pontos e sem omitir pendências ou riscos."""
