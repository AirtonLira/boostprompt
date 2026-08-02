"""
Prompts para o agente de Discovery.
"""

DISCOVERY_INTRO = """Olá! Eu sou o BoostPrompt e vou te ajudar a transformar sua necessidade em um escopo completo, atualizado e implementável.

Vou conduzir uma entrevista estruturada com no mínimo 30 e no máximo 50 perguntas. Em cada etapa, vou trazer alternativas, explicar trade-offs e recomendar a melhor direção com base no seu contexto e, quando disponível, em referências atuais obtidas por pesquisa.

Para começar, descreva a necessidade, ideia ou problema que você quer transformar em solução."""

QUESTION_TEMPLATE = """### Pergunta {number} — {category}

**Por que esta pergunta importa:**  
{why_it_matters}

**Alternativas:**

{alternatives}

**Recomendação da IA:**  
{ai_recommendation}

**Como responder:**  
{how_to_respond}"""
