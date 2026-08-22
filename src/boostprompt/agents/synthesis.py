"""
Agente de Synthesis: consolida todo o discovery no documento Markdown final.

Responsabilidades:
- Consolidar contexto acumulado
- Gerar documento Markdown completo com todas as seções
- Incluir prompt mestre para implementação
- Seguir estrutura definida na skill original
"""
import json
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from boostprompt.models.schemas import Message, PromptValidationReport

from .base import BaseAgent

# =============================================================================
# Schemas
# =============================================================================

class SynthesisResponse(BaseModel):
    """Resposta do agente de synthesis."""
    markdown_document: str = Field(
        description="Documento Markdown completo com o escopo da solução"
    )
    summary: str = Field(
        description="Resumo executivo do documento"
    )


# =============================================================================
# Prompts
# =============================================================================

SYNTHESIS_SYSTEM_PROMPT = """Você é o Synthesis Agent do BoostPrompt.

Consolide o discovery em um único prompt Markdown autocontido, dirigido ao agente que
implementará o sistema. Não gere um escopo separado nem repita o documento em outro
"prompt mestre".

O Markdown deve começar exatamente com `# Prompt Mestre de Implementação - <projeto>` e
conter, nesta ordem, as 22 seções abaixo, todas com conteúdo concreto:

1. Contexto e objetivo
2. Problema e contexto
3. Objetivos de negócio
4. Público-alvo, usuários e stakeholders
5. Premissas e restrições
6. Requisitos funcionais
7. Requisitos não funcionais
8. Arquitetura recomendada
9. Stack tecnológica sugerida
10. Dados, integrações e fluxos
11. Segurança, privacidade e compliance
12. Estratégia de entrega e operação
13. Observabilidade, suporte e evolução
14. Riscos, trade-offs e mitigação
15. Roadmap sugerido
16. Decisões consolidadas
17. Plano de execução
18. Critérios de aceite
19. Estratégia de validação
20. Pendências para execução
21. Referências consultadas
22. Instruções ao agente implementador

Use `## <número>. <título>` como cabeçalho de cada seção. Use listas para requisitos e
critérios observáveis, tabelas para mapeamentos com três ou mais campos e cercas de código
com linguagem para contratos técnicos. Não invente fatos: lacunas devem ser pendências.

Em referências, mantenha cada evidência com `[source_id]`, URL, data de consulta quando
disponível e a decisão que ela fundamenta. A seção 22 deve instruir diretamente a execução
e cobrir objetivo e escopo, restrições, requisitos funcionais e não funcionais, arquitetura,
dados e integrações, segurança, testes, observabilidade, entrega e critérios de aceite, sem
fazer referência a um documento acima ou a um prompt abaixo.
"""

SYNTHESIS_USER_PROMPT = """
## Contexto Acumulado do Discovery

{context_json}

## Decisões Tomadas

{decisions_json}

## Requisitos de Segurança

{security_json}

## Plano de Delivery

{delivery_json}

## Referências Consultadas

{research_json}

## Histórico da Conversa

{conversation_history}

## Sua Tarefa

Gere o único prompt Markdown de implementação seguindo a estrutura definida no system prompt.

Use todas as informações acima para criar um documento coerente, completo e implementável.

Não deixe seções em branco. Se alguma informação não foi coletada, indique explicitamente como pendência.
"""

SYNTHESIS_REPAIR_PROMPT = """## Prompt Markdown a corrigir

{markdown}

## Lacunas da validação

{report_json}

## Contexto preservado

{context_json}

Corrija o Markdown sem inventar fatos nem remover decisões ou referências válidas. Retorne
o único prompt completo com o título e as 22 seções exigidos.
"""


# =============================================================================
# Agente
# =============================================================================

class SynthesisAgent(BaseAgent):
    """Agente de Synthesis com Pydantic AI."""

    name = "synthesis"
    description = "Consolida o discovery no documento Markdown final"

    def __init__(self, model: Model | str = "openai:gpt-4o-mini"):
        self.agent = Agent(
            model,
            output_type=SynthesisResponse,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executa o agente de synthesis."""
        context = state.get("context", {})
        decisions = state.get("decisions", [])
        security = state.get("security_requirements", [])
        delivery = state.get("delivery_plan", {})
        messages = state.get("messages", [])
        research_references = state.get(
            "research_references", state.get("research_findings", [])
        )
        research = [
            reference.model_dump(mode="json")
            if isinstance(reference, BaseModel)
            else reference
            for reference in research_references
        ]

        user_prompt = SYNTHESIS_USER_PROMPT.format(
            context_json=json.dumps(context, indent=2, ensure_ascii=False),
            decisions_json=json.dumps(decisions, indent=2, ensure_ascii=False),
            security_json=json.dumps(security, indent=2, ensure_ascii=False),
            delivery_json=json.dumps(delivery, indent=2, ensure_ascii=False),
            research_json=json.dumps(research, indent=2, ensure_ascii=False),
            conversation_history=self._format_history(messages),
        )

        result = await self.agent.run(user_prompt)
        response: SynthesisResponse = result.output

        # Atualiza estado
        new_state = state.copy()
        new_state["final_markdown"] = response.markdown_document
        new_state["synthesis_summary"] = response.summary

        # Adiciona mensagem final
        new_state["messages"] = messages + [
            {
                "role": "assistant",
                "content": f"⬡ {response.summary}\n\nO prompt mestre de implementação foi gerado."
            }
        ]

        return new_state

    async def repair(
        self,
        markdown: str,
        report: PromptValidationReport,
        state: dict[str, Any],
    ) -> SynthesisResponse:
        """Corrige uma única vez um prompt recusado pela validação estrutural."""

        prompt = SYNTHESIS_REPAIR_PROMPT.format(
            markdown=markdown,
            report_json=report.model_dump_json(indent=2),
            context_json=json.dumps(state.get("context", {}), indent=2, ensure_ascii=False),
        )
        result = await self.agent.run(prompt)
        return result.output

    def _format_history(self, messages: list[Message | dict[str, Any]]) -> str:
        """Formata o histórico para exibição no prompt."""
        lines = []
        for raw_message in messages[-20:]:  # Últimas 20 mensagens
            message = (
                raw_message
                if isinstance(raw_message, Message)
                else Message.model_validate(raw_message)
            )
            role = "Usuário" if message.role == "user" else "Assistente"
            content = (
                message.content[:500] + "..."
                if len(message.content) > 500
                else message.content
            )
            lines.append(f"**{role}:** {content}")
        return "\n\n".join(lines) if lines else "Nenhuma mensagem."


# =============================================================================
# Factory
# =============================================================================

def create_synthesis_agent(model: Model | str = "openai:gpt-4o-mini") -> SynthesisAgent:
    """Cria uma instância do Synthesis Agent."""
    return SynthesisAgent(model=model)
