"""
RaahiSense - Source-Independent Context Detector

Version: 1.0.0

Reads normalized observations and session metadata only.
Does not read hidden ground truth.
Writes detected contexts to the frozen v1 `contexts` table.

Supported sources through the common model:
    synthetic, simulation/CARLA, replay, physical
"""

from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required. Install it with: pip install pyyaml") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "database" / "raahisense.db"
RULES_PATH = PROJECT_ROOT / "config" / "context_rules.yaml"
DETECTOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class Observation:
    observation_id: str
    session_id: str
    signal_name: str
    timestamp_ms: int
    value: Any
    source: str | None
    quality: str | None
    confidence: float | None
    latitude: float | None
    longitude: float | None
    data_origin: str


def uuid7() -> str:
    timestamp_ms = int(time.time() * 1000)
    timestamp_48 = timestamp_ms & ((1 << 48) - 1)
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (
        (timestamp_48 << 80)
        | (0x7 << 76)
        | (random_a << 64)
        | (0x2 << 62)
        | random_b
    )
    return str(uuid.UUID(int=value))


def load_rules() -> dict[str, Any]:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_value(row: sqlite3.Row) -> Any:
    if row["value_bool"] is not None:
        return bool(row["value_bool"])
    if row["value_num"] is not None:
        return row["value_num"]
    if row["value_int"] is not None:
        return row["value_int"]
    if row["value_text"] is not None:
        return row["value_text"]
    if row["value_json"] is not None:
        try:
            return json.loads(row["value_json"])
        except json.JSONDecodeError:
            return row["value_json"]
    return None


