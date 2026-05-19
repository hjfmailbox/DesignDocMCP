"""SQLite-based storage backend for DesignDoc MCP.

Replaces the JSON file-based SessionStore with a relational SQLite backend
that supports event sourcing, task inbox (blocking pull), and single
active-session constraint.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    AgentInfo,
    Assumption,
    AssumptionAlternative,
    Challenge,
    ChallengeCategory,
    ChallengePriority,
    ConsensusVote,
    DebatePhase,
    DevilsAdvocate,
    Event,
    EventType,
    MergedAssumptionGroup,
    Optimization,
    PendingQuestion,
    Proposal,
    QuestionOption,
    RefinedRequirement,
    Requirement,
    Revision,
    Session,
    SessionStatus,
    VoteType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- 会话表
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    current_phase TEXT NOT NULL DEFAULT 'clarify_identify',
    current_round INTEGER NOT NULL DEFAULT 1,
    min_rounds INTEGER NOT NULL DEFAULT 4,
    max_rounds INTEGER NOT NULL DEFAULT 8,
    clarify_round INTEGER NOT NULL DEFAULT 1,
    devils_advocate_agent TEXT NOT NULL DEFAULT '',
    requirement_json TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    archived_at TEXT
);

-- Agent 注册表
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    perspective TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    registered_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 事件表（事件溯源）
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    phase TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_agent TEXT NOT NULL DEFAULT '',
    target_agent TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    category TEXT NOT NULL DEFAULT '',
    references_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 任务队列表（blocking pull 的核心）
CREATE TABLE IF NOT EXISTS task_inbox (
    task_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    phase TEXT NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    claimed_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);

-- Artifacts 表
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT '',
    artifact_type TEXT NOT NULL,
    round_number INTEGER NOT NULL DEFAULT 1,
    clarify_round INTEGER NOT NULL DEFAULT 1,
    data_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 文档输出表
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, round_number);
CREATE INDEX IF NOT EXISTS idx_task_inbox_agent ON task_inbox(agent_id, status);
CREATE INDEX IF NOT EXISTS idx_task_inbox_session ON task_inbox(session_id, status);
CREATE INDEX IF NOT EXISTS idx_artifacts_session_type ON artifacts(session_id, artifact_type);
CREATE INDEX IF NOT EXISTS idx_agents_session ON agents(session_id);
"""


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class StorageBackend(ABC):
    """Abstract storage interface – implement to swap backends."""

    # -- Session 管理 --
    @abstractmethod
    def create_session(self, session: Session) -> Session: ...

    @abstractmethod
    def get_session(self, session_id: str) -> Session | None: ...

    @abstractmethod
    def get_active_session(self) -> Session | None: ...

    @abstractmethod
    def list_sessions(self, status: str | None = None) -> list[Session]: ...

    @abstractmethod
    def update_session(self, session: Session) -> Session: ...

    @abstractmethod
    def archive_session(self, session_id: str) -> Path | None: ...

    # -- Agent 管理 --
    @abstractmethod
    def register_agent(self, agent: AgentInfo, session_id: str) -> AgentInfo: ...

    @abstractmethod
    def get_agent(self, agent_id: str) -> AgentInfo | None: ...

    @abstractmethod
    def update_agent(self, agent: AgentInfo) -> AgentInfo: ...

    @abstractmethod
    def list_agents(self, session_id: str) -> list[AgentInfo]: ...

    # -- Artifact 管理 --
    @abstractmethod
    def save_artifact(
        self,
        artifact_type: str,
        artifact_id: str,
        session_id: str,
        agent_id: str,
        round_number: int,
        data: dict,
        clarify_round: int = 1,
    ) -> None: ...

    @abstractmethod
    def get_artifacts(
        self,
        session_id: str,
        artifact_type: str,
        round_number: int | None = None,
    ) -> list[dict]: ...

    # -- Event 管理 --
    @abstractmethod
    def append_event(self, event: Event) -> None: ...

    @abstractmethod
    def get_events(self, session_id: str, limit: int = 100) -> list[Event]: ...

    # -- Task Inbox --
    @abstractmethod
    def push_task(
        self,
        session_id: str,
        agent_id: str,
        task_type: str,
        phase: str,
        round_number: int,
        payload: dict | None = None,
    ) -> str: ...

    @abstractmethod
    def wait_for_task(
        self, agent_id: str, timeout: float = 300.0
    ) -> dict | None: ...

    @abstractmethod
    def claim_task(self, task_id: str, agent_id: str) -> None: ...

    @abstractmethod
    def complete_task(self, task_id: str) -> None: ...

    # -- Document 管理 --
    @abstractmethod
    def save_document(
        self, session_id: str, doc_type: str, content: str
    ) -> None: ...

    @abstractmethod
    def get_document(self, session_id: str, doc_type: str) -> str | None: ...


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

