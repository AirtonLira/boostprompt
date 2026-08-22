"""Adaptador HTTP da Exa para evidências de pesquisa auditáveis."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from boostprompt.models.schemas import ResearchFinding, ResearchRequest, SourceKind

from .errors import ResearchUnavailableError


class ExaClient(Protocol):
    """Porta pequena para testar a integração sem chamadas HTTP."""

    async def search(self, request: ResearchRequest) -> Mapping[str, Any]: ...


class HttpExaClient:
    """Cliente mínimo da API de busca Exa."""

    endpoint = "https://api.exa.ai/search"

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 15.0) -> None:
        self.api_key = api_key or os.getenv("EXA_API_KEY", "")
        self.timeout_seconds = timeout_seconds

    async def search(self, request: ResearchRequest) -> Mapping[str, Any]:
        if not self.api_key:
            raise ResearchUnavailableError("Pesquisa Exa não configurada; EXA_API_KEY ausente.")
        payload: dict[str, Any] = {
            "query": request.query,
            "numResults": request.max_results,
            "contents": {
                "highlights": {"maxCharacters": 1000},
                "text": {"maxCharacters": 2000},
            },
        }
        if request.include_domains:
            payload["includeDomains"] = request.include_domains
        if request.freshness_days is not None:
            payload["startPublishedDate"] = (
                datetime.now(UTC) - timedelta(days=request.freshness_days)
            ).isoformat()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                headers={"x-api-key": self.api_key},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        if not isinstance(body, Mapping):
            raise ResearchUnavailableError("A Exa retornou uma resposta de pesquisa inválida.")
        return body


class ExaResearchProvider:
    """Converte respostas Exa no contrato interno de pesquisa."""

    def __init__(self, client: ExaClient | None = None) -> None:
        self._client = client or HttpExaClient()

    async def search(self, request: ResearchRequest) -> list[ResearchFinding]:
        try:
            response = await self._client.search(request)
        except ResearchUnavailableError:
            raise
        except (httpx.HTTPError, OSError, RuntimeError, ValueError) as error:
            raise ResearchUnavailableError("Pesquisa Exa indisponível no momento.") from error

        raw_results = response.get("results", [])
        if not isinstance(raw_results, Sequence):
            raise ResearchUnavailableError("A Exa não retornou resultados utilizáveis.")
        findings = [
            self._to_finding(raw_result, request)
            for raw_result in raw_results
            if isinstance(raw_result, Mapping) and self._has_url(raw_result)
        ]
        if not findings:
            raise ResearchUnavailableError("A Exa não retornou fontes com URL.")
        return findings

    @staticmethod
    def _has_url(raw_result: Mapping[str, Any]) -> bool:
        return isinstance(raw_result.get("url"), str) and bool(raw_result["url"].strip())

    @classmethod
    def _to_finding(
        cls, raw_result: Mapping[str, Any], request: ResearchRequest
    ) -> ResearchFinding:
        highlights = raw_result.get("highlights")
        texts = highlights if isinstance(highlights, Sequence) and not isinstance(highlights, str) else []
        excerpt = next((str(text) for text in texts if isinstance(text, str) and text.strip()), "")
        if not excerpt:
            excerpt = str(raw_result.get("text") or raw_result.get("summary") or "")
        scores = raw_result.get("highlightScores")
        raw_score = scores[0] if isinstance(scores, Sequence) and scores else None
        score = float(raw_score) if isinstance(raw_score, (int, float)) else None
        if score is not None and not 0 <= score <= 1:
            score = None
        url = str(raw_result["url"])
        return ResearchFinding(
            title=str(raw_result.get("title") or "Resultado Exa"),
            url=url,
            excerpt=excerpt,
            query=request.query,
            published_at=cls._parse_datetime(raw_result.get("publishedDate")),
            source_kind=cls._source_kind(url, request.include_domains),
            relevance_score=score,
            decision_context=request.decision_context,
        )

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _source_kind(url: str, include_domains: Sequence[str]) -> SourceKind:
        hostname = (urlparse(url).hostname or "").casefold()
        normalized_domains = [domain.casefold().lstrip(".") for domain in include_domains]
        if any(hostname == domain or hostname.endswith(f".{domain}") for domain in normalized_domains):
            return SourceKind.OFFICIAL
        if hostname.endswith((".gov", ".edu")):
            return SourceKind.PRIMARY
        return SourceKind.UNKNOWN


__all__ = ["ExaResearchProvider", "HttpExaClient", "ResearchUnavailableError"]
