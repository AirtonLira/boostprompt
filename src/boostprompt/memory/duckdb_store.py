"""Persistência local durável de sessões de discovery usando DuckDB."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from boostprompt.models.schemas import DiscoveryMode, Message, Session, SessionSummary


def _utc_now() -> datetime:
    """Retorna UTC como TIMESTAMP simples, compatível com DuckDB sem pytz."""

    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class ResumedSession:
    """Dados mínimos para retomar uma conversa sem reabrir todo o histórico."""

    session: Session
    messages: list[Message]
    context: dict[str, Any]
    summary: SessionSummary
    decisions: list[dict[str, Any]]
    final_markdown: str | None


class DuckDBStore:
    """Repositório transacional de sessões, mensagens, contexto e resumos."""

    def __init__(self, db_path: str | Path = "data/boostprompt.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                codigo TEXT UNIQUE NOT NULL,
                nome TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'prompt_desenvolvimento',
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                questions_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                sequence INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_snapshots (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                snapshot_data TEXT NOT NULL,
                questions_count INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                category TEXT NOT NULL,
                decision TEXT NOT NULL,
                alternatives TEXT NOT NULL,
                tradeoffs TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_summaries (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                summary_data TEXT NOT NULL,
                summarized_through_sequence INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS research_findings (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                query TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                decision_context TEXT NOT NULL,
                consulted_at TIMESTAMP NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS final_documents (
                session_id TEXT PRIMARY KEY,
                markdown TEXT NOT NULL,
                generated_at TIMESTAMP NOT NULL
            )
            """
        )
        self._migrate_existing_schema()

    def _migrate_existing_schema(self) -> None:
        """Aplica somente alterações aditivas aos bancos criados pela versão inicial."""

        self.conn.execute(
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'prompt_desenvolvimento'"
        )
        self.conn.execute(
            "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS questions_count INTEGER DEFAULT 0"
        )
        self.conn.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS sequence INTEGER")
        self.conn.execute(
            """
            UPDATE messages
            SET sequence = ranked.sequence
            FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY session_id ORDER BY created_at, id
                ) AS sequence
                FROM messages
            ) AS ranked
            WHERE messages.id = ranked.id AND messages.sequence IS NULL
            """
        )
        self._drop_legacy_session_foreign_keys()
        self.conn.execute(
            """
            UPDATE sessions
            SET status = 'completed'
            WHERE status = 'active'
              AND EXISTS (
                  SELECT 1 FROM final_documents
                  WHERE final_documents.session_id = sessions.id
              )
            """
        )

    def _drop_legacy_session_foreign_keys(self) -> None:
        """Recria sem FK as tabelas de bancos antigos (criados pelo setup_project.sh).

        DuckDB não suporta ALTER TABLE DROP CONSTRAINT e falha ao checar a FK
        quando sessão e filhos são apagados na mesma transação (delete_session),
        mesmo com os filhos já removidos antes do DELETE em sessions.
        """

        fk_tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT DISTINCT table_name FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'"
            ).fetchall()
        }
        rebuilds: dict[str, list[str]] = {
            "messages": [
                "id TEXT PRIMARY KEY",
                "session_id TEXT NOT NULL",
                "sequence INTEGER",
                "role TEXT NOT NULL",
                "content TEXT NOT NULL",
                "created_at TIMESTAMP NOT NULL",
            ],
            "context_snapshots": [
                "id TEXT PRIMARY KEY",
                "session_id TEXT NOT NULL",
                "snapshot_data TEXT NOT NULL",
                "questions_count INTEGER NOT NULL",
                "created_at TIMESTAMP NOT NULL",
            ],
            "decisions": [
                "id TEXT PRIMARY KEY",
                "session_id TEXT NOT NULL",
                "category TEXT NOT NULL",
                "decision TEXT NOT NULL",
                "alternatives TEXT NOT NULL",
                "tradeoffs TEXT NOT NULL",
                "created_at TIMESTAMP NOT NULL",
            ],
        }
        for table, column_defs in rebuilds.items():
            if table not in fk_tables:
                continue
            column_names = ", ".join(definition.split()[0] for definition in column_defs)
            self.conn.execute(f"DROP TABLE IF EXISTS {table}_no_fk")
            self.conn.execute(f"CREATE TABLE {table}_no_fk ({', '.join(column_defs)})")
            self.conn.execute(f"INSERT INTO {table}_no_fk SELECT {column_names} FROM {table}")
            self.conn.execute(f"DROP TABLE {table}")
            self.conn.execute(f"ALTER TABLE {table}_no_fk RENAME TO {table}")

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Agrupa um turno inteiro para evitar histórico parcialmente salvo."""

        self.conn.execute("BEGIN TRANSACTION")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    def create_session(
        self,
        nome: str,
        mode: DiscoveryMode = DiscoveryMode.PROMPT_DESENVOLVIMENTO,
    ) -> Session:
        """Cria a sessão antes da primeira chamada de agente."""

        now = _utc_now()
        session = Session(
            id=str(uuid.uuid4()),
            codigo=f"BP-{now.year}-{self._get_next_code(now.year)}",
            nome=nome,
            mode=mode,
            created_at=now,
            updated_at=now,
        )
        with self.transaction():
            self._insert_session(session)
        return session

    def _insert_session(self, session: Session) -> None:
        self.conn.execute(
            """
            INSERT INTO sessions (
                id, codigo, nome, mode, created_at, updated_at, status, questions_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                session.id,
                session.codigo,
                session.nome,
                session.mode.value,
                session.created_at,
                session.updated_at,
                session.status,
                session.questions_count,
            ],
        )

    def _get_next_code(self, year: int) -> str:
        row = self.conn.execute(
            """
            SELECT COALESCE(MAX(CAST(SPLIT_PART(codigo, '-', 3) AS INTEGER)), 0) + 1
            FROM sessions
            WHERE codigo LIKE ?
            """,
            [f"BP-{year}-%"],
        ).fetchone()
        if row is None:  # pragma: no cover - agregação sempre retorna uma linha no DuckDB
            raise RuntimeError("Não foi possível calcular o próximo código de sessão.")
        return f"{int(row[0]):03d}"

    def append_turn(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        context: dict[str, Any],
        questions_count: int,
        final_markdown: str | None = None,
    ) -> None:
        """Persiste exatamente a resposta e a saída do turno atual."""

        if not self.get_session(session_id):
            raise KeyError(f"Sessão {session_id} não encontrada")

        with self.transaction():
            self._append_message(session_id, "user", user_content)
            self._append_message(session_id, "assistant", assistant_content)
            self._save_context_snapshot(session_id, context, questions_count)
            self.conn.execute(
                """
                UPDATE sessions
                SET updated_at = ?, questions_count = ?
                WHERE id = ?
                """,
                [_utc_now(), questions_count, session_id],
            )
            if final_markdown is not None:
                self._save_final_markdown(session_id, final_markdown)

    def _append_message(self, session_id: str, role: str, content: str) -> None:
        sequence = self._next_message_sequence(session_id)
        self.conn.execute(
            """
            INSERT INTO messages (id, session_id, sequence, role, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [str(uuid.uuid4()), session_id, sequence, role, content, _utc_now()],
        )

    def _next_message_sequence(self, session_id: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM messages WHERE session_id = ?",
            [session_id],
        ).fetchone()
        if row is None:  # pragma: no cover - agregação sempre retorna uma linha no DuckDB
            raise RuntimeError("Não foi possível calcular a próxima sequência de mensagem.")
        return int(row[0])

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT role, content, sequence, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY sequence ASC
            """,
            [session_id],
        ).fetchall()
        return [
            {
                "role": row[0],
                "content": row[1],
                "sequence": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    def get_messages_summary(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Compatibilidade: retorna a janela recente em ordem cronológica."""

        return [message.model_dump() for message in self._get_recent_messages(session_id, limit)]

    def _get_recent_messages(self, session_id: str, limit: int) -> list[Message]:
        rows = self.conn.execute(
            """
            SELECT role, content, sequence, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY sequence DESC
            LIMIT ?
            """,
            [session_id, limit],
        ).fetchall()
        return [
            Message(role=row[0], content=row[1], sequence=row[2], created_at=row[3])
            for row in reversed(rows)
        ]

    def get_messages_after_sequence(self, session_id: str, sequence: int) -> list[Message]:
        """Recupera mensagens ainda não condensadas, em ordem cronológica."""

        rows = self.conn.execute(
            """
            SELECT role, content, sequence, created_at
            FROM messages
            WHERE session_id = ? AND sequence > ?
            ORDER BY sequence ASC
            """,
            [session_id, sequence],
        ).fetchall()
        return [
            Message(role=row[0], content=row[1], sequence=row[2], created_at=row[3])
            for row in rows
        ]

    def save_context_snapshot(
        self,
        session_id: str,
        context: dict[str, Any],
        questions_count: int,
    ) -> None:
        with self.transaction():
            self._save_context_snapshot(session_id, context, questions_count)

    def _save_context_snapshot(
        self,
        session_id: str,
        context: dict[str, Any],
        questions_count: int,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO context_snapshots (id, session_id, snapshot_data, questions_count, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                session_id,
                json.dumps(context, ensure_ascii=False),
                questions_count,
                _utc_now(),
            ],
        )

    def save_final_markdown(self, session_id: str, markdown: str) -> None:
        """Persiste o artefato de escopo para disponibilizá-lo em retomadas futuras."""

        with self.transaction():
            self._save_final_markdown(session_id, markdown)

    def save_generated_markdown(
        self,
        session_id: str,
        context: dict[str, Any],
        questions_count: int,
        status: str,
        markdown: str,
    ) -> None:
        """Persiste um documento gerado sem acrescentar uma mensagem ao histórico."""

        if not self.get_session(session_id):
            raise KeyError(f"Sessão {session_id} não encontrada")
        with self.transaction():
            self._save_context_snapshot(session_id, context, questions_count)
            self._save_final_markdown(session_id, markdown)
            self.set_session_status(session_id, status)

    def _save_final_markdown(self, session_id: str, markdown: str) -> None:
        self.conn.execute("DELETE FROM final_documents WHERE session_id = ?", [session_id])
        self.conn.execute(
            """
            INSERT INTO final_documents (session_id, markdown, generated_at)
            VALUES (?, ?, ?)
            """,
            [session_id, markdown, _utc_now()],
        )

    def set_session_status(self, session_id: str, status: str) -> None:
        self.conn.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            [status, _utc_now(), session_id],
        )

    def get_final_markdown(self, session_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT markdown FROM final_documents WHERE session_id = ?",
            [session_id],
        ).fetchone()
        return str(row[0]) if row else None

    def get_latest_context(self, session_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT snapshot_data FROM context_snapshots
            WHERE session_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            [session_id],
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_summary(self, session_id: str, summary: SessionSummary) -> None:
        with self.transaction():
            self._save_summary(session_id, summary)

    def _save_summary(self, session_id: str, summary: SessionSummary) -> None:
        self.conn.execute(
            """
            INSERT INTO session_summaries (
                id, session_id, summary_data, summarized_through_sequence, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                session_id,
                summary.model_dump_json(),
                summary.summarized_through_sequence,
                _utc_now(),
            ],
        )

    def create_continuation(self, source: Session, summary: SessionSummary) -> Session:
        """Cria uma sessão nova com apenas o contexto compacto da sessão concluída."""

        now = _utc_now()
        continuation = Session(
            id=str(uuid.uuid4()),
            codigo=f"BP-{now.year}-{self._get_next_code(now.year)}",
            nome=f"{source.nome} — continuação",
            mode=source.mode,
            created_at=now,
            updated_at=now,
        )
        context = {
            "sessao_origem": {
                "id": source.id,
                "codigo": source.codigo,
                "nome": source.nome,
            }
        }
        with self.transaction():
            self._insert_session(continuation)
            self._save_summary(continuation.id, summary)
            self._save_context_snapshot(continuation.id, context, 0)
        return continuation

    def get_latest_summary(self, session_id: str) -> SessionSummary | None:
        row = self.conn.execute(
            """
            SELECT summary_data FROM session_summaries
            WHERE session_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            [session_id],
        ).fetchone()
        return SessionSummary.model_validate_json(row[0]) if row else None

    def save_research_findings(
        self,
        session_id: str,
        query: str,
        findings: Sequence[Any],
    ) -> None:
        """Mantém as fontes usadas em uma decisão para a seção de referências."""

        with self.transaction():
            for finding in findings:
                self.conn.execute(
                    """
                    INSERT INTO research_findings (
                        id, session_id, query, title, url, excerpt, decision_context, consulted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        str(uuid.uuid4()),
                        session_id,
                        query,
                        finding.title,
                        finding.url,
                        finding.excerpt,
                        finding.decision_context,
                        finding.consulted_at.replace(tzinfo=None),
                    ],
                )

    def get_research_findings(self, session_id: str) -> list[dict[str, Any]]:
        """Recupera referências auditáveis para síntese e retomada da sessão."""

        rows = self.conn.execute(
            """
            SELECT query, title, url, excerpt, decision_context, consulted_at
            FROM research_findings
            WHERE session_id = ?
            ORDER BY consulted_at ASC, id ASC
            """,
            [session_id],
        ).fetchall()
        return [
            {
                "query": row[0],
                "title": row[1],
                "url": row[2],
                "excerpt": row[3],
                "decision_context": row[4],
                "consulted_at": row[5],
            }
            for row in rows
        ]

    def load_for_resume(self, session_id: str, recent_limit: int = 10) -> ResumedSession:
        session_data = self.get_session(session_id)
        if session_data is None:
            raise KeyError(f"Sessão {session_id} não encontrada")
        return ResumedSession(
            session=Session.model_validate(session_data),
            messages=self._get_recent_messages(session_id, recent_limit),
            context=self.get_latest_context(session_id) or {},
            summary=self.get_latest_summary(session_id) or SessionSummary(),
            decisions=self.get_decisions(session_id),
            final_markdown=self.get_final_markdown(session_id),
        )

    def save_decision(
        self,
        session_id: str,
        category: str,
        decision: str,
        alternatives: Sequence[Any],
        tradeoffs: str,
    ) -> None:
        with self.transaction():
            self.conn.execute(
                """
                INSERT INTO decisions (id, session_id, category, decision, alternatives, tradeoffs, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    session_id,
                    category,
                    decision,
                    json.dumps(list(alternatives), ensure_ascii=False),
                    tradeoffs,
                    _utc_now(),
                ],
            )

    def get_decisions(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT category, decision, alternatives, tradeoffs
            FROM decisions
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            [session_id],
        ).fetchall()
        return [
            {
                "category": row[0],
                "decision": row[1],
                "alternatives": json.loads(row[2]),
                "tradeoffs": row[3],
            }
            for row in rows
        ]

    def list_sessions(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT id, codigo, nome, mode, created_at, updated_at, status, questions_count
            FROM sessions
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        return [self._session_dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT id, codigo, nome, mode, created_at, updated_at, status, questions_count
            FROM sessions
            WHERE id = ?
            """,
            [session_id],
        ).fetchone()
        return self._session_dict(row) if row else None

    @staticmethod
    def _session_dict(row: Sequence[Any]) -> dict[str, Any]:
        mode_value = row[3] or DiscoveryMode.PROMPT_DESENVOLVIMENTO.value
        try:
            mode = DiscoveryMode(mode_value).value
        except ValueError:
            mode = DiscoveryMode.PROMPT_DESENVOLVIMENTO.value
        return {
            "id": row[0],
            "codigo": row[1],
            "nome": row[2],
            "mode": mode,
            "created_at": row[4],
            "updated_at": row[5],
            "status": row[6],
            "questions_count": row[7] or 0,
        }

    def delete_session(self, session_id: str) -> None:
        with self.transaction():
            for table in (
                "research_findings",
                "final_documents",
                "session_summaries",
                "decisions",
                "context_snapshots",
                "messages",
            ):
                self.conn.execute(f"DELETE FROM {table} WHERE session_id = ?", [session_id])
            self.conn.execute("DELETE FROM sessions WHERE id = ?", [session_id])

    def close(self) -> None:
        self.conn.close()
