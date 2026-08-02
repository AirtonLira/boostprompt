import asyncio

import pytest

from boostprompt.research import duckduckgo_mcp
from boostprompt.research.duckduckgo_mcp import (
    DuckDuckGoMCPResearchProvider,
    PydanticAIDuckDuckGoMCPClient,
    ResearchUnavailableError,
)


class FakeMCPClient:
    async def search(self, query: str) -> list[dict[str, str]]:
        assert query == "LangGraph persistence"
        return [
            {
                "title": "LangGraph persistence",
                "url": "https://langchain-ai.github.io/langgraph/",
                "text": "Documentação oficial",
            }
        ]


class UnavailableMCPClient:
    async def search(self, query: str) -> list[dict[str, str]]:
        raise OSError(f"Servidor indisponível para {query}")


class NoUrlMCPClient:
    async def search(self, _query: str) -> list[dict[str, str]]:
        return [{"title": "Resultado sem fonte", "text": "Sem URL utilizável."}]


@pytest.mark.asyncio
async def test_provider_normalizes_results_returned_by_duckduckgo_mcp() -> None:
    provider = DuckDuckGoMCPResearchProvider(client=FakeMCPClient())

    findings = await provider.search("LangGraph persistence")

    assert findings[0].title == "LangGraph persistence"
    assert findings[0].url.startswith("https://")
    assert findings[0].excerpt == "Documentação oficial"


@pytest.mark.asyncio
async def test_provider_raises_typed_error_when_mcp_is_unavailable() -> None:
    provider = DuckDuckGoMCPResearchProvider(client=UnavailableMCPClient())

    with pytest.raises(ResearchUnavailableError, match="DuckDuckGo"):
        await provider.search("DuckDB")


@pytest.mark.asyncio
async def test_provider_rejects_results_that_cannot_be_audited_by_url() -> None:
    """Evita que texto do MCP seja tratado como fonte sem URL verificável."""

    provider = DuckDuckGoMCPResearchProvider(client=NoUrlMCPClient())

    with pytest.raises(ResearchUnavailableError, match="fontes com URL"):
        await provider.search("LangGraph")


@pytest.mark.asyncio
async def test_real_client_invokes_the_discovered_search_tool_without_starting_a_subprocess(monkeypatch) -> None:
    """Caracteriza o adaptador stdio com um toolset em memória, isolando a rede."""

    calls = []

    class FakeTool:
        name = "ddg_search"

    class FakeToolset:
        def __init__(self, transport) -> None:
            self.transport = transport

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def list_tools(self):
            return [FakeTool()]

        async def direct_call_tool(self, name: str, arguments: dict[str, str]):
            calls.append((name, arguments))
            return {
                "results": [
                    {
                        "title": "DuckDB",
                        "url": "https://duckdb.org/docs/",
                        "text": "Documentação oficial",
                    }
                ]
            }

    monkeypatch.setattr(duckduckgo_mcp, "StdioTransport", lambda **kwargs: kwargs)
    monkeypatch.setattr(duckduckgo_mcp, "MCPToolset", FakeToolset)

    results = await PydanticAIDuckDuckGoMCPClient().search("DuckDB persistence")

    assert calls == [("ddg_search", {"query": "DuckDB persistence"})]
    assert results == [
        {
            "title": "DuckDB",
            "url": "https://duckdb.org/docs/",
            "text": "Documentação oficial",
        }
    ]


def test_client_extracts_json_records_from_mcp_text_content() -> None:
    class TextContent:
        text = '[{"title": "LangGraph", "url": "https://langchain-ai.github.io/langgraph/"}]'

    class CallResult:
        def __init__(self) -> None:
            self.content = [TextContent()]

    records = PydanticAIDuckDuckGoMCPClient._extract_records(CallResult())

    assert records == [
        {"title": "LangGraph", "url": "https://langchain-ai.github.io/langgraph/"}
    ]


@pytest.mark.asyncio
async def test_real_client_converts_a_stalled_mcp_call_to_the_degraded_mode_error(monkeypatch) -> None:
    """Evita que um subprocesso MCP travado bloqueie indefinidamente a TUI."""

    class FakeTool:
        name = "ddg_search"

    class BlockingToolset:
        def __init__(self, _transport) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def list_tools(self):
            return [FakeTool()]

        async def direct_call_tool(self, _name: str, _arguments: dict[str, str]):
            await asyncio.Future()

    monkeypatch.setattr(duckduckgo_mcp, "StdioTransport", lambda **kwargs: kwargs)
    monkeypatch.setattr(duckduckgo_mcp, "MCPToolset", BlockingToolset)
    client = PydanticAIDuckDuckGoMCPClient(timeout_seconds=0.01)

    with pytest.raises(ResearchUnavailableError, match="tempo"):
        await asyncio.wait_for(client.search("LangGraph"), timeout=0.05)
