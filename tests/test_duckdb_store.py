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


def test_delete_session_removes_the_session_and_its_related_data(tmp_path) -> None:
    store = DuckDBStore(tmp_path / "sessions.db")
    session = store.create_session("Portal", DiscoveryMode.ROTEIRO_PERGUNTAS_CLIENTE)
    store.append_turn(session.id, "Portal de fornecedores", "Roteiro pronto", {}, 0)

    store.delete_session(session.id)

    assert store.get_session(session.id) is None
    assert store.get_messages(session.id) == []
