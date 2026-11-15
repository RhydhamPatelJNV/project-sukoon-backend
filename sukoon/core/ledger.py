"""
Project Sukoon — Append-Only Event Ledger & Transactional Outbox
Supports local SQLite for testing and PostgreSQL for production.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable, Dict, List, Optional
from sukoon.core.events import EventEnvelope


class EventLedger:
    """Append-only, immutable event ledger with transactional outbox."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._shared_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:")
            self._shared_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_ledger (
                sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                occurred_at_utc TEXT NOT NULL,
                received_at_utc TEXT NOT NULL,
                source TEXT NOT NULL,
                environment TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_type ON event_ledger(event_type);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_occurred_at ON event_ledger(occurred_at_utc);
        """)

        # Transactional Outbox table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_outbox (
                outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                destination TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at_utc TEXT NOT NULL,
                dispatched_at_utc TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (event_id) REFERENCES event_ledger(event_id)
            )
        """)
        conn.commit()
        if self._shared_conn is None:
            conn.close()

    def append(self, event: EventEnvelope, destinations: Optional[List[str]] = None) -> int:
        """Atomically append an event to the ledger and enqueue to the outbox."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO event_ledger (
                event_id, event_type, schema_version, occurred_at_utc,
                received_at_utc, source, environment, correlation_id,
                payload_hash, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id,
            event.event_type,
            event.schema_version,
            event.occurred_at_utc,
            event.received_at_utc,
            event.source,
            event.environment,
            event.correlation_id,
            event.payload_hash,
            json.dumps(event.payload, sort_keys=True)
        ))
        seq_id = cursor.lastrowid or 0

        # Outbox entries
        if destinations:
            for dest in destinations:
                cursor.execute("""
                    INSERT INTO event_outbox (
                        event_id, event_type, destination, status, created_at_utc
                    ) VALUES (?, ?, ?, 'PENDING', ?)
                """, (event.event_id, event.event_type, dest, event.received_at_utc))

        conn.commit()
        if self._shared_conn is None:
            conn.close()
        return seq_id

    def get_by_event_id(self, event_id: str) -> Optional[EventEnvelope]:
        conn = self._get_connection()
        row = conn.execute("""
            SELECT * FROM event_ledger WHERE event_id = ?
        """, (event_id,)).fetchone()
        result = self._row_to_envelope(row) if row else None
        if self._shared_conn is None:
            conn.close()
        return result

    def get_events(
        self,
        event_type: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EventEnvelope]:
        query = "SELECT * FROM event_ledger WHERE 1=1"
        params: List[Any] = []
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if environment:
            query += " AND environment = ?"
            params.append(environment.upper())
        query += " ORDER BY sequence_id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._get_connection()
        rows = conn.execute(query, params).fetchall()
        results = [self._row_to_envelope(r) for r in rows]
        if self._shared_conn is None:
            conn.close()
        return results

    def count(self) -> int:
        conn = self._get_connection()
        count = conn.execute("SELECT COUNT(*) FROM event_ledger").fetchone()[0]
        if self._shared_conn is None:
            conn.close()
        return count

    @staticmethod
    def _row_to_envelope(row: sqlite3.Row) -> EventEnvelope:
        return EventEnvelope(
            event_id=row["event_id"],
            event_type=row["event_type"],
            schema_version=row["schema_version"],
            occurred_at_utc=row["occurred_at_utc"],
            received_at_utc=row["received_at_utc"],
            processed_at_utc=row["received_at_utc"],
            source=row["source"],
            environment=row["environment"],
            correlation_id=row["correlation_id"],
            payload=json.loads(row["payload_json"])
        )
