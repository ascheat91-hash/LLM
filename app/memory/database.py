import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.core.logger import logger
from app.config.settings import get_settings


class MemoryDatabase:
    """Local SQLite memory repository for conversation history and user preferences."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path
        self._init_db()

    def _get_path(self) -> Path:
        if self._db_path:
            p = Path(self._db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p

        settings = get_settings()
        p = settings.resolve_path(settings.memory.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._get_path()), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    created_at REAL NOT NULL
                )
            """)
            # Key-value user preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            # Long-term semantic/fact memories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()
            logger.info(f"SQLite memory database initialized at {self._get_path()}")

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: Optional[Dict[str, Any]] = None,
    ) -> int:
        settings = get_settings()
        if not settings.memory.enabled:
            return -1

        with self._get_conn() as conn:
            cursor = conn.cursor()
            tool_json = json.dumps(tool_calls) if tool_calls else None
            cursor.execute(
                "INSERT INTO messages (role, content, tool_calls, created_at) VALUES (?, ?, ?, ?)",
                (role, content, tool_json, time.time()),
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        settings = get_settings()
        if not settings.memory.enabled:
            return []

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, role, content, tool_calls, created_at FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            messages = []
            for r in reversed(rows):
                tc = json.loads(r["tool_calls"]) if r["tool_calls"] else None
                messages.append({
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "tool_calls": tc,
                    "created_at": r["created_at"],
                })
            return messages

    def clear_conversation(self) -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            count = cursor.rowcount
            conn.commit()
            logger.info("Conversation history cleared from SQLite database.")
            return count

    def set_preference(self, key: str, value: Any) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time()),
            )
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
            return default

    def add_memory(self, fact: str, category: str = "general") -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memories (category, fact, created_at) VALUES (?, ?, ?)",
                (category, fact, time.time()),
            )
            conn.commit()
            return cursor.lastrowid

    def get_memories(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, fact, created_at FROM memories ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def clear_all_memory(self) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM preferences")
            cursor.execute("DELETE FROM memories")
            conn.commit()
            logger.info("All SQLite memory cleared.")

    def export_memory(self) -> Dict[str, Any]:
        """Exports all local memory records into a JSON-serializable dictionary."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, role, content, tool_calls, created_at FROM messages")
            msgs = [
                {
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "tool_calls": json.loads(r["tool_calls"]) if r["tool_calls"] else None,
                    "created_at": r["created_at"],
                }
                for r in cursor.fetchall()
            ]

            cursor.execute("SELECT key, value, updated_at FROM preferences")
            prefs = {r["key"]: r["value"] for r in cursor.fetchall()}

            cursor.execute("SELECT id, category, fact, created_at FROM memories")
            mems = [dict(r) for r in cursor.fetchall()]

            return {
                "exported_at": time.time(),
                "messages_count": len(msgs),
                "messages": msgs,
                "preferences": prefs,
                "memories": mems,
            }


_memory_instance: Optional[MemoryDatabase] = None


def get_memory_db() -> MemoryDatabase:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryDatabase()
    return _memory_instance
