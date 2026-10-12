"""
RaahiSense Temporal Relationship Engine
=======================================

Creates detected temporal/semantic relationships between detected events
using the configured relationship examples in config/event_rules.yaml.

Design constraints:
- Reads detected events only; hidden ground truth is never consulted.
- Relationships are restricted to events in the same session.
- Uses epoch milliseconds.
- Never creates CAUSES.
- causal_claim_allowed is always false for the current v1 engine.
- Relationship thresholds come from event_rules.yaml.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "database" / "raahisense.db"
RULES_PATH = PROJECT_ROOT / "config" / "event_rules.yaml"

DETECTOR_VERSION = "1.0.0"


def uuid7_like() -> str:
    """Generate a UUIDv7-compatible identifier using the current Unix time."""
    import time

    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    random_a = uuid.uuid4().int & ((1 << 12) - 1)
    random_b = uuid.uuid4().int & ((1 << 62) - 1)

    value = (
        (timestamp_ms << 80)
        | (0x7 << 76)
        | (random_a << 64)
        | (0b10 << 62)
        | random_b
    )
    return str(uuid.UUID(int=value))


def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_relationship_rules(rules: dict) -> list[dict]:
    relationships = rules.get("relationships", {})
    prohibited = set(relationships.get("prohibited_types", []))

    examples = []
    for item in relationships.get("examples", []):
        relationship = item.get("relationship")
        if not relationship:
            continue
        if relationship in prohibited or relationship == "CAUSES":
            continue
        examples.append(item)

    return examples


def get_event_rows(
    conn: sqlite3.Connection, session_id: str
) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            event_id,
            session_id,
            event_type,
            start_time_ms,
            end_time_ms,
            duration_ms,
            severity,
            confidence,
            source,
            detection_method,
            detection_version,
            description,
            road_context,
            driving_context,
            latitude,
            longitude,
            data_origin,
            is_ground_truth,
            metadata_json
        FROM events
        WHERE session_id = ?
          AND COALESCE(is_ground_truth, 0) = 0
        ORDER BY start_time_ms, event_type
        """,
        (session_id,),
    ).fetchall()

    return [dict(row) for row in rows]


def validate_event(row: dict[str, Any]) -> bool:
    required = ("event_id", "event_type", "start_time_ms", "end_time_ms")
    if any(row.get(field) is None for field in required):
        return False

    return int(row["end_time_ms"]) >= int(row["start_time_ms"])


def temporal_relation(
    source: dict[str, Any],
    target: dict[str, Any],
    relationship_type: str,
    maximum_time_delta_ms: int,
) -> Optional[dict[str, int]]:
    """
    Evaluate one configured relationship.

    PRECEDES:
        source ends before/equal to target starts.
        delta = target.start - source.end

    FOLLOWS:
        source starts after/equal to target ends.
        delta = source.start - target.end

    OVERLAPS:
        intervals overlap.
        overlap_ms is the positive intersection duration.

    CO_OCCURS:
        event starts are within the configured temporal window, or intervals
        overlap.

    WITHIN_WINDOW / ASSOCIATED_WITH:
        absolute gap between source end and target start, or overlap, is within
        the configured window.
    """
    s0 = int(source["start_time_ms"])
    s1 = int(source["end_time_ms"])
    t0 = int(target["start_time_ms"])
    t1 = int(target["end_time_ms"])

    if relationship_type == "PRECEDES":
        delta = t0 - s1
        if 0 <= delta <= maximum_time_delta_ms:
            return {"time_delta_ms": delta, "overlap_ms": 0}
        return None

    if relationship_type == "FOLLOWS":
        delta = s0 - t1
        if 0 <= delta <= maximum_time_delta_ms:
            return {"time_delta_ms": delta, "overlap_ms": 0}
        return None

    overlap = min(s1, t1) - max(s0, t0)

    if relationship_type == "OVERLAPS":
        if overlap > 0:
            return {"time_delta_ms": 0, "overlap_ms": overlap}
        return None

    if relationship_type == "CO_OCCURS":
        start_delta = abs(t0 - s0)
        if overlap > 0 or start_delta <= maximum_time_delta_ms:
            return {
                "time_delta_ms": start_delta,
                "overlap_ms": max(0, overlap),
            }
        return None

    if relationship_type in {"WITHIN_WINDOW", "ASSOCIATED_WITH"}:
        if overlap > 0:
            return {
                "time_delta_ms": 0,
                "overlap_ms": overlap,
            }

        # For non-overlapping events, use the closest interval boundary.
        if s1 <= t0:
            gap = t0 - s1
        elif t1 <= s0:
            gap = s0 - t1
        else:
            gap = 0

        if gap <= maximum_time_delta_ms:
            return {"time_delta_ms": gap, "overlap_ms": 0}
        return None

    return None


