"""Façade de compatibilidade para operações locais de memória."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from boostprompt.memory.duckdb_store import DuckDBStore
from boostprompt.models.schemas import DiscoveryMode

from .base import BaseAgent


class MemoryResponse(BaseModel):
    """Resultado estruturado de uma operação local de memória."""

    success: bool
    message: str
    data: dict[str, Any] | list[dict[str, Any]] | None = None


class MemoryAgent(BaseAgent):
    """Mantém imports antigos enquanto o serviço centraliza persistência por turno."""

    name = "memory"
    description = "Consulta e mantém sessões locais no DuckDB"

    def __init__(self, db_path: str | Path = "data/boostprompt.db") -> None:
        self.store = DuckDBStore(db_path)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        action = state.get("memory_action") or "list"
        session_id = state.get("session_id")
        result = self._dispatch(action, session_id, state)
        new_state = state.copy()
        new_state["memory_result"] = result.model_dump()
        if result.success and action == "save" and isinstance(result.data, dict):
            session_id = result.data.get("session_id")
            if isinstance(session_id, str):
                new_state["session_id"] = session_id
        return new_state

    def _dispatch(
        self,
        action: str,
        session_id: str | None,
        state: dict[str, Any],
    ) -> MemoryResponse:
        if action == "list":
            sessions = self.store.list_sessions()
            return MemoryResponse(
                success=True,
                message=f"{len(sessions)} sessões encontradas.",
                data=sessions,
            )
        if action == "load":
            return self._load(session_id)
        if action == "summary":
            return self._summary(session_id)
        if action == "delete":
            return self._delete(session_id)
        if action == "save":
            return self._save(session_id, state)
        return MemoryResponse(success=False, message=f"Ação de memória desconhecida: {action}")

    def _load(self, session_id: str | None) -> MemoryResponse:
        if not session_id:
            return MemoryResponse(
                success=False,
                message="session_id é obrigatório para carregar uma sessão.",
            )
        try:
            resumed = self.store.load_for_resume(session_id)
        except KeyError:
            return MemoryResponse(success=False, message="Sessão não encontrada.")
        return MemoryResponse(
            success=True,
            message=f"Sessão {resumed.session.codigo} carregada.",
            data={
                "session": resumed.session.model_dump(mode="json"),
                "messages": [message.model_dump(mode="json") for message in resumed.messages],
                "context": resumed.context,
                "summary": resumed.summary.model_dump(),
                "decisions": resumed.decisions,
            },
        )

    def _summary(self, session_id: str | None) -> MemoryResponse:
        if not session_id:
            return MemoryResponse(
                success=False,
                message="session_id é obrigatório para obter o resumo.",
            )
        if self.store.get_session(session_id) is None:
            return MemoryResponse(success=False, message="Sessão não encontrada.")
        summary = self.store.get_latest_summary(session_id)
        if summary is None:
            return MemoryResponse(
                success=True,
                message="Ainda não há resumo para esta sessão.",
                data={"summary": None},
            )
        return MemoryResponse(
            success=True,
            message="Resumo da sessão recuperado.",
            data={"summary": summary.model_dump()},
        )

    def _delete(self, session_id: str | None) -> MemoryResponse:
        if not session_id or self.store.get_session(session_id) is None:
            return MemoryResponse(success=False, message="Sessão não encontrada.")
        self.store.delete_session(session_id)
        return MemoryResponse(success=True, message="Sessão removida.")

    def _save(self, session_id: str | None, state: dict[str, Any]) -> MemoryResponse:
        if session_id is None:
            mode = DiscoveryMode(state.get("mode", DiscoveryMode.PROMPT_DESENVOLVIMENTO))
            session = self.store.create_session(state.get("session_name", "Sessão sem nome"), mode)
            session_id = session.id
        context = state.get("context", {})
        questions_count = int(state.get("questions_count", 0))
        self.store.save_context_snapshot(session_id, context, questions_count)
        return MemoryResponse(
            success=True,
            message="Snapshot da sessão salvo.",
            data={"session_id": session_id},
        )

    def close(self) -> None:
        self.store.close()


def create_memory_agent(db_path: str | Path = "data/boostprompt.db") -> MemoryAgent:
    """Factory preservada para consumidores anteriores."""

    return MemoryAgent(db_path)
