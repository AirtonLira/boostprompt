"""Agente que decide se uma pesquisa externa agrega ao proximo turno."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model

from boostprompt.models.schemas import Message, ResearchPlan

PlannerRunner = Callable[..., Awaitable[ResearchPlan]]

RESEARCH_PLANNER_SYSTEM_PROMPT = """Você é o planejador de pesquisa do BoostPrompt.

Decida se evidências externas recentes ajudam a formular a próxima pergunta de discovery.

Regras obrigatórias:
- Retorne no máximo duas consultas estruturadas.
- Pesquise apenas decisões externas e verificáveis, como padrões técnicos, segurança,
  conformidade, mercado ou fatos recentes.
- Não pesquise prioridades de negócio, orçamento, preferências internas ou fatos que o
  usuário precisa confirmar.
- Use `freshness_days` somente quando a atualidade altera a decisão.
- Prefira domínios oficiais ou primários em `include_domains` quando eles forem conhecidos.
- Quando não houver pesquisa útil, retorne `requests: []`.
"""


class ResearchPlannerAgent:
    """Planeja pesquisas pequenas antes de cada pergunta de discovery."""

    def __init__(
        self,
        model: Model | str = "openai:gpt-4o-mini",
        runner: PlannerRunner | None = None,
    ) -> None:
        self._runner = runner
        self._agent = (
            None
            if runner is not None
            else Agent(model, output_type=ResearchPlan, system_prompt=RESEARCH_PLANNER_SYSTEM_PROMPT)
        )

    async def plan(
        self,
        *,
        context: dict[str, Any],
        messages: Sequence[Message | dict[str, Any]],
        questions_count: int,
    ) -> ResearchPlan:
        prompt = self._render_prompt(context, messages, questions_count)
        if self._runner is not None:
            return await self._runner(prompt)
        if self._agent is None:  # pragma: no cover - protege o type checker
            raise RuntimeError("ResearchPlannerAgent sem executor configurado")
        result = await self._agent.run(prompt)
        return result.output

    @staticmethod
    def _render_prompt(
        context: dict[str, Any],
        messages: Sequence[Message | dict[str, Any]],
        questions_count: int,
    ) -> str:
        history = []
        for raw_message in messages[-10:]:
            message = (
                raw_message if isinstance(raw_message, Message) else Message.model_validate(raw_message)
            )
            speaker = "Usuário" if message.role == "user" else "Assistente"
            history.append(f"{speaker}: {message.content}")
        return f"""## Contexto acumulado
{json.dumps(context, ensure_ascii=False, indent=2)}

## Histórico recente
{chr(10).join(history) or "Nenhuma mensagem anterior."}

## Controle do turno
- Perguntas já exibidas: {questions_count}

Planeje somente a pesquisa externa que aumenta a qualidade da próxima pergunta.
"""
