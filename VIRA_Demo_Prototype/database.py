"""
VIRA — Evidence Database Module
SQLite local evidence store with full-text search, provenance tracking,
temporal indexing, and observed vs inferred status.
"""

import json
import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "vira_evidence.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a connection with row factory configured."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize database tables, indexes, and FTS5 virtual table."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scenes (
            scene_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT,
            duration_s REAL DEFAULT 0.0,
            description TEXT,
            data_origin TEXT NOT NULL,
            primary_road_context TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_records (
            record_id TEXT PRIMARY KEY,
            scene_id TEXT NOT NULL,
            timestamp_iso TEXT NOT NULL,
            timestamp_relative_s REAL NOT NULL,
            event_type TEXT NOT NULL,
            road_user_category TEXT NOT NULL,
            observation_description TEXT NOT NULL,
            source_sensor TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            road_context TEXT NOT NULL,
            evidence_reference TEXT,
            data_origin TEXT NOT NULL,
            status TEXT NOT NULL,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scene_id) REFERENCES scenes (scene_id) ON DELETE CASCADE
        );
        """
    )

    # Core performance indexes
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_scene_time ON evidence_records(scene_id, timestamp_relative_s);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence_records(event_type);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_origin ON evidence_records(data_origin);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_user ON evidence_records(road_user_category);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_status ON evidence_records(status);"
    )

    # Full-text search (FTS5) table
    cur.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
            record_id UNINDEXED,
            scene_id,
            event_type,
            road_user_category,
            observation_description,
            road_context,
            content='evidence_records',
            content_rowid='rowid'
        );
        """
    )

    # Triggers to keep FTS in sync with base table
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS evidence_ai AFTER INSERT ON evidence_records BEGIN
            INSERT INTO evidence_fts(rowid, record_id, scene_id, event_type, road_user_category, observation_description, road_context)
            VALUES (new.rowid, new.record_id, new.scene_id, new.event_type, new.road_user_category, new.observation_description, new.road_context);
        END;
        """
    )
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS evidence_ad AFTER DELETE ON evidence_records BEGIN
            INSERT INTO evidence_fts(evidence_fts, rowid, record_id, scene_id, event_type, road_user_category, observation_description, road_context)
            VALUES ('delete', old.rowid, old.record_id, old.scene_id, old.event_type, old.road_user_category, old.observation_description, old.road_context);
        END;
        """
    )
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS evidence_au AFTER UPDATE ON evidence_records BEGIN
            INSERT INTO evidence_fts(evidence_fts, rowid, record_id, scene_id, event_type, road_user_category, observation_description, road_context)
            VALUES ('delete', old.rowid, old.record_id, old.scene_id, old.event_type, old.road_user_category, old.observation_description, old.road_context);
            INSERT INTO evidence_fts(rowid, record_id, scene_id, event_type, road_user_category, observation_description, road_context)
            VALUES (new.rowid, new.record_id, new.scene_id, new.event_type, new.road_user_category, new.observation_description, new.road_context);
        END;
        """
    )

    conn.commit()
    conn.close()
    logger.info("Initialized VIRA evidence database at %s", db_path)


def upsert_scene(scene: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> None:
    """Insert or update a scene record."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO scenes (scene_id, name, location, duration_s, description, data_origin, primary_road_context)
            VALUES (:scene_id, :name, :location, :duration_s, :description, :data_origin, :primary_road_context)
            ON CONFLICT(scene_id) DO UPDATE SET
                name=excluded.name,
                location=excluded.location,
                duration_s=excluded.duration_s,
                description=excluded.description,
                data_origin=excluded.data_origin,
                primary_road_context=excluded.primary_road_context;
            """,
            scene,
        )
    conn.close()


def insert_evidence_record(rec: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> bool:
    """Insert a single evidence record. Returns True on success, False if duplicate."""
    conn = get_db_connection(db_path)
    metadata_str = rec.get("metadata_json")
    if isinstance(metadata_str, dict):
        metadata_str = json.dumps(metadata_str)

    data = {
        "record_id": rec["record_id"],
        "scene_id": rec["scene_id"],
        "timestamp_iso": str(rec["timestamp_iso"]),
        "timestamp_relative_s": float(rec.get("timestamp_relative_s", 0.0)),
        "event_type": rec.get("event_type", "GENERAL_OBSERVATION"),
        "road_user_category": rec.get("road_user_category", "none"),
        "observation_description": rec["observation_description"],
        "source_sensor": rec.get("source_sensor", "UNKNOWN"),
        "confidence": float(rec.get("confidence", 1.0)),
        "road_context": rec.get("road_context", "Indian Road Corridor"),
        "evidence_reference": rec.get("evidence_reference", ""),
        "data_origin": rec.get("data_origin", "synthetic_demo_data"),
        "status": rec.get("status", "observed"),
        "metadata_json": metadata_str or "{}",
    }

    try:
        with conn:
            conn.execute(
                """
                INSERT INTO evidence_records (
                    record_id, scene_id, timestamp_iso, timestamp_relative_s,
                    event_type, road_user_category, observation_description,
                    source_sensor, confidence, road_context, evidence_reference,
                    data_origin, status, metadata_json
                ) VALUES (
                    :record_id, :scene_id, :timestamp_iso, :timestamp_relative_s,
                    :event_type, :road_user_category, :observation_description,
                    :source_sensor, :confidence, :road_context, :evidence_reference,
                    :data_origin, :status, :metadata_json
                );
                """,
                data,
            )
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def insert_evidence_records_batch(records: List[Dict[str, Any]], db_path: str = DEFAULT_DB_PATH) -> int:
    """Insert a batch of records, skipping duplicates. Returns count of inserted records."""
    if not records:
        return 0
    conn = get_db_connection(db_path)
    inserted = 0
    with conn:
        for rec in records:
            meta = rec.get("metadata_json")
            if isinstance(meta, dict):
                meta = json.dumps(meta)

            row = (
                rec["record_id"],
                rec["scene_id"],
                str(rec["timestamp_iso"]),
                float(rec.get("timestamp_relative_s", 0.0)),
                rec.get("event_type", "GENERAL_OBSERVATION"),
                rec.get("road_user_category", "none"),
                rec["observation_description"],
                rec.get("source_sensor", "UNKNOWN"),
                float(rec.get("confidence", 1.0)),
                rec.get("road_context", "Indian Road Corridor"),
                rec.get("evidence_reference", ""),
                rec.get("data_origin", "synthetic_demo_data"),
                rec.get("status", "observed"),
                meta or "{}",
            )
            try:
                conn.execute(
                    """
                    INSERT INTO evidence_records (
                        record_id, scene_id, timestamp_iso, timestamp_relative_s,
                        event_type, road_user_category, observation_description,
                        source_sensor, confidence, road_context, evidence_reference,
                        data_origin, status, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    row,
                )
                inserted += 1
            except sqlite3.IntegrityError:
                continue
    conn.close()
    return inserted


