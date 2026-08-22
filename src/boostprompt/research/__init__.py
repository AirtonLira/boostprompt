"""Adaptadores de pesquisa externa usados pelos agentes."""

from .duckduckgo_mcp import DuckDuckGoMCPResearchProvider
from .errors import ResearchUnavailableError
from .evidence import EvidencePolicy
from .exa import ExaResearchProvider, HttpExaClient

__all__ = [
    "DuckDuckGoMCPResearchProvider",
    "EvidencePolicy",
    "ExaResearchProvider",
    "HttpExaClient",
    "ResearchUnavailableError",
]
