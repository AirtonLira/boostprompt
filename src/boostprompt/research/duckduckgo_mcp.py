"""Pesquisa opcional por meio do servidor stdio MCP DuckDuckGo."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Protocol

from pydantic_ai.mcp import MCPError, MCPToolset, StdioTransport  # type: ignore[attr-defined]

from boostprompt.models.schemas import ResearchFinding


class ResearchUnavailableError(RuntimeError):
    """Indica indisponibilidade do servidor MCP, sem invalidar a sessão local."""


class MCPResearchClient(Protocol):
    """Porta mínima para permitir testes sem iniciar um subprocesso MCP."""

    async def search(self, query: str) -> list[Mapping[str, Any]]: ...


class PydanticAIDuckDuckGoMCPClient:
    """Cliente real que inicia o servidor configurado pelo instalador do projeto."""

    command: ClassVar[str] = "uvx"
    args: ClassVar[list[str]] = ["duckduckgo-mcp-server"]
    default_timeout_seconds: ClassVar[float] = 15.0

    def __init__(self, timeout_seconds: float = default_timeout_seconds) -> None:
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str) -> list[Mapping[str, Any]]:
        try:
            return await asyncio.wait_for(
                self._search_with_mcp(query), timeout=self.timeout_seconds
            )
        except TimeoutError as error:
            raise ResearchUnavailableError(
                "O MCP DuckDuckGo excedeu o tempo limite de pesquisa."
            ) from error

    async def _search_with_mcp(self, query: str) -> list[Mapping[str, Any]]:
        transport = StdioTransport(command=self.command, args=self.args)
        async with MCPToolset(transport) as toolset:
            tool_name = self._search_tool_name(await toolset.list_tools())
            result = await toolset.direct_call_tool(tool_name, {"query": query})
        records = self._extract_records(result)
        if not records:
            raise ResearchUnavailableError("O MCP DuckDuckGo não retornou resultados utilizáveis.")
        return records

    @staticmethod
    def _search_tool_name(tools: Sequence[Any]) -> str:
        for tool in tools:
            name = str(tool.name)
            if "search" in name.lower():
                return name
        raise ResearchUnavailableError("O MCP DuckDuckGo não expôs uma ferramenta de busca.")

    @classmethod
    def _extract_records(cls, value: Any) -> list[Mapping[str, Any]]:
        if isinstance(value, Mapping):
            for key in ("results", "items", "data"):
                nested = value.get(key)
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, Mapping)]
            return [value]
        if isinstance(value, list):
            mappings = [item for item in value if isinstance(item, Mapping)]
            if mappings:
                return mappings
        content = getattr(value, "content", None)
        if isinstance(content, list):
            return cls._extract_content_records(content)
        return []

    @staticmethod
    def _extract_content_records(content: Sequence[Any]) -> list[Mapping[str, Any]]:
        records: list[Mapping[str, Any]] = []
        for item in content:
            text = getattr(item, "text", None)
            if not isinstance(text, str):
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                records.extend(entry for entry in parsed if isinstance(entry, Mapping))
            elif isinstance(parsed, Mapping):
                records.append(parsed)
        return records


class DuckDuckGoMCPResearchProvider:
    """Normaliza os resultados do MCP no contrato usado pelos agentes."""

    def __init__(self, client: MCPResearchClient | None = None) -> None:
        self._client = client or PydanticAIDuckDuckGoMCPClient()

    async def search(self, query: str, decision_context: str = "") -> list[ResearchFinding]:
        try:
            raw_results = await self._client.search(query)
        except ResearchUnavailableError:
            raise
        except (MCPError, OSError, RuntimeError, ValueError) as error:
            raise ResearchUnavailableError("Pesquisa DuckDuckGo indisponível via MCP.") from error

        findings = [
            self._to_finding(result, decision_context)
            for result in raw_results
            if self._has_url(result)
        ]
        if not findings:
            raise ResearchUnavailableError("Pesquisa DuckDuckGo não retornou fontes com URL.")
        return findings

    @staticmethod
    def _has_url(result: Mapping[str, Any]) -> bool:
        return bool(result.get("url") or result.get("link") or result.get("href"))

    @staticmethod
    def _to_finding(result: Mapping[str, Any], decision_context: str) -> ResearchFinding:
        return ResearchFinding(
            title=str(result.get("title") or result.get("name") or "Resultado DuckDuckGo"),
            url=str(result.get("url") or result.get("link") or result.get("href")),
            excerpt=str(result.get("text") or result.get("excerpt") or result.get("description") or ""),
            decision_context=decision_context,
        )
