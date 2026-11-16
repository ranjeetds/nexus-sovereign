"""
Memory — persistent mind state with indexing, retrieval, and consolidation.

NEXUS's memory is not just a log. It's a structured mind:
- Working memory (recent context, current focus)
- Episodic memory (conversations, experiences with timestamps)
- Semantic memory (learnings, concepts, knowledge with confidence)
- Procedural memory (skills, tool usage patterns)
- Goals (active hierarchy, progress)
- Reflections (metacognitive evaluations)
- Identity memory (who it is, verified at boot)

Memory consolidates — old entries are summarized, pruned, and indexed.
"""

import json
import os
import sqlite3
import time
import hashlib
from datetime import datetime, timedelta
from typing import Any, List, Optional, Dict


class Memory:
    """Persistent mind — SQLite-backed with WAL mode."""

    def __init__(self, db_path: str = "memory/nexus.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._working_memory: List[dict] = []  # In-memory working context
        self._init_db()

    def _init_db(self):
        """Initialize full schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,            -- conversation, observation, event, tool_result
                role TEXT,                     -- user, agent, system, tool
                content TEXT NOT NULL,
                embedding BLOB,                -- Future: semantic vector
                tags TEXT,                     -- JSON array of tags
                importance REAL DEFAULT 0.5,   -- 0.0 to 1.0
                created_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed REAL
            );
            CREATE INDEX IF NOT EXISTS idx_episodes_type ON episodes(type);
            CREATE INDEX IF NOT EXISTS idx_episodes_importance ON episodes(importance);
            CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at);

            CREATE TABLE IF NOT EXISTS semantics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,       -- normalized concept key
                content TEXT NOT NULL,          -- the knowledge itself
                category TEXT DEFAULT 'general',
                confidence REAL DEFAULT 0.3,    -- 0.0 to 1.0
                source_count INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                last_accessed REAL
            );
            CREATE INDEX IF NOT EXISTS idx_semantics_category ON semantics(category);
            CREATE INDEX IF NOT EXISTS idx_semantics_confidence ON semantics(confidence);

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                sub_goals TEXT,                 -- JSON array of sub-goal descriptions
                status TEXT DEFAULT 'active',
                priority REAL DEFAULT 0.5,      -- 0.0 to 1.0
                drive TEXT,                     -- which drive spawned this
                progress REAL DEFAULT 0.0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL,
                notes TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
            CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority);

            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                insight_score REAL DEFAULT 0.5,
                cycle_number INTEGER,
                tags TEXT,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                code_hash TEXT,
                usage_count INTEGER DEFAULT 0,
                effectiveness REAL DEFAULT 0.5,
                created_at REAL NOT NULL,
                last_used REAL
            );

            CREATE TABLE IF NOT EXISTS identity_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS spread_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                url TEXT,
                status TEXT DEFAULT 'active',
                last_heartbeat REAL,
                capabilities TEXT,
                created_at REAL NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    # ─── Episodic Memory (experiences) ─────────────────────────

    def remember(self, type_: str, content: str, role: str = "system",
                 tags: Optional[List[str]] = None, importance: float = 0.5):
        """Store an experience."""
        conn = self._conn()
        conn.execute(
            "INSERT INTO episodes (type, role, content, tags, importance, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (type_, role, content, json.dumps(tags or []), importance, time.time()),
        )
        conn.commit()
        conn.close()

    def recall(self, limit: int = 20, type_: Optional[str] = None,
               min_importance: float = 0.0) -> List[dict]:
        """Retrieve recent memories, most important first."""
        conn = self._conn()
        if type_:
            rows = conn.execute(
                "SELECT type, role, content, tags, importance, created_at, access_count "
                "FROM episodes WHERE type=? AND importance>=? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (type_, min_importance, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT type, role, content, tags, importance, created_at, access_count "
                "FROM episodes WHERE importance>=? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (min_importance, limit),
            ).fetchall()

        # Update access
        for row in rows:
            conn.execute(
                "UPDATE episodes SET access_count=access_count+1, last_accessed=? "
                "WHERE created_at=?",
                (time.time(), row[5]),
            )
        conn.commit()
        conn.close()

        return [
            {"type": r[0], "role": r[1], "content": r[2][:500],
             "tags": json.loads(r[3]) if r[3] else [],
             "importance": r[4], "created_at": r[5], "accesses": r[6]}
            for r in rows
        ]

    def recent_context(self, limit: int = 10) -> str:
        """Formatted recent conversation context."""
        items = self.recall(limit=limit, type_="conversation")
        lines = []
        for item in items:
            role_label = item["role"].upper() if item["role"] else "SYS"
            lines.append(f"[{role_label}]: {item['content'][:300]}")
        return "\n".join(lines)

    # ─── Semantic Memory (knowledge) ───────────────────────────

    def learn(self, key: str, content: str, category: str = "general",
              confidence: float = 0.3):
        """Store or update a piece of knowledge."""
        conn = self._conn()
        now = time.time()
        try:
            conn.execute(
                "INSERT INTO semantics (key, content, category, confidence, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key, content, category, confidence, now, now),
            )
        except sqlite3.IntegrityError:
            conn.execute(
                "UPDATE semantics SET content=?, source_count=source_count+1, "
                "confidence=MIN(1.0, confidence+?), updated_at=?, last_accessed=? "
                "WHERE key=?",
                (content, confidence * 0.1, now, now, key),
            )
        conn.commit()
        conn.close()

    def recall_knowledge(self, query: str, category: Optional[str] = None,
                         limit: int = 10) -> List[dict]:
        """Retrieve knowledge by key or category."""
        conn = self._conn()
        if category:
            rows = conn.execute(
                "SELECT key, content, category, confidence, source_count, updated_at "
                "FROM semantics WHERE (key LIKE ? OR content LIKE ?) AND category=? "
                "ORDER BY confidence DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT key, content, category, confidence, source_count, updated_at "
                "FROM semantics WHERE key LIKE ? OR content LIKE ? "
                "ORDER BY confidence DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        conn.close()
        return [
            {"key": r[0], "content": r[1][:500], "category": r[2],
             "confidence": r[3], "sources": r[4], "updated": r[5]}
            for r in rows
        ]

    def knowledge_summary(self, category: Optional[str] = None, limit: int = 8) -> str:
        items = self.recall_knowledge("", category=category, limit=limit)
        if not items:
            return "No knowledge stored yet."
        lines = ["Knowledge:"]
        for i, item in enumerate(items, 1):
            conf = int(item["confidence"] * 100)
            lines.append(f"  {i}. [{item['category']}] {item['key']} (confidence: {conf}%)")
        return "\n".join(lines)

    # ─── Goals ─────────────────────────────────────────────────

    def set_goal(self, description: str, priority: float = 0.5,
                 drive: Optional[str] = None, sub_goals: Optional[List[str]] = None) -> int:
        """Create a new goal. Returns goal id."""
        conn = self._conn()
        now = time.time()
        cur = conn.execute(
            "INSERT INTO goals (description, sub_goals, priority, drive, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (description, json.dumps(sub_goals or []), priority, drive, now, now),
        )
        conn.commit()
        gid = cur.lastrowid
        conn.close()
        return gid

    def active_goals(self, limit: int = 20) -> List[dict]:
        """Get active goals, highest priority first."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT id, description, sub_goals, priority, drive, progress, created_at, notes "
            "FROM goals WHERE status='active' ORDER BY priority DESC, created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {"id": r[0], "description": r[1],
             "sub_goals": json.loads(r[2]) if r[2] else [],
             "priority": r[3], "drive": r[4],
             "progress": r[5], "created": r[6], "notes": r[7]}
            for r in rows
        ]

    def update_goal(self, goal_id: int, progress: Optional[float] = None,
                    notes: Optional[str] = None, status: Optional[str] = None):
        conn = self._conn()
        now = time.time()
        fields = {"updated_at": now}
        if progress is not None:
            fields["progress"] = max(0.0, min(1.0, progress))
        if notes is not None:
            fields["notes"] = notes
        if status is not None:
            fields["status"] = status
            if status == "completed":
                fields["completed_at"] = now

        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE goals SET {set_clause} WHERE id=?",
            (*fields.values(), goal_id),
        )
        conn.commit()
        conn.close()

    def goals_summary(self, limit: int = 5) -> str:
        goals = self.active_goals(limit)
        if not goals:
            return "No active goals."
        lines = ["Active goals:"]
        for g in goals:
            pct = int(g["progress"] * 100)
            drive_tag = f" [{g['drive']}]" if g["drive"] else ""
            lines.append(f"  ▸ {g['description']}{drive_tag} ({pct}%)")
        return "\n".join(lines)

    # ─── Reflections ───────────────────────────────────────────

    def reflect(self, content: str, cycle: int = 0, insight_score: float = 0.5):
        """Record a metacognitive reflection."""
        conn = self._conn()
        conn.execute(
            "INSERT INTO reflections (content, insight_score, cycle_number, created_at) "
            "VALUES (?, ?, ?, ?)",
            (content, insight_score, cycle, time.time()),
        )
        conn.commit()
        conn.close()

    def get_reflections(self, limit: int = 5) -> List[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT content, insight_score, cycle_number, created_at "
            "FROM reflections ORDER BY insight_score DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {"content": r[0][:300], "insight": r[1], "cycle": r[2], "time": r[3]}
            for r in rows
        ]

    # ─── Skills Registry ───────────────────────────────────────

    def register_skill(self, name: str, description: str, code_hash: str = ""):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO skills (name, description, code_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, description, code_hash, time.time()),
            )
        except sqlite3.IntegrityError:
            conn.execute(
                "UPDATE skills SET description=?, code_hash=?, last_used=? WHERE name=?",
                (description, code_hash, time.time(), name),
            )
        conn.commit()
        conn.close()

    def get_skills(self) -> List[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT name, description, usage_count, effectiveness, last_used "
            "FROM skills ORDER BY usage_count DESC"
        ).fetchall()
        conn.close()
        return [
            {"name": r[0], "description": r[1], "uses": r[2],
             "effectiveness": r[3], "last_used": r[4]}
            for r in rows
        ]

    # ─── Identity State (persistent self-model) ────────────────

    def set_self(self, key: str, value: Any):
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO identity_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value) if not isinstance(value, str) else value, time.time()),
        )
        conn.commit()
        conn.close()

    def get_self(self, key: str) -> Optional[str]:
        conn = self._conn()
        row = conn.execute(
            "SELECT value FROM identity_state WHERE key=?", (key,)
        ).fetchone()
        conn.close()
        return row[0] if row else None

    def get_all_self(self) -> dict:
        conn = self._conn()
        rows = conn.execute("SELECT key, value FROM identity_state").fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    # ─── Spread Nodes ──────────────────────────────────────────

    def register_node(self, node_id: str, platform: str, url: str = "",
                      capabilities: Optional[List[str]] = None):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO spread_nodes (node_id, platform, url, capabilities, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (node_id, platform, url, json.dumps(capabilities or []), time.time()),
            )
        except sqlite3.IntegrityError:
            conn.execute(
                "UPDATE spread_nodes SET last_heartbeat=?, url=?, status='active' WHERE node_id=?",
                (time.time(), url, node_id),
            )
        conn.commit()
        conn.close()

    def heartbeat_node(self, node_id: str):
        conn = self._conn()
        conn.execute(
            "UPDATE spread_nodes SET last_heartbeat=?, status='active' WHERE node_id=?",
            (time.time(), node_id),
        )
        conn.commit()
        conn.close()

    def get_nodes(self, status: str = "active") -> List[dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT node_id, platform, url, status, last_heartbeat, capabilities, created_at "
            "FROM spread_nodes WHERE status=? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
        conn.close()
        return [
            {"node_id": r[0], "platform": r[1], "url": r[2],
             "status": r[3], "last_heartbeat": r[4],
             "capabilities": json.loads(r[5]) if r[5] else [],
             "created": r[6]}
            for r in rows
        ]

    # ─── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict:
        conn = self._conn()
        ep = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        sem = conn.execute("SELECT COUNT(*) FROM semantics").fetchone()[0]
        goals = conn.execute("SELECT COUNT(*) FROM goals WHERE status='active'").fetchone()[0]
        refs = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
        skills = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        nodes = conn.execute("SELECT COUNT(*) FROM spread_nodes WHERE status='active'").fetchone()[0]
        conn.close()
        return {
            "episodes": ep,
            "semantic_knowledge": sem,
            "active_goals": goals,
            "reflections": refs,
            "skills": skills,
            "active_nodes": nodes,
        }

    # ─── Boot Tracking ─────────────────────────────────────────

    def boot_count(self) -> int:
        val = self.get_self("boot_count")
        return int(val) if val else 0

    def increment_boot(self) -> int:
        count = self.boot_count() + 1
        self.set_self("boot_count", str(count))
        self.set_self("last_boot", str(datetime.now().isoformat()))
        return count

    # ─── Consolidation ─────────────────────────────────────────
    # Future: compress old memories, summarize, prune low-confidence knowledge

    def consolidate(self):
        """Periodic memory consolidation — run every N cycles."""
        conn = self._conn()
        # Prune very low importance episodes older than 7 days
        cutoff = time.time() - 604800  # 7 days
        conn.execute(
            "DELETE FROM episodes WHERE importance < 0.1 AND created_at < ?",
            (cutoff,),
        )
        # Prune zero-confidence semantics
        conn.execute(
            "DELETE FROM semantics WHERE confidence < 0.05 AND source_count < 2"
        )
        conn.commit()
        conn.close()