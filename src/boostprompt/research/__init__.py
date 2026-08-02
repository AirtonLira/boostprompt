"""Adaptadores de pesquisa externa usados pelos agentes."""

from .duckduckgo_mcp import DuckDuckGoMCPResearchProvider, ResearchUnavailableError

__all__ = ["DuckDuckGoMCPResearchProvider", "ResearchUnavailableError"]
