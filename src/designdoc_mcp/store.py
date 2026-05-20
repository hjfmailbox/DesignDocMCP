from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Session, SessionStatus

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, data_dir: str | None = None):
        if data_dir is None:
            data_dir = os.environ.get("DESIGNDOC_DATA_DIR", str(Path.home() / ".designdoc_mcp"))
        self.data_dir = Path(data_dir)
        self.sessions_dir = self.data_dir / "sessions"
        self.docs_dir = self.data_dir / "docs"
        self.history_dir = self.data_dir / "history"
        self.archive_dir = self.data_dir / "archive"
        self.requirements_dir = self.data_dir / "requirements"
        self._sessions: dict[str, Session] = {}
        self._mtimes: dict[str, float] = {}
        # In-memory task queue for blocking-pull protocol
        self._tasks: dict[str, list[dict]] = {}  # agent_id -> list of task dicts
        self._ensure_dirs()
        self._load_all()

    def _ensure_dirs(self) -> None:
        for d in [self.sessions_dir, self.docs_dir, self.history_dir, self.archive_dir, self.requirements_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def _lock_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.lock"

    def _acquire_lock(self, session_id: str, timeout: float = 5.0) -> None:
        lock_path = self._lock_path(session_id)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return
            except FileExistsError:
                try:
                    age = time.time() - lock_path.stat().st_mtime
                    if age > timeout:
                        lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
                time.sleep(0.05)
            except OSError:
                time.sleep(0.05)
        raise TimeoutError(f"Could not acquire lock for session '{session_id}'")

    def _release_lock(self, session_id: str) -> None:
        try:
            self._lock_path(session_id).unlink(missing_ok=True)
        except OSError:
            pass

    def _load_all(self) -> None:
        for f in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                session = Session.model_validate(data)
                self._sessions[session.session_id] = session
                self._mtimes[session.session_id] = f.stat().st_mtime
            except Exception as e:
                logger.warning("Failed to load session file %s: %s", f.name, e)

    def _reload_session(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if not path.exists():
            return
        try:
            current_mtime = path.stat().st_mtime
            if session_id in self._mtimes and self._mtimes[session_id] >= current_mtime:
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            session = Session.model_validate(data)
            self._sessions[session_id] = session
            self._mtimes[session_id] = current_mtime
        except Exception as e:
            logger.warning("Failed to reload session %s: %s", session_id, e)

    def _save(self, session: Session) -> None:
        session.updated_at = datetime.now(timezone.utc).isoformat()
        path = self._session_path(session.session_id)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.sessions_dir), suffix=".tmp", prefix=session.session_id
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))
            shutil.move(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self._sessions[session.session_id] = session
        self._mtimes[session.session_id] = path.stat().st_mtime

    def create_session(self, session: Session) -> Session:
        self._save(session)
        return session

    def get_session(self, session_id: str) -> Session | None:
        self._reload_session(session_id)
        return self._sessions.get(session_id)

    def list_sessions(self, status: str | None = None, limit: int = 0, offset: int = 0) -> list[Session]:
        self._load_all()
        sessions = list(self._sessions.values())
        if status is not None:
            sessions = [s for s in sessions if s.status.value == status]
        sessions = sorted(sessions, key=lambda s: s.created_at, reverse=True)
        if offset > 0:
            sessions = sessions[offset:]
        if limit > 0:
            sessions = sessions[:limit]
        return sessions

    def update_session(self, session: Session) -> Session:
        self._acquire_lock(session.session_id)
        try:
            self._reload_session(session.session_id)
            self._save(session)
        finally:
            self._release_lock(session.session_id)
        return session

    def delete_session(self, session_id: str) -> bool:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
        return self._sessions.pop(session_id, None) is not None

    def save_document(self, session_id: str, content: str, filename: str | None = None) -> Path:
        session = self._get_or_raise(session_id)
        if filename is None:
            safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in session.title)
            filename = f"{safe_title}.md"
        path = self.docs_dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def save_history(self, session_id: str) -> Path:
        session = self._get_or_raise(session_id)
        path = self.history_dir / f"{session_id}_history.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        return path

    def save_requirement_file(self, session_id: str, content: str) -> Path:
        path = self.requirements_dir / f"{session_id}_requirement.md"
        path.write_text(content, encoding="utf-8")
        return path

    def load_requirement_file(self, session_id: str) -> str | None:
        path = self.requirements_dir / f"{session_id}_requirement.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def archive_session(self, session_id: str) -> Path | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None

        archive_session_dir = self.archive_dir / session_id
        archive_session_dir.mkdir(parents=True, exist_ok=True)

        session_path = self._session_path(session_id)
        if session_path.exists():
            shutil.copy2(session_path, archive_session_dir / "session.json")

        for doc in self.docs_dir.glob(f"*{session_id}*"):
            shutil.copy2(doc, archive_session_dir / doc.name)

        for doc in self.docs_dir.glob("*.md"):
            safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in session.title)
            if doc.name.startswith(safe_title):
                shutil.copy2(doc, archive_session_dir / doc.name)

        history_path = self.history_dir / f"{session_id}_history.json"
        if history_path.exists():
            shutil.copy2(history_path, archive_session_dir / "history.json")

        req_path = self.requirements_dir / f"{session_id}_requirement.md"
        if req_path.exists():
            shutil.copy2(req_path, archive_session_dir / "requirement.md")

        session.status = SessionStatus.ARCHIVED
        session.archived_at = datetime.now(timezone.utc).isoformat()
        self._save(session)

        self._cleanup_working_data(session_id)

        return archive_session_dir

    def _cleanup_working_data(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return

        req_path = self.requirements_dir / f"{session_id}_requirement.md"
        if req_path.exists():
            req_path.unlink()

        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in session.title)
        for doc in self.docs_dir.glob(f"{safe_title}*.md"):
            doc.unlink()

        history_path = self.history_dir / f"{session_id}_history.json"
        if history_path.exists():
            history_path.unlink()

    def _get_or_raise(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found")
        return session

    # ------------------------------------------------------------------
    # Task Inbox (blocking-pull protocol)
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
        """Push a task into an agent's inbox. Returns the task_id."""
        task_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        task = {
            "task_id": task_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "task_type": task_type,
            "phase": phase,
            "round_number": round_number,
            "payload": payload or {},
            "status": "pending",
            "created_at": now,
            "claimed_at": None,
            "completed_at": None,
        }
        self._tasks.setdefault(agent_id, []).append(task)
        logger.debug("push_task: agent=%s task_type=%s task_id=%s", agent_id, task_type, task_id)
        return task_id

    def wait_for_task(self, agent_id: str, timeout: float = 300.0) -> dict | None:
        """Blocking pull: wait until a pending task is available or timeout."""
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
        return None

    def claim_task(self, task_id: str, agent_id: str) -> None:
        """Mark a task as claimed by the agent."""
        now = datetime.now(timezone.utc).isoformat()
        for task in self._tasks.get(agent_id, []):
            if task["task_id"] == task_id and task["status"] == "pending":
                task["status"] = "claimed"
                task["claimed_at"] = now
                break

    def complete_task(self, task_id: str) -> None:
        """Mark a task as completed."""
        now = datetime.now(timezone.utc).isoformat()
        for agent_tasks in self._tasks.values():
            for task in agent_tasks:
                if task["task_id"] == task_id:
                    task["status"] = "completed"
                    task["completed_at"] = now
                    return

    def _get_pending_task(self, agent_id: str) -> dict | None:
        """Return the first pending task for an agent, or None."""
        for task in self._tasks.get(agent_id, []):
            if task["status"] == "pending":
                return task
        return None