def get_record_by_id(record_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve single evidence record by ID."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM evidence_records WHERE record_id = ?;", (record_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def query_evidence(
    scene_id: Optional[str] = None,
    time_min_s: Optional[float] = None,
    time_max_s: Optional[float] = None,
    event_type: Optional[str] = None,
    road_user_category: Optional[str] = None,
    data_origin: Optional[str] = None,
    status: Optional[str] = None,
    search_keyword: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Query evidence with structured filters and keyword search."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    conditions = []
    params: List[Any] = []

    if scene_id:
        conditions.append("scene_id = ?")
        params.append(scene_id)
    if time_min_s is not None:
        conditions.append("timestamp_relative_s >= ?")
        params.append(time_min_s)
    if time_max_s is not None:
        conditions.append("timestamp_relative_s <= ?")
        params.append(time_max_s)
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if road_user_category:
        conditions.append("road_user_category = ?")
        params.append(road_user_category)
    if data_origin:
        conditions.append("data_origin = ?")
        params.append(data_origin)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if search_keyword and search_keyword.strip():
        kw = f"%{search_keyword.strip()}%"
        conditions.append(
            "(observation_description LIKE ? OR road_context LIKE ? OR event_type LIKE ? OR record_id LIKE ?)"
        )
        params.extend([kw, kw, kw, kw])

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT * FROM evidence_records
        {where_clause}
        ORDER BY scene_id ASC, timestamp_relative_s ASC
        LIMIT ? OFFSET ?;
    """
    params.extend([limit, offset])

    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def search_evidence_fts(
    search_phrase: str,
    scene_id: Optional[str] = None,
    limit: int = 25,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Full-text search using SQLite FTS5."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    clean_phrase = "".join(c if c.isalnum() or c.isspace() else " " for c in search_phrase)
    tokens = [t for t in clean_phrase.split() if t]
    if not tokens:
        conn.close()
        return []

    # Construct match expression
    match_query = " OR ".join(f'"{tok}"*' for tok in tokens)

    try:
        if scene_id:
            cur.execute(
                """
                SELECT r.*, rank as bm25_rank
                FROM evidence_fts f
                JOIN evidence_records r ON f.record_id = r.record_id
                WHERE evidence_fts MATCH ? AND r.scene_id = ?
                ORDER BY rank
                LIMIT ?;
                """,
                (match_query, scene_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT r.*, rank as bm25_rank
                FROM evidence_fts f
                JOIN evidence_records r ON f.record_id = r.record_id
                WHERE evidence_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
                """,
                (match_query, limit),
            )
        rows = [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()

    return rows


def get_all_scenes(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """List all available scenes with counts."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.*,
            (SELECT COUNT(*) FROM evidence_records e WHERE e.scene_id = s.scene_id) as record_count,
            (SELECT COUNT(*) FROM evidence_records e WHERE e.scene_id = s.scene_id AND e.status = 'observed') as observed_count,
            (SELECT COUNT(*) FROM evidence_records e WHERE e.scene_id = s.scene_id AND e.status = 'inferred') as inferred_count
        FROM scenes s
        ORDER BY s.scene_id ASC;
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_provenance_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Return provenance proportions, total counts, and observed vs inferred status."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM evidence_records;")
    total_records = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scenes;")
    total_scenes = cur.fetchone()[0]

    cur.execute(
        """
        SELECT data_origin, COUNT(*) as cnt
        FROM evidence_records
        GROUP BY data_origin;
        """
    )
    origin_counts = {r["data_origin"]: r["cnt"] for r in cur.fetchall()}

    cur.execute(
        """
        SELECT status, COUNT(*) as cnt
        FROM evidence_records
        GROUP BY status;
        """
    )
    status_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

    cur.execute(
        """
        SELECT road_user_category, COUNT(*) as cnt
        FROM evidence_records
        WHERE road_user_category != 'none'
        GROUP BY road_user_category
        ORDER BY cnt DESC;
        """
    )
    road_user_counts = {r["road_user_category"]: r["cnt"] for r in cur.fetchall()}

    cur.execute(
        """
        SELECT event_type, COUNT(*) as cnt
        FROM evidence_records
        GROUP BY event_type
        ORDER BY cnt DESC;
        """
    )
    event_counts = {r["event_type"]: r["cnt"] for r in cur.fetchall()}

    conn.close()

    tiand_count = origin_counts.get("TIAND", 0)
    synthetic_count = origin_counts.get("synthetic_demo_data", 0)
    uploaded_count = origin_counts.get("uploaded_data", 0)

    tiand_pct = round((tiand_count / total_records * 100), 1) if total_records > 0 else 0.0
    synthetic_pct = round((synthetic_count / total_records * 100), 1) if total_records > 0 else 0.0
    uploaded_pct = round((uploaded_count / total_records * 100), 1) if total_records > 0 else 0.0

    return {
        "total_records": total_records,
        "total_scenes": total_scenes,
        "tiand_count": tiand_count,
        "synthetic_count": synthetic_count,
        "uploaded_count": uploaded_count,
        "tiand_pct": tiand_pct,
        "synthetic_pct": synthetic_pct,
        "uploaded_pct": uploaded_pct,
        "observed_count": status_counts.get("observed", 0),
        "inferred_count": status_counts.get("inferred", 0),
        "road_user_counts": road_user_counts,
        "event_counts": event_counts,
    }


def reset_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """Safely drop tables and recreate empty database schema."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS evidence_fts;")
    cur.execute("DROP TABLE IF EXISTS evidence_records;")
    cur.execute("DROP TABLE IF EXISTS scenes;")
    conn.commit()
    conn.close()
    init_database(db_path)
    logger.info("Reset database at %s", db_path)
