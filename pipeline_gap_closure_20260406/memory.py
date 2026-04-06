#!/usr/bin/env python3
"""
Pipeline Memory Layer — PostgreSQL
Provides persistent learning, pattern recognition, and fix history
for the multi-agent self-fix pipeline.

Connection priority:
1. PIPELINE_DB_URL env var (full connection URL)
2. Construct from POSTGRES_HOST/PORT/DB/USER/PASSWORD env vars
3. deployment_package-postgres-1 on Docker network (port 5432)
4. root-postgres-1 on Docker network (port 5432)
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Any
from pathlib import Path

# Try to import asyncpg; fall back to installing it
try:
    import asyncpg
except ImportError:
    import subprocess
    print("[MEMORY] asyncpg not found, attempting pip install...")
    subprocess.run([sys.executable, "-m", "pip", "install", "asyncpg", "-q"], check=True)
    import asyncpg

from dotenv import load_dotenv

load_dotenv("/root/minimax-agent/.env", override=True)


class PipelineMemory:
    """
    Manages all PostgreSQL interactions for the pipeline.
    One instance per pipeline run; call close() when done.
    """

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._conn_info: str = "unknown"
        self._connected: bool = False

    # ─── Connection Management ───────────────────────────────────────────────

    async def _build_conn_info(self) -> dict:
        """Build connection dict from environment, trying in order."""
        # 1. Full connection URL
        db_url = os.getenv("PIPELINE_DB_URL") or os.getenv("DATABASE_URL")
        if db_url:
            # Parse postgresql://user:pass@host:port/db
            if db_url.startswith("postgresql://"):
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                return {
                    "host": parsed.hostname or "localhost",
                    "port": parsed.port or 5432,
                    "user": parsed.username or "postgres",
                    "password": parsed.password or "",
                    "database": parsed.path.lstrip("/") or "postgres",
                }

        # 2. Individual PIPELINE_DB_* vars (primary for pipeline)
        pipeline_host = os.getenv("PIPELINE_DB_HOST")
        if pipeline_host:
            return {
                "host": pipeline_host,
                "port": int(os.getenv("PIPELINE_DB_PORT", "5432")),
                "user": os.getenv("PIPELINE_DB_USER", "n8n"),
                "password": os.getenv("PIPELINE_DB_PASSWORD", ""),
                "database": os.getenv("PIPELINE_DB_NAME", "pipeline_db"),
            }

        # 3. Individual POSTGRES_* vars (fallback)
        host = os.getenv("POSTGRES_HOST")
        if host:
            return {
                "host": host,
                "port": int(os.getenv("POSTGRES_PORT", "5432")),
                "user": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", ""),
                "database": os.getenv("POSTGRES_DB", "postgres"),
            }

        # 3. Try Docker network: deployment_package-postgres-1
        candidates = [
            {"host": "deployment_package-postgres-1", "port": 5432, "user": "postgres",
             "password": os.getenv("POSTGRES_PASSWORD", "postgres"), "database": "postgres"},
            {"host": "root-postgres-1", "port": 5432, "user": "postgres",
             "password": os.getenv("POSTGRES_PASSWORD", "postgres"), "database": "postgres"},
            {"host": "localhost", "port": 5432, "user": "postgres",
             "password": "postgres", "database": "postgres"},
        ]

        for cand in candidates:
            try:
                test_conn = await asyncpg.connect(
                    host=cand["host"],
                    port=cand["port"],
                    user=cand["user"],
                    password=cand["password"],
                    database=cand["database"],
                    timeout=3,
                )
                await test_conn.close()
                return cand
            except Exception:
                continue

        # Fallback — will fail on first query with a clear message
        return {
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "postgres",
            "database": "postgres",
        }

    async def initialize(self) -> None:
        """Create connection pool and ensure tables exist."""
        if self._connected:
            return

        conn_info = await self._build_conn_info()
        self._conn_info = (
            f"postgresql://{conn_info['user']}@{conn_info['host']}:{conn_info['port']}"
            f"/{conn_info['database']}"
        )

        print(f"[MEMORY] Connecting to PostgreSQL: {self._conn_info}")

        self._pool = await asyncpg.create_pool(
            host=conn_info["host"],
            port=conn_info["port"],
            user=conn_info["user"],
            password=conn_info["password"],
            database=conn_info["database"],
            min_size=2,
            max_size=10,
            command_timeout=30,
            server_settings={"search_path": "pipeline_memory,public"},
        )

        await self._create_tables()
        self._connected = True
        print(f"[MEMORY] PostgreSQL connected: {self._conn_info}")

    async def _create_tables(self) -> None:
        """Create all required tables if they don't exist."""
        async with self._pool.acquire() as conn:
            # Create isolated schema (outside transaction — DDL auto-commits)
            await conn.execute("CREATE SCHEMA IF NOT EXISTS pipeline_memory")

            # Wrap all DDL in a transaction
            async with conn.transaction():
                # All tables prefixed with pipeline_memory.
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_memory.fix_history (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(64) UNIQUE NOT NULL,
                        trigger_message TEXT,
                        error_type VARCHAR(32),
                        root_cause_file VARCHAR(256),
                        root_cause_function VARCHAR(128),
                        root_cause_line INTEGER,
                        files_modified TEXT[],
                        fix_applied TEXT,
                        verdict VARCHAR(16) DEFAULT 'UNKNOWN',
                        confidence REAL DEFAULT 0.0,
                        revert_executed BOOLEAN DEFAULT FALSE,
                        revert_succeeded BOOLEAN,
                        duration_seconds INTEGER,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_memory.fix_patterns (
                        id SERIAL PRIMARY KEY,
                        error_type VARCHAR(32),
                        root_cause_signature VARCHAR(256),
                        successful_fix_template TEXT,
                        occurrence_count INTEGER DEFAULT 1,
                        success_count INTEGER DEFAULT 0,
                        last_seen TIMESTAMPTZ DEFAULT NOW(),
                        first_seen TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_memory.pipeline_learnings (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(64),
                        learning_text TEXT,
                        context VARCHAR(128),
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                # Indexes — name only (schema inferred from search_path)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fix_history_error_type
                    ON pipeline_memory.fix_history(error_type)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fix_history_created_at
                    ON pipeline_memory.fix_history(created_at DESC)
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fix_patterns_error_type
                    ON pipeline_memory.fix_patterns(error_type)
                """)
                await conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_fix_patterns_signature
                    ON pipeline_memory.fix_patterns(root_cause_signature)
                """)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False
            print("[MEMORY] Connection pool closed.")

    # ─── Session Record Management ───────────────────────────────────────────

    async def create_session_record(
        self,
        session_id: str,
        trigger_message: str,
        error_type: str = "UNKNOWN",
    ) -> int:
        """Create initial pipeline_memory.fix_history row. Returns record id."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO pipeline_memory.fix_history (session_id, trigger_message, error_type)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (session_id) DO UPDATE
                        SET trigger_message = EXCLUDED.trigger_message,
                            updated_at = NOW()
                    RETURNING id
                    """,
                    session_id,
                    trigger_message,
                    error_type,
                )
                return row["id"]

    async def update_session_record(self, session_id: str, **kwargs) -> None:
        """
        Update pipeline_memory.fix_history row with new data.

        Supported kwargs:
            error_type, root_cause_file, root_cause_function,
            root_cause_line, files_modified (list),
            fix_applied, verdict, confidence,
            revert_executed, revert_succeeded, duration_seconds
        """
        allowed = {
            "error_type", "root_cause_file", "root_cause_function",
            "root_cause_line", "files_modified", "fix_applied",
            "verdict", "confidence", "revert_executed",
            "revert_succeeded", "duration_seconds",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}

        if not updates:
            return

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if "files_modified" in updates:
                    arr = updates["files_modified"]
                    other_keys = [k for k in updates.keys() if k != "files_modified"]
                    if other_keys:
                        set_parts = []
                        vals = []
                        for i, k in enumerate(other_keys):
                            v = updates[k]
                            if isinstance(v, bool):
                                set_parts.append(f"{k} = ${i+1}::bool")
                            elif isinstance(v, (int, float)):
                                set_parts.append(f"{k} = ${i+1}")
                            else:
                                set_parts.append(f"{k} = ${i+1}")
                            vals.append(v)
                        scalar_query = f"UPDATE pipeline_memory.fix_history SET {', '.join(set_parts)}, updated_at = NOW() WHERE session_id = ${len(vals)+1}"
                        await conn.execute(scalar_query, *vals, session_id)
                        await conn.execute(
                            "UPDATE pipeline_memory.fix_history SET files_modified = $1::text[] WHERE session_id = $2",
                            arr, session_id
                        )
                    else:
                        await conn.execute(
                            "UPDATE pipeline_memory.fix_history SET files_modified = $1::text[], updated_at = NOW() WHERE session_id = $2",
                            arr, session_id
                        )
                else:
                    non_arr = {k: v for k, v in updates.items() if k != "files_modified"}
                    set_parts = []
                    vals = []
                    for i, k in enumerate(non_arr.keys()):
                        v = list(non_arr.values())[i]
                        if isinstance(v, bool):
                            set_parts.append(f"{k} = ${i+1}::bool")
                        elif isinstance(v, (int, float)):
                            set_parts.append(f"{k} = ${i+1}")
                        else:
                            set_parts.append(f"{k} = ${i+1}")
                        vals.append(v)
                    set_parts.append("updated_at = NOW()")
                    await conn.execute(
                        f"UPDATE pipeline_memory.fix_history SET {', '.join(set_parts)} WHERE session_id = ${len(vals) + 1}",
                        *vals, session_id
                    )

    async def get_session_record(self, session_id: str) -> Optional[dict]:
        """Get a single pipeline_memory.fix_history record by session_id."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pipeline_memory.fix_history WHERE session_id = $1",
                session_id,
            )
            return dict(row) if row else None

    async def get_active_session(
        self,
        trigger_message: str,
        minutes: int = 30,
    ) -> Optional[str]:
        """
        Return session_id of a recent session with the same trigger_message
        that was active within the last `minutes`. Used for deduplication.

        Returns session_id string or None if no active session found.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT session_id FROM pipeline_memory.fix_history
                WHERE trigger_message = $1
                  AND updated_at >= NOW() - INTERVAL '1 minute' * $2
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                trigger_message,
                minutes,
            )
            return row["session_id"] if row else None

    # ─── Similar Fixes ────────────────────────────────────────────────────────

    async def get_similar_fixes(
        self,
        error_type: str,
        files: list[str],
        limit: int = 5,
    ) -> list[dict]:
        """
        Return top similar past fixes ordered by success rate.

        Matches by error_type OR any file in files_modified.
        Excludes the current session.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                    session_id,
                    trigger_message,
                    error_type,
                    root_cause_file,
                    fix_applied,
                    verdict,
                    confidence,
                    duration_seconds,
                    created_at,
                    CASE WHEN verdict = 'PASS' THEN 1 ELSE 0 END AS passed
                FROM pipeline_memory.fix_history
                WHERE session_id != $1
                  AND (
                      error_type = $2
                      OR files_modified && $3::text[]
                      OR root_cause_file = ANY($3::text[])
                  )
                ORDER BY
                    passed DESC NULLS LAST,
                    created_at DESC
                LIMIT $4
                """,
                session_id if "test" not in error_type.lower() else "__no_session__",
                error_type,
                files,
                limit,
            )
            return [dict(r) for r in rows]

    # ─── Patterns ────────────────────────────────────────────────────────────

    async def get_pattern(
        self,
        root_cause_signature: str,
    ) -> Optional[dict]:
        """Look up known pattern by signature."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM pipeline_memory.fix_patterns
                WHERE root_cause_signature = $1
                """,
                root_cause_signature,
            )
            return dict(row) if row else None

    async def upsert_pattern(
        self,
        error_type: str,
        root_cause_signature: str,
        fix_template: str,
        succeeded: bool,
    ) -> None:
        """Update or insert pattern record after each cycle."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO pipeline_memory.fix_patterns
                        (error_type, root_cause_signature, successful_fix_template,
                         occurrence_count, success_count, last_seen, first_seen)
                    VALUES ($1, $2, $3, 1, CASE WHEN $4 THEN 1 ELSE 0 END, NOW(), NOW())
                    ON CONFLICT (root_cause_signature) DO UPDATE SET
                        occurrence_count = pipeline_memory.fix_patterns.occurrence_count + 1,
                        success_count = pipeline_memory.fix_patterns.success_count + CASE WHEN $4 THEN 1 ELSE 0 END,
                        last_seen = NOW(),
                        successful_fix_template = COALESCE(
                            NULLIF(pipeline_memory.fix_patterns.successful_fix_template, ''),
                            EXCLUDED.successful_fix_template
                        )
                    """,
                    error_type,
                    root_cause_signature,
                    fix_template,
                    succeeded,
                )

    async def get_recurrence_count(
        self,
        error_type: str,
        root_cause_signature: str = "",
    ) -> int:
        """How many times has this exact problem occurred?"""
        async with self._pool.acquire() as conn:
            if root_cause_signature:
                row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as cnt FROM pipeline_memory.fix_history
                    WHERE error_type = $1
                      AND (root_cause_file || ':' || COALESCE(root_cause_function,''))
                          = $2
                    """,
                    error_type,
                    root_cause_signature,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as cnt FROM pipeline_memory.fix_history WHERE error_type = $1",
                    error_type,
                )
            return row["cnt"] if row else 0

    async def get_success_rate(self, fix_type: str) -> float:
        """What % of times did this fix_type succeed? (0.0 to 1.0)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN verdict = 'PASS' THEN 1 ELSE 0 END) as passed
                FROM pipeline_memory.fix_history
                WHERE error_type = $1
                """,
                fix_type,
            )
            total = row["total"] or 0
            passed = row["passed"] or 0
            return (passed / total) if total > 0 else 0.0

    async def get_fix_history_summary(self, limit: int = 10) -> list[dict]:
        """Return last N pipeline_memory.fix_history rows for reporting."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT session_id, error_type, verdict, duration_seconds, created_at
                FROM pipeline_memory.fix_history
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    # ─── Learnings ────────────────────────────────────────────────────────────

    async def save_learning(
        self,
        session_id: str,
        learning_text: str,
        context: str = "",
    ) -> None:
        """Save Agent 7 insight to pipeline_learnings table."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO pipeline_memory.pipeline_learnings (session_id, learning_text, context)
                    VALUES ($1, $2, $3)
                    """,
                    session_id,
                    learning_text,
                    context,
                )

    async def get_recent_learnings(self, limit: int = 20) -> list[dict]:
        """Return recent learnings for context injection."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM pipeline_memory.pipeline_learnings
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    # ─── High-Level Pipeline Helpers ─────────────────────────────────────────

    async def record_fix_attempt(
        self,
        session_id: str,
        trigger_message: str,
        error_type: str,
        root_cause_file: str = "",
        root_cause_function: str = "",
        root_cause_line: int = 0,
        files_modified: list[str] = None,
        verdict: str = "UNKNOWN",
        confidence: float = 0.0,
        duration_seconds: int = 0,
        revert_executed: bool = False,
        revert_succeeded: bool = None,
    ) -> None:
        """Convenience method to record a complete fix cycle outcome."""
        await self.update_session_record(
            session_id,
            error_type=error_type,
            root_cause_file=root_cause_file,
            root_cause_function=root_cause_function,
            root_cause_line=root_cause_line,
            files_modified=files_modified or [],
            verdict=verdict,
            confidence=confidence,
            duration_seconds=duration_seconds,
            revert_executed=revert_executed,
            revert_succeeded=revert_succeeded,
        )

    async def get_pipeline_stats(self) -> dict:
        """Return aggregate pipeline statistics."""
        async with self._pool.acquire() as conn:
            total = await conn.fetchrow("SELECT COUNT(*) as c FROM pipeline_memory.fix_history")
            passed = await conn.fetchrow(
                "SELECT COUNT(*) as c FROM pipeline_memory.fix_history WHERE verdict = 'PASS'"
            )
            failed = await conn.fetchrow(
                "SELECT COUNT(*) as c FROM pipeline_memory.fix_history WHERE verdict = 'FAIL'"
            )
            patterns = await conn.fetchrow(
                "SELECT COUNT(*) as c FROM pipeline_memory.fix_patterns"
            )
            learnings = await conn.fetchrow(
                "SELECT COUNT(*) as c FROM pipeline_memory.pipeline_learnings"
            )

            return {
                "total_sessions": total["c"] if total else 0,
                "passed": passed["c"] if passed else 0,
                "failed": failed["c"] if failed else 0,
                "success_rate": (
                    passed["c"] / total["c"] if total and total["c"] > 0 else 0.0
                ),
                "unique_patterns": patterns["c"] if patterns else 0,
                "learnings": learnings["c"] if learnings else 0,
            }

    async def check_prior_fixes(
        self,
        files: list[str],
        lookback_days: int = 14,
    ) -> list[dict]:
        """
        Return recent PASS/partial fixes that modified any of the given files.
        Used as anti-overwrite protection before Agent 3 runs.

        Returns list of dicts with: session_id, error_type, verdict,
        confidence, files_modified, created_at, root_cause_summary.
        """
        if not files:
            return []

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    session_id,
                    error_type,
                    verdict,
                    confidence,
                    files_modified,
                    created_at,
                    root_cause_file,
                    root_cause_function,
                    fix_applied
                FROM pipeline_memory.fix_history
                WHERE verdict IN ('PASS', 'PARTIAL')
                  AND created_at >= NOW() - INTERVAL '1 day' * $1
                  AND (
                      files_modified && $2::text[]
                      OR root_cause_file = ANY($2::text[])
                  )
                ORDER BY created_at DESC
                LIMIT 5
                """,
                lookback_days,
                files,
            )
            return [dict(r) for r in rows]