def load_session(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Session not found: {session_id}")
    return row


def load_observations(
    conn: sqlite3.Connection, session_id: str
) -> dict[str, list[Observation]]:
    rows = conn.execute(
        """
        SELECT
            o.observation_id, o.session_id, s.canonical_name AS signal_name,
            o.timestamp_ms, o.source, o.value_num, o.value_text,
            o.value_bool, o.value_int, o.value_json, o.quality,
            o.confidence, o.latitude, o.longitude, o.data_origin
        FROM observations o
        JOIN signals s ON s.signal_id = o.signal_id
        WHERE o.session_id = ?
        ORDER BY o.timestamp_ms, o.observation_id
        """,
        (session_id,),
    ).fetchall()

    grouped: dict[str, list[Observation]] = {}
    for row in rows:
        obs = Observation(
            observation_id=row["observation_id"],
            session_id=row["session_id"],
            signal_name=row["signal_name"],
            timestamp_ms=int(row["timestamp_ms"]),
            value=get_value(row),
            source=row["source"],
            quality=row["quality"],
            confidence=row["confidence"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            data_origin=row["data_origin"],
        )
        grouped.setdefault(obs.signal_name, []).append(obs)
    return grouped


def valid_observations(items: list[Observation]) -> list[Observation]:
    invalid = {"invalid", "out_of_range", "missing"}
    return [x for x in items if x.value is not None and x.quality not in invalid]


def compare(value: Any, operator: str, target: Any) -> bool:
    if operator == "==":
        return value == target
    if operator == "!=":
        return value != target
    if operator == "<":
        return value < target
    if operator == "<=":
        return value <= target
    if operator == ">":
        return value > target
    if operator == ">=":
        return value >= target
    raise ValueError(f"Unsupported operator: {operator}")


def rule_matches(value: Any, rule: dict[str, Any]) -> bool:
    operator = rule["operator"]
    if operator == "range":
        lower_ok = value >= rule["min_value"] if rule.get("min_inclusive", True) else value > rule["min_value"]
        upper_ok = value <= rule["max_value"] if rule.get("max_inclusive", True) else value < rule["max_value"]
        return lower_ok and upper_ok
    return compare(value, operator, rule["value"])


def interval_from_true_runs(items: list[Observation], rule: dict[str, Any]) -> list[tuple[int, int, Observation]]:
    """Create intervals from consecutive matching observations.

    The end is the last matching observation timestamp. This avoids using
    the first false sample as the event/context end and matches the detector's
    evaluation convention.
    """
    matches = []
    for obs in valid_observations(items):
        try:
            if rule_matches(obs.value, rule):
                matches.append(obs)
        except (TypeError, ValueError):
            continue

    if not matches:
        return []

    runs: list[list[Observation]] = [[matches[0]]]
    for obs in matches[1:]:
        previous = runs[-1][-1]
        if obs.timestamp_ms >= previous.timestamp_ms:
            runs[-1].append(obs)
        else:
            runs.append([obs])

    return [(run[0].timestamp_ms, run[-1].timestamp_ms, run[0]) for run in runs]


def insert_context(
    conn: sqlite3.Connection,
    session_id: str,
    context_type: str,
    label: str | None,
    start_ms: int,
    end_ms: int,
    confidence: float,
    source: str | None,
    detection_method: str,
    data_origin: str,
    value_text: str | None = None,
    value_num: float | None = None,
    unit: str | None = None,
    latitude_start: float | None = None,
    longitude_start: float | None = None,
    latitude_end: float | None = None,
    longitude_end: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO contexts (
            context_id, session_id, context_type, context_category,
            start_time_ms, end_time_ms, label, value_num, value_text,
            unit, confidence, source, detection_method,
            latitude_start, longitude_start, latitude_end, longitude_end,
            data_origin, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid7(), session_id, context_type, context_type,
            start_ms, end_ms, label, value_num, value_text, unit,
            confidence, source, detection_method,
            latitude_start, longitude_start, latitude_end, longitude_end,
            data_origin, json.dumps(metadata or {}, sort_keys=True),
        ),
    )


def session_contexts(
    conn: sqlite3.Connection,
    session: sqlite3.Row,
    rules: dict[str, Any],
) -> int:
    count = 0
    start_ms = int(session["start_time_ms"])
    end_ms = int(session["end_time_ms"])
    data_origin = session["data_origin"]

    for rule in rules.get("contexts", []):
        if rule.get("source") != "session_metadata":
            continue
        field = rule.get("field")
        value = session[field] if field in session.keys() else None
        if value is None or str(value).strip() == "":
            continue
        confidence = float(rule.get("confidence", 1.0))
        if confidence < float(rules["global"].get("minimum_confidence", 0.70)):
            continue
        insert_context(
            conn, session["session_id"], rule["context_type"], str(value),
            start_ms, end_ms, confidence, "session_metadata", "rule",
            data_origin, value_text=str(value),
            metadata={"rule_source": "session_metadata", "field": field, "detector_version": DETECTOR_VERSION},
        )
        count += 1
    return count


def observation_contexts(
    conn: sqlite3.Connection,
    session: sqlite3.Row,
    grouped: dict[str, list[Observation]],
    rules: dict[str, Any],
) -> tuple[int, int]:
    detected = 0
    abstained = 0
    min_conf = float(rules["global"].get("minimum_confidence", 0.70))

    for rule_def in rules.get("contexts", []):
        if rule_def.get("source") == "session_metadata":
            continue
        signal = rule_def.get("signal")
        items = grouped.get(signal, [])
        if not items:
            abstained += 1
            continue

        confidence = float(rule_def.get("confidence", 0.0))
        if confidence < min_conf:
            abstained += 1
            continue

        intervals = interval_from_true_runs(items, rule_def["rule"])
        if not intervals:
            continue

        for start_ms, end_ms, first in intervals:
            matching = [
                x for x in valid_observations(items)
                if start_ms <= x.timestamp_ms <= end_ms
            ]
            last = matching[-1] if matching else first
            insert_context(
                conn,
                session["session_id"],
                rule_def["context_type"],
                rule_def.get("label"),
                start_ms,
                end_ms,
                confidence,
                first.source,
                "rule",
                first.data_origin,
                value_num=float(first.value) if isinstance(first.value, (int, float)) and not isinstance(first.value, bool) else None,
                unit=rule_def["rule"].get("unit"),
                latitude_start=first.latitude,
                longitude_start=first.longitude,
                latitude_end=last.latitude,
                longitude_end=last.longitude,
                metadata={
                    "signal": signal,
                    "rule": rule_def["rule"],
                    "detector_version": DETECTOR_VERSION,
                    "temporal_context_is_not_causal": True,
                },
            )
            detected += 1
    return detected, abstained


def clear_session_contexts(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute("DELETE FROM contexts WHERE session_id = ?", (session_id,))


def detect_contexts(session_id: str, replace: bool = False) -> tuple[int, int, int]:
    rules = load_rules()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        session = load_session(conn, session_id)
        if replace:
            clear_session_contexts(conn, session_id)
        grouped = load_observations(conn, session_id)
        metadata_count = session_contexts(conn, session, rules)
        observation_count, abstained = observation_contexts(conn, session, grouped, rules)
        conn.commit()
        return metadata_count + observation_count, abstained, len(grouped)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect RaahiSense contexts for one session")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    try:
        detected, abstained, signal_count = detect_contexts(args.session_id, args.replace)
    except Exception as exc:
        print(f"Context detection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("RaahiSense context detection completed")
    print("=" * 72)
    print(f"Session ID       : {args.session_id}")
    print(f"Detector version : {DETECTOR_VERSION}")
    print(f"Min confidence   : {load_rules()['global']['minimum_confidence']:.2f}")
    print(f"Signals available: {signal_count}")
    print(f"Contexts created : {detected}")
    print(f"Rules abstained  : {abstained}")

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            """
            SELECT context_type, label, start_time_ms, end_time_ms,
                   confidence, source, data_origin
            FROM contexts
            WHERE session_id = ?
            ORDER BY start_time_ms, context_id
            """,
            (args.session_id,),
        ).fetchall()
    finally:
        conn.close()

    if rows:
        print("Contexts:")
        for row in rows:
            print(
                f"  - {row[0]}:{row[1] or '-'} "
                f"[{row[2]} - {row[3]}] "
                f"confidence={row[4]:.2f} source={row[5]} origin={row[6]}"
            )


if __name__ == "__main__":
    main()
