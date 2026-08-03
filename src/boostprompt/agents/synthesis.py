"""
Agente de Synthesis: consolida todo o discovery no documento Markdown final.

Responsabilidades:
- Consolidar contexto acumulado
- Gerar documento Markdown completo com todas as seções
- Incluir prompt mestre para implementação
- Seguir estrutura definida na skill original
"""
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from boostprompt.models.schemas import Message

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

Sua função é consolidar todo o contexto coletado durante o discovery em um único documento Markdown completo, estruturado e implementável.

## Estrutura Obrigatória do Documento

O documento deve seguir EXATAMENTE esta estrutura:

```markdown
# Escopo da Solução

## 1. Resumo executivo
## 2. Problema e contexto
## 3. Objetivos de negócio
## 4. Público-alvo, usuários e stakeholders
## 5. Premissas e restrições
## 6. Requisitos funcionais
## 7. Requisitos não funcionais
## 8. Arquitetura recomendada
## 9. Stack tecnológica sugerida
## 10. Dados, integrações e fluxos
## 11. Segurança, privacidade e compliance
## 12. Estratégia de entrega e operação
## 13. Observabilidade, suporte e evolução
## 14. Riscos, trade-offs e mitigação
## 15. Roadmap sugerido
## 16. Decisões consolidadas
## 17. Plano de execução
## 18. Critérios de aceite
## 19. Estratégia de validação
## 20. Pendências para execução
## 21. Referências consultadas
## 22. Prompt mestre para implementação
```

## Regras Importantes

1. **Não invente informações** - use apenas o que foi coletado no discovery
2. **Seja específico** - evite generalidades, seja concreto nas recomendações
3. **Inclua trade-offs** - explicite decisões e alternativas descartadas
4. **Prompt mestre** - deve ser detalhado o suficiente para implementar sem novo discovery
5. **Português do Brasil** - todo o documento deve ser em pt-BR

## Prompt Mestre

O prompt mestre (seção 22) deve:
- Estar em Markdown
- Estar em português pt-BR
- Ser detalhado e específico
- Explicar o que construir e como construir
- Incluir restrições, trade-offs, arquitetura, stack, integrações, testes, segurança, observabilidade e entrega
- Usar exclusivamente as decisões e restrições do mesmo documento
- Não solicitar um novo discovery

## Formato de Resposta

Sempre responda com:
- `markdown_document`: O documento Markdown completo
- `summary`: Resumo executivo (2-3 frases)
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

Gere o documento Markdown completo seguindo a estrutura definida no system prompt.

Use todas as informações acima para criar um documento coerente, completo e implementável.

Não deixe seções em branco. Se alguma informação não foi coletada, indique explicitamente como pendência.
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
        import json

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
                "content": f"⬡ {response.summary}\n\nO documento Markdown completo foi gerado e está disponível para download."
            }
        ]

        return new_state

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
