from datetime import UTC, date, datetime

import duckdb

from boostprompt.memory.duckdb_store import DuckDBStore
from boostprompt.models.schemas import (
    DiscoveryMode,
    PromptQualityEvaluation,
    ResearchFinding,
    SessionSummary,
    SourceKind,
)


def test_append_turn_is_durable_and_never_duplicates_prior_messages(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("API de pagamentos", DiscoveryMode.PROMPT_DESENVOLVIMENTO)

    store.append_turn(
        session.id,
        "Preciso cobrar clientes.",
        "Qual público utilizará a API?",
        {"necessidade": "Cobrar clientes"},
        1,
    )
    store.append_turn(
        session.id,
        "Lojistas parceiros.",
        "Qual volume diário é esperado?",
        {"usuarios": ["lojistas parceiros"]},
        2,
    )

    assert [message["content"] for message in store.get_messages(session.id)] == [
        "Preciso cobrar clientes.",
        "Qual público utilizará a API?",
        "Lojistas parceiros.",
        "Qual volume diário é esperado?",
    ]
    assert store.get_session(session.id)["questions_count"] == 2


def test_legacy_database_adds_answer_counter_with_zero_default(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    connection = duckdb.connect(str(database_path))
    connection.execute(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            codigo TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            mode TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            status TEXT NOT NULL,
            questions_count INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO sessions VALUES
        ('legacy-session', 'BP-2026-001', 'Legada', 'prompt_desenvolvimento', ?, ?, 'active', 1)
        """,
        [datetime(2026, 8, 22, tzinfo=UTC), datetime(2026, 8, 22, tzinfo=UTC)],
    )
    connection.close()

    store = DuckDBStore(database_path)
    try:
        assert store.get_session("legacy-session")["answered_questions_count"] == 0
    finally:
        store.close()


def test_research_finding_round_trips_with_stable_metadata(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("API")
    finding = ResearchFinding(
        source_id="source-1",
        title="OAuth 2.1",
        url="https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1",
        excerpt="Especificação atual.",
        query="OAuth 2.1",
        published_at=datetime(2026, 8, 1, tzinfo=UTC),
        source_kind=SourceKind.OFFICIAL,
        relevance_score=0.9,
        decision_context="autenticação",
    )

    store.save_research_findings(session.id, [finding])

    restored = store.get_research_findings(session.id)[0]
    assert restored["source_id"] == "source-1"
    assert restored["published_at"].date() == date(2026, 8, 1)
    assert restored["source_kind"] == "official"


def test_resume_uses_structured_summary_and_only_the_requested_recent_messages(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("CRM", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    store.append_turn(session.id, "Resposta 1", "Pergunta 1", {}, 1)
    store.append_turn(session.id, "Resposta 2", "Pergunta 2", {}, 2)
    store.append_turn(session.id, "Resposta 3", "Pergunta 3", {}, 3)
    store.save_summary(
        session.id,
        SessionSummary(
            goal="Centralizar o relacionamento com clientes",
            risks=["Adequação à LGPD"],
            summarized_through_sequence=4,
        ),
    )

    resumed = store.load_for_resume(session.id, recent_limit=2)

    assert resumed.summary.goal == "Centralizar o relacionamento com clientes"
    assert resumed.summary.risks == ["Adequação à LGPD"]
    assert [message.content for message in resumed.messages] == ["Resposta 3", "Pergunta 3"]


def test_partial_markdown_is_persisted_without_new_messages_and_marks_in_progress(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    store.append_turn(session.id, "Criar portal", "Pergunta 10", {"objetivo": "Portal"}, 10)
    before = store.get_messages(session.id)

    quality = PromptQualityEvaluation(prompt_readiness=73, questions_count=10)

    store.save_generated_markdown(
        session.id,
        {"objetivo": "Portal"},
        10,
        "in_progress",
        "# Rascunho",
        quality_evaluation=quality,
    )

    assert store.get_messages(session.id) == before
    assert store.get_final_markdown(session.id) == "# Rascunho"
    assert store.get_session(session.id)["status"] == "in_progress"
    assert store.get_latest_quality_evaluation(session.id).prompt_readiness == 73


def test_continuation_has_new_identity_and_only_seeded_summary(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    source = store.create_session("Portal", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    summary = SessionSummary(goal="Portal de fornecedores", decisions=["Entregar MVP"])

    continuation = store.create_continuation(source, summary)
    resumed = store.load_for_resume(continuation.id)

    assert continuation.id != source.id
    assert continuation.codigo != source.codigo
    assert continuation.status == "active"
    assert resumed.messages == []
    assert resumed.summary == summary
    assert resumed.context["sessao_origem"]["id"] == source.id


def test_existing_final_document_is_migrated_to_completed_status(tmp_path) -> None:
    database_path = tmp_path / "sessions.db"
    store = DuckDBStore(database_path)
    session = store.create_session("Portal", DiscoveryMode.PROMPT_DESENVOLVIMENTO)
    store.save_final_markdown(session.id, "# Escopo final")
    store.close()

    reopened = DuckDBStore(database_path)
    try:
        assert reopened.get_session(session.id)["status"] == "completed"
    finally:
        reopened.close()


def test_delete_session_removes_the_session_and_its_related_data(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal", DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE)
    store.append_turn(session.id, "Portal de fornecedores", "Roteiro pronto", {}, 0)

    store.delete_session(session.id)

    assert store.get_session(session.id) is None
    assert store.get_messages(session.id) == []


def test_quality_snapshot_is_persisted_with_a_turn_and_restored_on_resume(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal")
    quality = PromptQualityEvaluation(
        coverage=44,
        decision_clarity=36,
        prompt_readiness=39,
        questions_count=1,
    )

    store.append_turn(
        session.id,
        "Criar portal",
        "Pergunta 1",
        {"objetivo": "Portal"},
        1,
        quality_evaluation=quality,
    )

    restored = store.load_for_resume(session.id).quality_evaluation

    assert restored is not None
    assert (restored.coverage, restored.decision_clarity, restored.prompt_readiness) == (44, 36, 39)


def test_list_sessions_exposes_the_latest_readiness_without_breaking_legacy_sessions(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    legacy = store.create_session("Legada")
    rated = store.create_session("Avaliada")
    store.save_quality_evaluation(rated.id, PromptQualityEvaluation(prompt_readiness=61, questions_count=12))

    sessions = {item["nome"]: item for item in store.list_sessions()}

    assert sessions[legacy.nome]["prompt_readiness"] is None
    assert sessions[rated.nome]["prompt_readiness"] == 61


def test_delete_session_removes_quality_snapshots(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal")
    store.save_quality_evaluation(session.id, PromptQualityEvaluation(prompt_readiness=20))

    store.delete_session(session.id)

    assert store.get_latest_quality_evaluation(session.id) is None