def relationship_confidence(
    source: dict[str, Any], target: dict[str, Any]
) -> float:
    source_conf = (
        float(source["confidence"])
        if source.get("confidence") is not None
        else 0.0
    )
    target_conf = (
        float(target["confidence"])
        if target.get("confidence") is not None
        else 0.0
    )

    # Conservative confidence for a relationship: weakest endpoint.
    return max(0.0, min(1.0, min(source_conf, target_conf)))


def build_description(
    source: dict[str, Any],
    target: dict[str, Any],
    relationship_type: str,
    time_delta_ms: int,
) -> str:
    if relationship_type == "PRECEDES":
        return (
            f"{source['event_type']} temporally precedes "
            f"{target['event_type']} by {time_delta_ms} ms."
        )

    if relationship_type == "FOLLOWS":
        return (
            f"{source['event_type']} temporally follows "
            f"{target['event_type']} by {time_delta_ms} ms."
        )

    if relationship_type == "OVERLAPS":
        return (
            f"{source['event_type']} overlaps "
            f"{target['event_type']} temporally."
        )

    if relationship_type == "CO_OCCURS":
        return (
            f"{source['event_type']} and {target['event_type']} "
            f"occur within the configured temporal window."
        )

    return (
        f"{source['event_type']} and {target['event_type']} "
        f"are temporally associated within the configured window."
    )


