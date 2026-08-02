"""
Classe base para todos os agentes do BoostPrompt.
Cada agente especializado herdará©© desta classe.
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Classe base para agentes."""

    name: str
    description: str

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executar o agente com o estado atual."""
