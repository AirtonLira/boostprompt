from datetime import UTC, datetime

from boostprompt.models.schemas import ResearchFinding, SourceKind
from boostprompt.research.evidence import EvidencePolicy


def test_evidence_policy_keeps_the_best_fresh_finding_per_canonical_url() -> None:
    old_duplicate = ResearchFinding(
        source_id="old",
        title="Post antigo",
        url="https://docs.example.com/guide#intro",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        source_kind=SourceKind.UNKNOWN,
        relevance_score=0.95,
    )
    official_fresh_duplicate = ResearchFinding(
        source_id="official",
        title="Documentação oficial",
        url="https://docs.example.com/guide/",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        source_kind=SourceKind.OFFICIAL,
        relevance_score=0.20,
    )
    other_source = ResearchFinding(
        source_id="other",
        title="Especificação",
        url="https://www.rfc-editor.org/rfc/rfc6749",
        source_kind=SourceKind.PRIMARY,
        relevance_score=0.50,
    )

    evidence = EvidencePolicy().select([old_duplicate, official_fresh_duplicate, other_source])

    assert [item.source_id for item in evidence] == ["official", "other"]