def insert_relationship(
    conn: sqlite3.Connection,
    session_id: str,
    source: dict[str, Any],
    target: dict[str, Any],
    relationship_rule: dict[str, Any],
    temporal: dict[str, int],
) -> None:
    relationship_type = relationship_rule["relationship"]
    max_delta = int(
        relationship_rule.get(
            "maximum_time_delta_ms",
            10000,
        )
    )

    confidence = relationship_confidence(source, target)

    conn.execute(
        """
        INSERT INTO event_relationships (
            relationship_id,
            session_id,
            source_event_id,
            target_event_id,
            relationship_type,
            time_delta_ms,
            overlap_ms,
            distance_m,
            confidence,
            method,
            window_ms,
            is_ground_truth,
            causal_claim_allowed,
            description,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid7_like(),
            session_id,
            source["event_id"],
            target["event_id"],
            relationship_type,
            temporal["time_delta_ms"],
            temporal["overlap_ms"],
            None,
            confidence,
            "rule",
            max_delta,
            0,
            0,
            build_description(
                source,
                target,
                relationship_type,
                temporal["time_delta_ms"],
            ),
            json.dumps(
                {
                    "detector_version": DETECTOR_VERSION,
                    "rule_source": "event_rules.yaml",
                    "configured_source_event": source["event_type"],
                    "configured_target_event": target["event_type"],
                    "maximum_time_delta_ms": max_delta,
                    "source_data_origin": source.get("data_origin"),
                    "target_data_origin": target.get("data_origin"),
                },
                separators=(",", ":"),
            ),
        ),
    )


def delete_detected_relationships(
    conn: sqlite3.Connection, session_id: str
) -> int:
    cursor = conn.execute(
        """
        DELETE FROM event_relationships
        WHERE session_id = ?
          AND COALESCE(is_ground_truth, 0) = 0
        """,
        (session_id,),
    )
    return cursor.rowcount


def run(session_id: str, replace: bool = False) -> int:
    rules = load_rules()
    relationship_rules = get_relationship_rules(rules)

    if not relationship_rules:
        raise RuntimeError(
            "No configured relationship examples found in event_rules.yaml"
        )

    minimum_confidence = float(
        rules.get("global", {})
        .get("detection", {})
        .get("minimum_confidence", 0.0)
    )

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        session = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        events = [
            row
            for row in get_event_rows(conn, session_id)
            if validate_event(row)
            and not row.get("is_ground_truth")
            and (
                row.get("confidence") is None
                or float(row["confidence"]) >= minimum_confidence
            )
        ]

        deleted = 0
        if replace:
            deleted = delete_detected_relationships(conn, session_id)

        created = 0
        abstained = 0
        used_pairs: set[tuple[str, str, str]] = set()

        existing_rows = conn.execute(
            """
            SELECT source_event_id, target_event_id, relationship_type
            FROM event_relationships
            WHERE session_id = ?
              AND COALESCE(is_ground_truth, 0) = 0
            """,
            (session_id,),
        ).fetchall()
        existing_pairs = {
            (row[0], row[1], row[2])
            for row in existing_rows
        }

        event_by_type: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            event_by_type.setdefault(event["event_type"], []).append(event)

        for rule in relationship_rules:
            source_type = rule.get("source_event")
            target_type = rule.get("target_event")
            relationship_type = rule.get("relationship")

            if not source_type or not target_type or not relationship_type:
                continue

            maximum_time_delta_ms = int(
                rule.get(
                    "maximum_time_delta_ms",
                    rules.get("relationships", {})
                    .get("defaults", {})
                    .get("temporal_window_ms", 10000),
                )
            )

            sources = event_by_type.get(source_type, [])
            targets = event_by_type.get(target_type, [])

            if not sources or not targets:
                continue

            for source in sources:
                for target in targets:
                    if source["event_id"] == target["event_id"]:
                        continue

                    key = (
                        source["event_id"],
                        target["event_id"],
                        relationship_type,
                    )
                    if key in used_pairs or key in existing_pairs:
                        continue

                    result = temporal_relation(
                        source,
                        target,
                        relationship_type,
                        maximum_time_delta_ms,
                    )

                    if result is None:
                        continue

                    if relationship_type == "CAUSES":
                        abstained += 1
                        continue

                    insert_relationship(
                        conn,
                        session_id,
                        source,
                        target,
                        rule,
                        result,
                    )
                    used_pairs.add(key)
                    created += 1

        conn.commit()

        print("RaahiSense temporal relationship detection completed")
        print("=" * 72)
        print(f"Session ID       : {session_id}")
        print(f"Detector version : {DETECTOR_VERSION}")
        print(f"Min confidence   : {minimum_confidence:.2f}")
        print(f"Events considered: {len(events)}")
        print(f"Rules configured : {len(relationship_rules)}")
        print(f"Relationships deleted: {deleted}")
        print(f"Relationships created: {created}")
        print(f"Relationships abstained: {abstained}")

        if created:
            rows = conn.execute(
                """
                SELECT
                    r.relationship_type,
                    se.event_type,
                    te.event_type,
                    r.time_delta_ms,
                    r.overlap_ms,
                    r.confidence,
                    r.causal_claim_allowed
                FROM event_relationships r
                JOIN events se ON se.event_id = r.source_event_id
                JOIN events te ON te.event_id = r.target_event_id
                WHERE r.session_id = ?
                  AND COALESCE(r.is_ground_truth, 0) = 0
                ORDER BY se.start_time_ms, te.start_time_ms
                """,
                (session_id,),
            ).fetchall()

            print("Relationships:")
            for row in rows:
                print(
                    f"  - {row[1]} -> {row[2]} "
                    f"type={row[0]} delta={row[3]}ms "
                    f"overlap={row[4]}ms confidence={row[5]:.2f} "
                    f"causal={row[6]}"
                )

        return created

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect configured temporal relationships between RaahiSense events."
    )
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    run(args.session_id, replace=args.replace)


if __name__ == "__main__":
    main()
