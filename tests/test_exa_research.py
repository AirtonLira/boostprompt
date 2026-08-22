from datetime import UTC, datetime

import httpx
import pytest

from boostprompt.models.schemas import ResearchRequest, SourceKind
from boostprompt.research import ResearchUnavailableError
from boostprompt.research.exa import ExaResearchProvider


class StaticExaClient:
    async def search(self, request: ResearchRequest) -> dict[str, object]:
        assert request.query == "FastAPI releases"
        assert request.freshness_days == 30
        return {
            "results": [
                {
                    "title": "Notas de versão do FastAPI",
                    "url": "https://fastapi.tiangolo.com/release-notes/",
                    "publishedDate": "2026-08-01T00:00:00Z",
                    "highlights": ["Versão com melhorias de segurança."],
                    "highlightScores": [0.91],
                }
            ]
        }


class FailingExaClient:
    async def search(self, _request: ResearchRequest) -> dict[str, object]:
        request = httpx.Request("POST", "https://api.exa.ai/search")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("invalid api key: secret", request=request, response=response)


@pytest.mark.asyncio
async def test_exa_provider_normalizes_dates_highlights_and_scores() -> None:
    provider = ExaResearchProvider(client=StaticExaClient())

    findings = await provider.search(
        ResearchRequest(
            query="FastAPI releases",
            freshness_days=30,
            include_domains=["fastapi.tiangolo.com"],
        )
    )

    assert findings[0].url == "https://fastapi.tiangolo.com/release-notes/"
    assert findings[0].published_at == datetime(2026, 8, 1, tzinfo=UTC)
    assert findings[0].excerpt == "Versão com melhorias de segurança."
    assert findings[0].relevance_score == 0.91
    assert findings[0].source_kind is SourceKind.OFFICIAL


@pytest.mark.asyncio
async def test_exa_provider_hides_authentication_details_in_degraded_error() -> None:
    provider = ExaResearchProvider(client=FailingExaClient())

    with pytest.raises(ResearchUnavailableError, match="Exa") as error:
        await provider.search(ResearchRequest(query="OAuth"))

    assert "secret" not in str(error.value)
    assert "api key" not in str(error.value).casefold()
