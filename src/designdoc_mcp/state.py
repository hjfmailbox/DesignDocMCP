"""Shared state singletons for API server and Web UI."""
from __future__ import annotations

import os
from typing import Any

from .engine import CollaborationEngine
from .models import SessionStatus
from .store import SessionStore

_store: SessionStore | None = None
_engine: CollaborationEngine | None = None


def _get_store() -> SessionStore:
    global _store
    if _store is None:
        storage_backend = os.environ.get("DESIGNDOC_STORAGE", "json").lower()
        data_dir = os.environ.get("DESIGNDOC_DATA_DIR")
        if storage_backend == "sqlite":
            from .sqlite_store import SQLiteBackend
            _store = SQLiteBackend(data_dir)  # type: ignore[assignment]
        else:
            _store = SessionStore(data_dir)
    return _store


def _get_engine() -> CollaborationEngine:
    global _engine
    if _engine is None:
        _engine = CollaborationEngine(_get_store())
    return _engine
