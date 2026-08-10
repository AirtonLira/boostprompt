"""Contratos Pydantic compartilhados entre TUI, agentes, workflow e persistência."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DiscoveryMode(StrEnum):
    """Formato que será entregue ao concluir a demanda."""

    PROMPT_DESENVOLVIMENTO = "prompt_desenvolvimento"
    ROTEIRO_PERGUNTAS_CLIENTE = "roteiro_perguntas_cliente"


class Session(BaseModel):
    """Metadados persistidos de uma sessão de discovery."""

    id: str
    codigo: str
    nome: str
    mode: DiscoveryMode = DiscoveryMode.PROMPT_DESENVOLVIMENTO
    created_at: datetime
    updated_at: datetime
    status: str = "active"
    questions_count: int = Field(default=0, ge=0, le=50)


class Message(BaseModel):
    """Mensagem persistida e exibida em uma sessão."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)
    sequence: int | None = Field(default=None, ge=1)
    created_at: datetime | None = None


class Question(BaseModel):
    """Pergunta validada para um turno interativo de discovery."""

    number: int = Field(ge=1, le=50)
    category: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    alternatives: list[str] = Field(min_length=2, max_length=4)
    tradeoffs: str = Field(min_length=1)
    ai_recommendation: str = Field(min_length=1)
    how_to_respond: str = Field(min_length=1)


class Decision(BaseModel):
    """Decisão consolidada durante o discovery ou pelas etapas especializadas."""

    category: str
    decision: str
    alternatives: list[Any] = Field(default_factory=list)
    tradeoffs: str = ""
    rationale: str = ""


class ContextState(BaseModel):
    """Contexto estruturado acumulado em uma entrevista."""

    nome_projeto: str = ""
    necessidade: str = ""
    modo_saida: DiscoveryMode | None = None
    problema: str = ""
    objetivo: str = ""
    dominio: str = ""
    tipo_solucao: str = ""
    usuarios: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    plataformas: list[str] = Field(default_factory=list)
    restricoes: list[str] = Field(default_factory=list)
    requisitos_funcionais: list[str] = Field(default_factory=list)
    requisitos_nao_funcionais: list[str] = Field(default_factory=list)
    integracoes: list[str] = Field(default_factory=list)
    dados: list[str] = Field(default_factory=list)
    arquitetura: list[str] = Field(default_factory=list)
    seguranca: list[str] = Field(default_factory=list)
    operacao: list[str] = Field(default_factory=list)
    entrega: list[str] = Field(default_factory=list)
    riscos: list[str] = Field(default_factory=list)
    premissas: list[str] = Field(default_factory=list)
    decisoes: list[dict[str, Any]] = Field(default_factory=list)
    pendencias: list[str] = Field(default_factory=list)


class SessionSummary(BaseModel):
    """Resumo durável que mantém os fatos essenciais fora da janela recente."""

    goal: str = ""
    confirmed_facts: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    covered_topics: list[str] = Field(default_factory=list)
    pending_topics: list[str] = Field(default_factory=list)
    summarized_through_sequence: int = Field(default=0, ge=0)


class ResearchFinding(BaseModel):
    """Fonte normalizada retornada pelo MCP DuckDuckGo."""

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    excerpt: str = ""
    consulted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decision_context: str = ""


class TurnResult(BaseModel):
    """Resultado que a TUI deve renderizar depois de um turno do workflow."""

    display_message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    questions_count: int = Field(default=0, ge=0, le=50)
    awaiting_user_answer: bool
    final_markdown: str | None = None
    research_findings: list[ResearchFinding] = Field(default_factory=list)
    research_degraded: bool = False


class QuestionGuide(BaseModel):
    """Roteiro direto para o cliente, sem entrevista interativa."""

    markdown: str = Field(min_length=1)
    questions: list[Question] = Field(min_length=30, max_length=50)


class PromptQualityEvaluation(BaseModel):
    """Avaliação determinística da qualidade do contexto para um prompt."""

    applicable: bool = True
    coverage: int | None = Field(default=None, ge=0, le=100)
    decision_clarity: int | None = Field(default=None, ge=0, le=100)
    prompt_readiness: int | None = Field(default=None, ge=0, le=100)
    questions_count: int = Field(default=0, ge=0, le=50)
    status_text: str = "Aguardando contexto inicial."
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
