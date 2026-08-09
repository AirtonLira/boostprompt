from boostprompt.memory.duckdb_store import DuckDBStore
from boostprompt.models.schemas import DiscoveryMode, SessionSummary


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

    store.save_generated_markdown(session.id, {"objetivo": "Portal"}, 10, "in_progress", "# Rascunho")

    assert store.get_messages(session.id) == before
    assert store.get_final_markdown(session.id) == "# Rascunho"
    assert store.get_session(session.id)["status"] == "in_progress"


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
