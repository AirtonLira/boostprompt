"""Política local e determinística para evidências retornadas por pesquisa."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import urlsplit, urlunsplit

from boostprompt.models.schemas import ResearchFinding, SourceKind


class EvidencePolicy:
    """Remove duplicatas e prioriza fontes mais úteis antes de chamar agentes."""

    max_findings = 8
    _priority: ClassVar[dict[SourceKind, int]] = {
        SourceKind.OFFICIAL: 0,
        SourceKind.PRIMARY: 1,
        SourceKind.REPUTABLE: 2,
        SourceKind.COMMUNITY: 3,
        SourceKind.UNKNOWN: 4,
    }

    def select(self, findings: Sequence[ResearchFinding]) -> list[ResearchFinding]:
        best_by_url: dict[str, ResearchFinding] = {}
        for finding in findings:
            canonical_url = self._canonical_url(finding.url)
            current = best_by_url.get(canonical_url)
            if current is None or self._rank(finding) < self._rank(current):
                best_by_url[canonical_url] = finding
        return sorted(best_by_url.values(), key=self._rank)[: self.max_findings]

    @staticmethod
    def _canonical_url(url: str) -> str:
        parts = urlsplit(url)
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, parts.query, ""))

    def _rank(self, finding: ResearchFinding) -> tuple[int, float, float, str]:
        published_at = finding.published_at or datetime.min.replace(tzinfo=UTC)
        score = finding.relevance_score if finding.relevance_score is not None else 0.0
        return (
            self._priority[finding.source_kind],
            -published_at.timestamp(),
            -score,
            finding.url,
        )
