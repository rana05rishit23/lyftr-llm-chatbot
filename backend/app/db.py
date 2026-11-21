import json
import os
import aiosqlite
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .config import settings

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  TEXT NOT NULL,
  role        TEXT NOT NULL,   -- 'user' or 'assistant'
  content     TEXT NOT NULL,
  metadata    TEXT,            -- JSON string, assistant messages only
  created_at  TEXT NOT NULL    -- server time, ISO-8601
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages (session_id, id);
"""


async def get_db_path() -> str:
    path = settings.sqlite_path
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    return path


async def init_db() -> None:
    db_path = await get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()


async def save_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    db_path = await get_db_path()
    created_at = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata) if metadata else None

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, meta_json, created_at),
        )
        await db.commit()
        return cursor.lastrowid


async def get_session_history(session_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Returns messages list for session_id oldest first.
    Returns None if session does not exist (no messages recorded for this session_id).
    """
    db_path = await get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT role, content, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return None

        result = []
        for row in rows:
            item: Dict[str, Any] = {
                "role": row["role"],
                "content": row["content"],
            }
            if row["metadata"]:
                try:
                    item["metadata"] = json.loads(row["metadata"])
                except Exception:
                    item["metadata"] = None
            result.append(item)
        return result


async def get_llm_conversation_messages(session_id: str) -> List[Dict[str, str]]:
    """
    Returns formatted messages for the LLM context:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    db_path = await get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
