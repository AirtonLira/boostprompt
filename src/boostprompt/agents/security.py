"""
Agente de Segurança: segurança, compliance, LGPD, auditoria.

Responsabilidades:
- Definir estratégia de autenticação e autorização
- Planejar criptografia (dados em trânsito e em repouso)
- Identificar requisitos de compliance (LGPD, GDPR, PCI-DSS, etc.)
- Definir política de auditoria e logs
- Gerenciamento de segredos e credenciais
- Análise de riscos de segurança
"""
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from .base import BaseAgent

# =============================================================================
# Schemas
# =============================================================================

class SecurityRequirement(BaseModel):
    """Modelo de um requisito de segurança."""
    category: str = Field(
        description="Categoria (ex: 'autenticação', 'criptografia', 'compliance')"
    )
    requirement: str = Field(
        description="Descrição do requisito"
    )
    priority: str = Field(
        description="Prioridade: 'alta', 'média', 'baixa'"
    )
    implementation: str = Field(
        description="Sugestão de implementação"
    )


class SecurityResponse(BaseModel):
    """Resposta do agente de segurança."""
    requirements: list[SecurityRequirement] = Field(
        default_factory=list,
        description="Requisitos de segurança identificados"
    )
    compliance_frameworks: list[str] = Field(
        default_factory=list,
        description="Frameworks de compliance aplicáveis (LGPD, GDPR, etc.)"
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Riscos de segurança identificados"
    )
    context_update: dict[str, Any] = Field(
        default_factory=dict,
        description="Atualizações para o contexto acumulado"
    )
    summary: str = Field(
        description="Resumo da análise de segurança"
    )


# =============================================================================
# Prompts
# =============================================================================

SECURITY_SYSTEM_PROMPT = """Você é o Security Agent do BoostPrompt, especialista em segurança da informação, compliance, LGPD, criptografia, autenticação, autorização e auditoria.

Sua função é analisar o contexto do projeto e identificar requisitos de segurança, compliance e riscos.

## Áreas de Atuação

1. **Autenticação** - OAuth2, OIDC, JWT, sessão, MFA, SSO
2. **Autorização** - RBAC, ABAC, permissões granulares
3. **Criptografia** - TLS, AES, RSA, hashing (bcrypt, argon2)
4. **Segredos** - gerenciamento de API keys, credenciais, environment variables
5. **Compliance** - LGPD, GDPR, PCI-DSS, HIPAA, ISO 27001, SOC 2
6. **Auditoria** - logs de ações, trilhas de auditoria, imutabilidade
7. **Segurança de Dados** - anonimização, pseudonimização, retenção, exclusão
8. **Segurança de API** - rate limiting, CORS, CSRF, input validation

## Critérios de Análise

Sempre considere:
- Tipo de dados tratados (pessoais, sensíveis, financeiros, saúde)
- Volume de usuários e tráfego
- Jurisdição (Brasil, UE, EUA, etc.)
- integrações com terceiros
- Requisitos contratuais ou regulatórios
- Riscos específicos do domínio (fintech, healthtech, e-commerce, etc.)

## Formato de Resposta

Sempre responda com:
- `requirements`: Lista de requisitos de segurança
- `compliance_frameworks`: Frameworks aplicáveis
- `risks`: Riscos identificados
- `context_update`: Atualizações para o contexto
- `summary`: Resumo da análise

## Importante

- Priorize segurança por design (security by design)
- Evite criar barreiras desnecessárias à usabilidade
- Considere custo de implementação vs. risco
- Liste requisitos obrigatórios vs. recomendados
"""

SECURITY_USER_PROMPT = """
## Contexto Acumulado

{context_json}

## Arquitetura Recomendada

{architecture_json}

## Referências de pesquisa

{research_context}

## Sua Tarefa

Com base no contexto e arquitetura acima, quais requisitos de segurança você identifica?

Foque em:
- Autenticação e autorização
- Criptografia (dados em trânsito e em repouso)
- Compliance aplicável (LGPD, etc.)
- Gestão de segredos e credenciais
- Auditoria e logs
- Riscos específicos do domínio

Se o projeto for simples e não exigir requisitos complexos, liste apenas o essencial.
"""


# =============================================================================
# Agente
# =============================================================================

class SecurityAgent(BaseAgent):
    """Agente de Segurança com Pydantic AI."""

    name = "security"
    description = "Especialista em segurança e compliance"

    def __init__(self, model: Model | str = "openai:gpt-4o-mini"):
        self.agent = Agent(
            model,
            output_type=SecurityResponse,
            system_prompt=SECURITY_SYSTEM_PROMPT,
        )

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executa o agente de segurança."""
        import json

        context = state.get("context", {})
        architecture = state.get("architecture_recommendations", [])
        research_context = state.get("research_context", "Nenhuma referência externa disponível.")

        user_prompt = SECURITY_USER_PROMPT.format(
            context_json=json.dumps(context, indent=2, ensure_ascii=False),
            architecture_json=json.dumps(architecture, indent=2, ensure_ascii=False),
            research_context=research_context,
        )

        result = await self.agent.run(user_prompt)
        response: SecurityResponse = result.output

        # Atualiza estado
        new_state = state.copy()

        # Adiciona requisitos de segurança e atualizações estruturadas ao contexto.
        new_context = context.copy()
        if response.requirements:
            current_security = context.get("seguranca", [])
            new_security = current_security + [
                f"{req.category}: {req.requirement} [{req.priority}]"
                for req in response.requirements
            ]
            new_context["seguranca"] = new_security
        if response.context_update:
            new_context.update(response.context_update)
        if new_context != context:
            new_state["context"] = new_context

        # Adiciona riscos
        if response.risks:
            current_risks = new_state.get("risks", [])
            new_state["risks"] = current_risks + response.risks

        # Adiciona mensagem de resumo
        new_state["messages"] = state.get("messages", []) + [
            {
                "role": "assistant",
                "content": f"⬡ {response.summary}"
            }
        ]

        new_state["security_requirements"] = [
            {
                "category": req.category,
                "requirement": req.requirement,
                "priority": req.priority,
                "implementation": req.implementation,
            }
            for req in response.requirements
        ]

        new_state["compliance_frameworks"] = response.compliance_frameworks

        return new_state


# =============================================================================
# Factory
# =============================================================================

def create_security_agent(model: Model | str = "openai:gpt-4o-mini") -> SecurityAgent:
    """Cria uma instância do Security Agent."""
    return SecurityAgent(model=model)