class SQLiteBackend(StorageBackend):
    """SQLite-backed storage with event sourcing and task inbox."""

    def __init__(self, data_dir: str | None = None) -> None:
        if data_dir is None:
            data_dir = os.environ.get(
                "DESIGNDOC_DATA_DIR", str(Path.home() / ".designdoc_mcp")
            )
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.data_dir / "designdoc.db"
        self.archive_dir = self.data_dir / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        self._lock = __import__("threading").Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Session 管理
    # ------------------------------------------------------------------

    def create_session(self, session: Session) -> Session:
        now = self._now()
        session.created_at = now
        session.updated_at = now
        req_json = (
            json.dumps(session.requirement.model_dump(), ensure_ascii=False)
            if session.requirement
            else None
        )
        meta_json = json.dumps(session.metadata, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions
                   (session_id, title, description, status, current_phase,
                    current_round, min_rounds, max_rounds, clarify_round,
                    devils_advocate_agent, requirement_json, metadata_json,
                    created_at, updated_at, completed_at, archived_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session.session_id,
                    session.title,
                    session.description,
                    session.status.value,
                    session.current_phase.value,
                    session.current_round,
                    session.min_rounds,
                    session.max_rounds,
                    session.clarify_round,
                    session.devils_advocate_agent,
                    req_json,
                    meta_json,
                    session.created_at,
                    session.updated_at,
                    session.completed_at,
                    session.archived_at,
                ),
            )
            # Persist agents that came with the session
            for agent in session.agents:
                self._insert_agent(conn, agent, session.session_id)
            # Persist events
            for ev in session.events:
                self._insert_event(conn, ev)
            # Persist artifacts
            self._persist_session_artifacts(conn, session)
        return session

    def get_session(self, session_id: str) -> Session | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row is None:
                return None
            return self._assemble_session(conn, row)

    def get_active_session(self) -> Session | None:
        """Return the single active (non-completed, non-archived) session."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM sessions
                   WHERE status NOT IN ('completed', 'archived')
                   ORDER BY updated_at DESC LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            return self._assemble_session(conn, row)

    def list_sessions(self, status: str | None = None) -> list[Session]:
        with self._connect() as conn:
            if status is not None:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY created_at DESC"
                ).fetchall()
            return [self._assemble_session(conn, r) for r in rows]

    def update_session(self, session: Session) -> Session:
        session.updated_at = self._now()
        req_json = (
            json.dumps(session.requirement.model_dump(), ensure_ascii=False)
            if session.requirement
            else None
        )
        meta_json = json.dumps(session.metadata, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE sessions SET
                   title=?, description=?, status=?, current_phase=?,
                   current_round=?, min_rounds=?, max_rounds=?, clarify_round=?,
                   devils_advocate_agent=?, requirement_json=?, metadata_json=?,
                   updated_at=?, completed_at=?, archived_at=?
                   WHERE session_id=?""",
                (
                    session.title,
                    session.description,
                    session.status.value,
                    session.current_phase.value,
                    session.current_round,
                    session.min_rounds,
                    session.max_rounds,
                    session.clarify_round,
                    session.devils_advocate_agent,
                    req_json,
                    meta_json,
                    session.updated_at,
                    session.completed_at,
                    session.archived_at,
                    session.session_id,
                ),
            )
            # Sync agents: upsert current list, remove any no longer present
            current_ids = {a.agent_id for a in session.agents}
            for agent in session.agents:
                self._insert_agent(conn, agent, session.session_id)
            # Remove agents that are no longer in the session
            if current_ids:
                placeholders = ",".join("?" for _ in current_ids)
                conn.execute(
                    f"DELETE FROM agents WHERE session_id = ? AND agent_id NOT IN ({placeholders})",
                    (session.session_id, *current_ids),
                )
            else:
                conn.execute(
                    "DELETE FROM agents WHERE session_id = ?",
                    (session.session_id,),
                )
            # Sync artifacts
            conn.execute(
                "DELETE FROM artifacts WHERE session_id = ?",
                (session.session_id,),
            )
            self._persist_session_artifacts(conn, session)
        return session

    def archive_session(self, session_id: str) -> Path | None:
        session = self.get_session(session_id)
        if session is None:
            return None

        archive_session_dir = self.archive_dir / session_id
        archive_session_dir.mkdir(parents=True, exist_ok=True)

        # Export full session JSON to archive
        session_json = session.model_dump_json(indent=2)
        (archive_session_dir / "session.json").write_text(
            session_json, encoding="utf-8"
        )

        # Mark session as archived in DB
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE sessions SET status='archived', archived_at=?, updated_at=?
                   WHERE session_id=?""",
                (now, now, session_id),
            )

        return archive_session_dir

    # ------------------------------------------------------------------
    # Agent 管理
    # ------------------------------------------------------------------

    def register_agent(self, agent: AgentInfo, session_id: str) -> AgentInfo:
        now = self._now()
        agent.registered_at = now
        agent.last_active_at = now
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO agents
                   (agent_id, session_id, name, model, provider, perspective,
                    is_active, registered_at, last_active_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(agent_id) DO UPDATE SET
                     name=excluded.name, model=excluded.model,
                     provider=excluded.provider, perspective=excluded.perspective,
                     is_active=excluded.is_active, last_active_at=excluded.last_active_at""",
                (
                    agent.agent_id,
                    session_id,
                    agent.name,
                    agent.model,
                    agent.provider,
                    agent.current_perspective,
                    1 if agent.is_active else 0,
                    agent.registered_at,
                    agent.last_active_at,
                ),
            )
        return agent

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_agent(row)

    def update_agent(self, agent: AgentInfo) -> AgentInfo:
        agent.last_active_at = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE agents SET name=?, model=?, provider=?, perspective=?,
                   is_active=?, last_active_at=? WHERE agent_id=?""",
                (
                    agent.name,
                    agent.model,
                    agent.provider,
                    agent.current_perspective,
                    1 if agent.is_active else 0,
                    agent.last_active_at,
                    agent.agent_id,
                ),
            )
        return agent

    def list_agents(self, session_id: str) -> list[AgentInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agents WHERE session_id = ?", (session_id,)
            ).fetchall()
            return [self._row_to_agent(r) for r in rows]

    # ------------------------------------------------------------------
    # Artifact 管理
    # ------------------------------------------------------------------

    def save_artifact(
        self,
        artifact_type: str,
        artifact_id: str,
        session_id: str,
        agent_id: str,
        round_number: int,
        data: dict,
        clarify_round: int = 1,
    ) -> None:
        now = self._now()
        data_json = json.dumps(data, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO artifacts
                   (artifact_id, session_id, agent_id, artifact_type,
                    round_number, clarify_round, data_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(artifact_id) DO UPDATE SET
                     data_json=excluded.data_json""",
                (
                    artifact_id,
                    session_id,
                    agent_id,
                    artifact_type,
                    round_number,
                    clarify_round,
                    data_json,
                    now,
                ),
            )

    def get_artifacts(
        self,
        session_id: str,
        artifact_type: str,
        round_number: int | None = None,
    ) -> list[dict]:
        with self._connect() as conn:
            if round_number is not None:
                rows = conn.execute(
                    """SELECT * FROM artifacts
                       WHERE session_id=? AND artifact_type=? AND round_number=?
                       ORDER BY created_at""",
                    (session_id, artifact_type, round_number),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM artifacts
                       WHERE session_id=? AND artifact_type=?
                       ORDER BY created_at""",
                    (session_id, artifact_type),
                ).fetchall()
            return [self._row_to_artifact_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event 管理
    # ------------------------------------------------------------------

    def append_event(self, event: Event) -> None:
        with self._lock, self._connect() as conn:
            self._insert_event(conn, event)

    def get_events(self, session_id: str, limit: int = 100) -> list[Event]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM events WHERE session_id=?
                   ORDER BY created_at DESC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
            return [self._row_to_event(r) for r in rows]

    # ------------------------------------------------------------------
    # Task Inbox（blocking pull 核心）
    # ------------------------------------------------------------------

    def push_task(
        self,
        session_id: str,
        agent_id: str,
        task_type: str,
        phase: str,
        round_number: int,
        payload: dict | None = None,
    ) -> str:
        task_id = uuid.uuid4().hex[:12]
        now = self._now()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO task_inbox
                   (task_id, session_id, agent_id, task_type, phase,
                    round_number, payload_json, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    task_id,
                    session_id,
                    agent_id,
                    task_type,
                    phase,
                    round_number,
                    payload_json,
                    "pending",
                    now,
                ),
            )
        return task_id

    def wait_for_task(
        self, agent_id: str, timeout: float = 300.0
    ) -> dict | None:
        """Blocking pull: 阻塞等待直到有 pending 任务或超时。"""
        deadline = time.monotonic() + timeout
        poll_interval = 1.0
        while time.monotonic() < deadline:
            task = self._get_pending_task(agent_id)
            if task:
                self.claim_task(task["task_id"], agent_id)
                return task
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(poll_interval, remaining))
        return None  # timeout

    def claim_task(self, task_id: str, agent_id: str) -> None:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE task_inbox SET status='claimed', claimed_at=?
                   WHERE task_id=? AND agent_id=? AND status='pending'""",
                (now, task_id, agent_id),
            )

    def complete_task(self, task_id: str) -> None:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE task_inbox SET status='completed', completed_at=?
                   WHERE task_id=?""",
                (now, task_id),
            )

    # ------------------------------------------------------------------
    # Document 管理
    # ------------------------------------------------------------------

    def save_document(
        self, session_id: str, doc_type: str, content: str
    ) -> None:
        doc_id = uuid.uuid4().hex[:8]
        now = self._now()
        with self._lock, self._connect() as conn:
            # Upsert: one document per (session_id, doc_type)
            existing = conn.execute(
                "SELECT doc_id FROM documents WHERE session_id=? AND doc_type=?",
                (session_id, doc_type),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE documents SET content=?, created_at=?
                       WHERE doc_id=?""",
                    (content, now, existing["doc_id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO documents
                       (doc_id, session_id, doc_type, content, created_at)
                       VALUES (?,?,?,?,?)""",
                    (doc_id, session_id, doc_type, content, now),
                )

    def get_document(self, session_id: str, doc_type: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT content FROM documents WHERE session_id=? AND doc_type=?",
                (session_id, doc_type),
            ).fetchone()
            if row is None:
                return None
            return row["content"]

    # ------------------------------------------------------------------
    # Private helpers – row ↔ model conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_agent(row: sqlite3.Row) -> AgentInfo:
        return AgentInfo(
            agent_id=row["agent_id"],
            name=row["name"],
            model=row["model"],
            provider=row["provider"],
            current_perspective=row["perspective"],
            is_active=bool(row["is_active"]),
            registered_at=row["registered_at"],
            last_active_at=row["last_active_at"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            event_id=row["event_id"],
            session_id=row["session_id"],
            round_number=row["round_number"],
            phase=DebatePhase(row["phase"]),
            event_type=EventType(row["event_type"]),
            source_agent=row["source_agent"],
            target_agent=row["target_agent"],
            content=row["content"],
            confidence=row["confidence"],
            category=row["category"],
            references=json.loads(row["references_json"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_artifact_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["data"] = json.loads(d.pop("data_json"))
        return d

    def _insert_agent(
        self, conn: sqlite3.Connection, agent: AgentInfo, session_id: str
    ) -> None:
        conn.execute(
            """INSERT OR REPLACE INTO agents
               (agent_id, session_id, name, model, provider, perspective,
                is_active, registered_at, last_active_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                agent.agent_id,
                session_id,
                agent.name,
                agent.model,
                agent.provider,
                agent.current_perspective,
                1 if agent.is_active else 0,
                agent.registered_at,
                agent.last_active_at,
            ),
        )

    def _insert_event(
        self, conn: sqlite3.Connection, event: Event
    ) -> None:
        conn.execute(
            """INSERT OR IGNORE INTO events
               (event_id, session_id, round_number, phase, event_type,
                source_agent, target_agent, content, confidence, category,
                references_json, metadata_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event.event_id,
                event.session_id,
                event.round_number,
                event.phase.value,
                event.event_type.value,
                event.source_agent,
                event.target_agent,
                event.content,
                event.confidence,
                event.category,
                json.dumps(event.references, ensure_ascii=False),
                json.dumps(event.metadata, ensure_ascii=False),
                event.created_at,
            ),
        )

    def _persist_session_artifacts(
        self, conn: sqlite3.Connection, session: Session
    ) -> None:
        """Write all artifact lists from a Session into the artifacts table."""
        now = self._now()

        def _upsert(
            artifact_id: str,
            agent_id: str,
            artifact_type: str,
            round_number: int,
            clarify_round: int,
            data: dict,
        ) -> None:
            conn.execute(
                """INSERT OR REPLACE INTO artifacts
                   (artifact_id, session_id, agent_id, artifact_type,
                    round_number, clarify_round, data_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    artifact_id,
                    session.session_id,
                    agent_id,
                    artifact_type,
                    round_number,
                    clarify_round,
                    json.dumps(data, ensure_ascii=False),
                    now,
                ),
            )

        for a in session.assumptions:
            _upsert(
                a.assumption_id,
                a.agent_id,
                "assumption",
                0,
                a.clarify_round,
                a.model_dump(),
            )

        for r in session.refined_requirements:
            _upsert(
                r.refine_id,
                r.agent_id,
                "refined_requirement",
                0,
                0,
                r.model_dump(),
            )

        for p in session.proposals:
            _upsert(
                p.proposal_id,
                p.agent_id,
                "proposal",
                p.round_number,
                0,
                p.model_dump(),
            )

        for c in session.challenges:
            _upsert(
                c.challenge_id,
                c.agent_id,
                "challenge",
                c.round_number,
                0,
                c.model_dump(),
            )

        for r in session.revisions:
            _upsert(
                r.revision_id,
                r.agent_id,
                "revision",
                r.round_number,
                0,
                r.model_dump(),
            )

        for o in session.optimizations:
            _upsert(
                o.optimization_id,
                o.agent_id,
                "optimization",
                o.round_number,
                0,
                o.model_dump(),
            )

        for da in session.devils_advocates:
            _upsert(
                da.da_id,
                da.agent_id,
                "devils_advocate",
                da.round_number,
                0,
                da.model_dump(),
            )

        for v in session.consensus_votes:
            _upsert(
                v.vote_id,
                v.agent_id,
                "consensus_vote",
                v.round_number,
                0,
                v.model_dump(),
            )

        for q in session.pending_questions:
            _upsert(
                q.question_id,
                q.asked_by,
                "pending_question",
                0,
                0,
                q.model_dump(),
            )

    def _assemble_session(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> Session:
        """Build a full Session object from the sessions row + related tables."""
        sid = row["session_id"]

        # Requirement
        requirement: Requirement | None = None
        req_json = row["requirement_json"]
        if req_json:
            requirement = Requirement.model_validate(json.loads(req_json))

        # Agents
        agent_rows = conn.execute(
            "SELECT * FROM agents WHERE session_id = ?", (sid,)
        ).fetchall()
        agents = [self._row_to_agent(r) for r in agent_rows]

        # Events
        event_rows = conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY created_at",
            (sid,),
        ).fetchall()
        events = [self._row_to_event(r) for r in event_rows]

        # Artifacts
        artifact_rows = conn.execute(
            "SELECT * FROM artifacts WHERE session_id = ?", (sid,)
        ).fetchall()

        assumptions: list[Assumption] = []
        refined_requirements: list[RefinedRequirement] = []
        proposals: list[Proposal] = []
        challenges: list[Challenge] = []
        revisions: list[Revision] = []
        optimizations: list[Optimization] = []
        devils_advocates: list[DevilsAdvocate] = []
        consensus_votes: list[ConsensusVote] = []
        pending_questions: list[PendingQuestion] = []

        _type_map: dict[str, type] = {
            "assumption": Assumption,
            "refined_requirement": RefinedRequirement,
            "proposal": Proposal,
            "challenge": Challenge,
            "revision": Revision,
            "optimization": Optimization,
            "devils_advocate": DevilsAdvocate,
            "consensus_vote": ConsensusVote,
            "pending_question": PendingQuestion,
        }
        _lists: dict[str, list] = {
            "assumption": assumptions,
            "refined_requirement": refined_requirements,
            "proposal": proposals,
            "challenge": challenges,
            "revision": revisions,
            "optimization": optimizations,
            "devils_advocate": devils_advocates,
            "consensus_vote": consensus_votes,
            "pending_question": pending_questions,
        }

        for ar in artifact_rows:
            data = json.loads(ar["data_json"])
            atype = ar["artifact_type"]
            model_cls = _type_map.get(atype)
            target_list = _lists.get(atype)
            if model_cls and target_list is not None:
                try:
                    target_list.append(model_cls.model_validate(data))
                except Exception:
                    logger.debug(
                        "Skipping artifact %s of type %s: validation failed",
                        ar["artifact_id"],
                        atype,
                    )

        # Merged assumptions – reconstruct from assumptions
        merged_assumptions = self._rebuild_merged_assumptions(assumptions)

        # clarify_refine_submitted – agents who submitted supplements
        clarify_refine_submitted: list[str] = []
        for ev in events:
            if ev.event_type == EventType.ASSUMPTION_SUPPLEMENT:
                if ev.source_agent not in clarify_refine_submitted:
                    clarify_refine_submitted.append(ev.source_agent)

        # Novelty scores from metadata
        metadata = json.loads(row["metadata_json"])
        novelty_scores: list[float] = metadata.pop("novelty_scores", [])

        return Session(
            session_id=sid,
            title=row["title"],
            description=row["description"],
            status=SessionStatus(row["status"]),
            current_phase=DebatePhase(row["current_phase"]),
            current_round=row["current_round"],
            min_rounds=row["min_rounds"],
            max_rounds=row["max_rounds"],
            clarify_round=row["clarify_round"],
            agents=agents,
            requirement=requirement,
            assumptions=assumptions,
            merged_assumptions=merged_assumptions,
            clarify_refine_submitted=clarify_refine_submitted,
            refined_requirements=refined_requirements,
            events=events,
            proposals=proposals,
            challenges=challenges,
            revisions=revisions,
            optimizations=optimizations,
            devils_advocates=devils_advocates,
            consensus_votes=consensus_votes,
            pending_questions=pending_questions,
            novelty_scores=novelty_scores,
            devils_advocate_agent=row["devils_advocate_agent"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            archived_at=row["archived_at"],
            metadata=metadata,
        )

    @staticmethod
    def _rebuild_merged_assumptions(
        assumptions: list[Assumption],
    ) -> list[MergedAssumptionGroup]:
        """Group assumptions by dimension for the merged_assumptions field."""
        from .models import ASSUMPTION_DIMENSIONS

        by_dim: dict[str, list[Assumption]] = {}
        for a in assumptions:
            by_dim.setdefault(a.dimension, []).append(a)

        merged: list[MergedAssumptionGroup] = []
        for dim in ASSUMPTION_DIMENSIONS:
            dim_assumptions = by_dim.get(dim, [])
            if not dim_assumptions:
                continue
            divergent = len(set(a.assumption for a in dim_assumptions)) > 1
            merged.append(
                MergedAssumptionGroup(
                    dimension=dim,
                    assumptions=dim_assumptions,
                    divergent=divergent,
                )
            )
        return merged

    def _get_pending_task(self, agent_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM task_inbox
                   WHERE agent_id=? AND status='pending'
                   ORDER BY created_at ASC LIMIT 1""",
                (agent_id,),
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            d["payload"] = json.loads(d.pop("payload_json"))
            return d
