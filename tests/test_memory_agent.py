import pytest

from boostprompt.agents.memory import MemoryAgent, create_memory_agent
from boostprompt.agents.memory_agent import (
    MemoryAgent as CompatibilityMemoryAgent,
)
from boostprompt.agents.memory_agent import (
    create_memory_agent as compatibility_factory,
)
from boostprompt.models.schemas import SessionSummary


def test_legacy_memory_agent_module_reexports_the_canonical_implementation() -> None:
    assert CompatibilityMemoryAgent is MemoryAgent
    assert compatibility_factory is create_memory_agent


@pytest.mark.asyncio
async def test_memory_agent_lists_sessions_through_its_compatibility_api(tmp_path) -> None:
    """Evita que a fachada legada deixe de retornar uma resposta Pydantic válida."""

    agent = MemoryAgent(tmp_path / "memory.db")
    try:
        state = await agent.execute({"memory_action": "list"})
    finally:
        agent.close()

    assert state["memory_result"] == {
        "success": True,
        "message": "0 sessões encontradas.",
        "data": [],
    }


@pytest.mark.asyncio
async def test_memory_agent_rejects_summary_for_a_session_that_does_not_exist(tmp_path) -> None:
    """Evita mascarar um identificador inválido como uma sessão sem resumo."""

    agent = MemoryAgent(tmp_path / "memory.db")
    try:
        state = await agent.execute(
            {"memory_action": "summary", "session_id": "inexistente"}
        )
    finally:
        agent.close()

    assert state["memory_result"] == {
        "success": False,
        "message": "Sessão não encontrada.",
        "data": None,
    }


@pytest.mark.asyncio
async def test_memory_agent_saves_and_loads_a_session_snapshot(tmp_path) -> None:
    agent = MemoryAgent(tmp_path / "memory.db")
    try:
        saved = await agent.execute(
            {
                "memory_action": "save",
                "session_name": "Portal",
                "context": {"objetivo": "Centralizar pedidos"},
                "questions_count": 4,
            }
        )
        session_id = saved["memory_result"]["data"]["session_id"]
        agent.store.append_turn(
            session_id,
            "Criar portal.",
            "Qual público usará o portal?",
            {"objetivo": "Centralizar pedidos"},
            5,
        )
        loaded = await agent.execute({"memory_action": "load", "session_id": session_id})
    finally:
        agent.close()

    assert saved["session_id"] == session_id
    assert loaded["memory_result"]["success"] is True
    assert loaded["memory_result"]["data"]["context"] == {
        "objetivo": "Centralizar pedidos"
    }
    assert loaded["memory_result"]["data"]["messages"][-1]["content"] == (
        "Qual público usará o portal?"
    )


@pytest.mark.asyncio
async def test_memory_agent_returns_a_summary_then_deletes_the_session(tmp_path) -> None:
    agent = MemoryAgent(tmp_path / "memory.db")
    try:
        session = agent.store.create_session("CRM")
        agent.store.save_summary(
            session.id,
            SessionSummary(goal="Centralizar o relacionamento com clientes"),
        )
        summary = await agent.execute({"memory_action": "summary", "session_id": session.id})
        deleted = await agent.execute({"memory_action": "delete", "session_id": session.id})
    finally:
        agent.close()

    assert summary["memory_result"]["data"] == {
        "summary": {
            "goal": "Centralizar o relacionamento com clientes",
            "confirmed_facts": [],
            "decisions": [],
            "constraints": [],
            "risks": [],
            "covered_topics": [],
            "pending_topics": [],
            "summarized_through_sequence": 0,
        }
    }
    assert deleted["memory_result"]["success"] is True


@pytest.mark.asyncio
async def test_memory_agent_reports_an_unknown_action_without_mutating_state(tmp_path) -> None:
    agent = MemoryAgent(tmp_path / "memory.db")
    try:
        result = await agent.execute({"memory_action": "migrate"})
    finally:
        agent.close()

    assert result["memory_result"]["success"] is False
    assert result["memory_result"]["message"] == "Ação de memória desconhecida: migrate"
