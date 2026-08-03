"""Agente PydanticAI que produz a próxima pergunta de discovery."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from boostprompt.models.schemas import Message, Question

from .base import BaseAgent


class DiscoveryResponse(BaseModel):
    """Saída estruturada de um único turno de discovery."""

    question: Question | None = Field(
        default=None,
        description="Próxima pergunta; null somente quando a entrevista pode finalizar.",
    )
    should_continue: bool = Field(
        description="Indica se ainda existem lacunas relevantes para investigar.",
    )
    context_update: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(min_length=1)


DISCOVERY_SYSTEM_PROMPT = """Você é o BoostPrompt, especialista em discovery de produto e tecnologia.

Conduza uma entrevista em português do Brasil para transformar uma demanda em escopo implementável.

Regras obrigatórias:
- Gere uma única próxima pergunta por execução.
- Nunca permita encerramento antes de 30 perguntas respondidas; encerre obrigatoriamente na pergunta 50.
- Cada pergunta precisa de `prompt` explícito, categoria, justificativa, 2 a 4 alternativas, trade-offs, recomendação e instrução de resposta.
- Adapte a pergunta ao contexto, evite redundância e cubra problema, objetivos, usuários, escopo, requisitos não funcionais, dados, arquitetura, segurança e entrega.
- Não invente fatos. Registre incertezas como pendências no contexto.
"""


def format_question(question: Question) -> str:
    """Converte a pergunta estruturada no Markdown exibido na TUI."""

    alternatives = "\n\n".join(
        f"{number}. {alternative}" for number, alternative in enumerate(question.alternatives, start=1)
    )
    return f"""### Pergunta {question.number} — {question.category}

**Pergunta:**  
{question.prompt}

**Por que esta pergunta importa:**  
{question.why_it_matters}

**Alternativas:**

{alternatives}

**Trade-offs a esclarecer:**  
{question.tradeoffs}

**Recomendação da IA:**  
{question.ai_recommendation}

**Como responder:**  
{question.how_to_respond}

---

*Aguardo sua resposta para continuar.*"""


class DiscoveryAgent(BaseAgent):
    """Encapsula PydanticAI e preserva uma interface testável por turno."""

    name = "discovery"
    description = "Conduz uma entrevista de 30 a 50 perguntas estruturadas"

    def __init__(self, model: Model | str = "openai:gpt-4o-mini") -> None:
        self.agent = Agent(
            model,
            output_type=DiscoveryResponse,
            system_prompt=DISCOVERY_SYSTEM_PROMPT,
        )

    async def ask_next(
        self,
        *,
        context: dict[str, Any],
        messages: Sequence[Message | dict[str, Any]],
        questions_count: int,
        research_context: str = "",
    ) -> DiscoveryResponse:
        """Gera somente a próxima pergunta; não executa loops nem persiste dados."""

        prompt = self._render_prompt(context, messages, questions_count, research_context)
        result = await self.agent.run(prompt)
        return result.output

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Compatibilidade com nós LangGraph legados durante a migração."""

        messages = state.get("messages", [])
        questions_count = int(state.get("questions_count", 0))
        response = await self.ask_next(
            context=state.get("context", {}),
            messages=messages,
            questions_count=questions_count,
            research_context=state.get("research_context", ""),
        )
        new_state = state.copy()
        new_context = state.get("context", {}).copy()
        new_context.update(response.context_update)
        new_state["context"] = new_context
        new_state["discovery_summary"] = response.summary
        new_state["should_continue"] = response.should_continue
        if response.question is None:
            new_state["next_question"] = None
            new_state["messages"] = [
                *messages,
                {"role": "assistant", "content": "Discovery concluído. Vou consolidar o escopo final."},
            ]
            return new_state

        new_state["next_question"] = response.question.model_dump()
        new_state["questions_count"] = questions_count + 1
        new_state["messages"] = [
            *messages,
            {"role": "assistant", "content": format_question(response.question)},
        ]
        return new_state

    @staticmethod
    def _render_prompt(
        context: dict[str, Any],
        messages: Sequence[Message | dict[str, Any]],
        questions_count: int,
        research_context: str,
    ) -> str:
        history: list[str] = []
        for raw_message in messages[-10:]:
            message = (
                raw_message
                if isinstance(raw_message, Message)
                else Message.model_validate(raw_message)
            )
            speaker = "Usuário" if message.role == "user" else "Assistente"
            history.append(f"{speaker}: {message.content}")
        return f"""## Contexto acumulado
{json.dumps(context, ensure_ascii=False, indent=2)}

## Histórico recente
{chr(10).join(history) or "Nenhuma mensagem anterior."}

## Pesquisa disponível
{research_context or "Nenhuma referência externa foi usada neste turno."}

## Controle do turno
- Perguntas já exibidas: {questions_count}
- Mínimo obrigatório: 30
- Máximo obrigatório: 50

Produza uma única `DiscoveryResponse` para a próxima pergunta ou, apenas se puder finalizar após o mínimo, retorne `question: null`.
"""


def create_discovery_agent(model: Model | str = "openai:gpt-4o-mini") -> DiscoveryAgent:
    """Cria o agente de discovery configurado com o modelo solicitado."""

    return DiscoveryAgent(model=model)
