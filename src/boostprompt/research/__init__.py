"""Adaptadores de pesquisa externa usados pelos agentes."""

from .errors import ResearchUnavailableError
from .evidence import EvidencePolicy
from .exa import ExaResearchProvider, HttpExaClient

__all__ = [
    "EvidencePolicy",
    "ExaResearchProvider",
    "HttpExaClient",
    "ResearchUnavailableError",
]
