"""

RaahiSense - Rule-Based Event Detector

Version: 1.0.0



Research constraints:

- Reads only normalized observations from SQLite.

- Reads configurable rules from config/event_rules.yaml.

- Does NOT read hidden ground-truth files.

- Writes detected events to the frozen v1 `events` table.

- All generated events have is_ground_truth = 0.

"""



from __future__ import annotations



import argparse

import json

import secrets

import sqlite3

import sys

import uuid

from dataclasses import dataclass

from pathlib import Path

from typing import Any



try:

    import yaml

except ImportError as exc:

    raise SystemExit(

        "PyYAML is required. Install it with: pip install pyyaml"

    ) from exc





PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "database" / "raahisense.db"

RULES_PATH = PROJECT_ROOT / "config" / "event_rules.yaml"



DETECTOR_VERSION = "1.0.1"

SCHEMA_VERSION = "1.0.0"





@dataclass(frozen=True)

class Observation:

    observation_id: str

    session_id: str

    signal_name: str

    timestamp_ms: int

    value: Any

    source: str

    quality: str

    confidence: float | None

    road_context: str | None

    driving_context: str | None

    latitude: float | None

    longitude: float | None

    data_origin: str





def uuid7() -> str:

    """Create a UUIDv7-compatible identifier with the current Unix-ms timestamp."""

    timestamp_ms = int(__import__("time").time() * 1000)

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

    """Return the populated typed observation value."""

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





def load_observations(

    conn: sqlite3.Connection,

    session_id: str,

) -> dict[str, list[Observation]]:

    """

    Load one session's observations grouped by canonical signal name.



    Ground-truth artifacts are intentionally never accessed here.

    """

    rows = conn.execute(

        """

        SELECT

            o.observation_id,

            o.session_id,

            s.canonical_name AS signal_name,

            o.timestamp_ms,

            o.source,

            o.value_num,

            o.value_text,

            o.value_bool,

            o.value_int,

            o.value_json,

            o.quality,

            o.confidence,

            o.road_context,

            o.driving_context,

            o.latitude,

            o.longitude,

            o.data_origin

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

            timestamp_ms=row["timestamp_ms"],

            value=get_value(row),

            source=row["source"],

            quality=row["quality"],

            confidence=row["confidence"],

            road_context=row["road_context"],

            driving_context=row["driving_context"],

            latitude=row["latitude"],

            longitude=row["longitude"],

            data_origin=row["data_origin"],

        )

        grouped.setdefault(obs.signal_name, []).append(obs)



    return grouped





def valid_observations(

    observations: list[Observation],

) -> list[Observation]:

    """Exclude observations explicitly marked unusable."""

    invalid = {"invalid", "out_of_range", "missing"}

    return [

        obs

        for obs in observations

        if obs.value is not None and obs.quality not in invalid

    ]





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





def condition_matches(

    obs: Observation,

    condition: dict[str, Any],

) -> bool:

    return compare(

        obs.value,

        condition["operator"],

        condition["value"],

    )





def nearest_observation(

    observations: list[Observation],

    timestamp_ms: int,

) -> Observation | None:

    if not observations:

        return None

    return min(

        observations,

        key=lambda obs: abs(obs.timestamp_ms - timestamp_ms),

    )





def supporting_signal_present(

    grouped: dict[str, list[Observation]],

    signal_name: str,

    start_ms: int,

    end_ms: int,

) -> bool:

    for obs in grouped.get(signal_name, []):

        if start_ms <= obs.timestamp_ms <= end_ms:

            if obs.value is not None and obs.quality not in {

                "invalid",

                "out_of_range",

                "missing",

            }:

                return True

    return False





def calculate_confidence(

    rule: dict[str, Any],

    grouped: dict[str, list[Observation]],

    start_ms: int,

    end_ms: int,

) -> float:

    confidence_cfg = rule.get("confidence", {})

    confidence = float(confidence_cfg.get("base", 0.5))



    for signal_name, bonus in confidence_cfg.get(

        "supporting_signal_bonus", {}

    ).items():

        if supporting_signal_present(

            grouped, signal_name, start_ms, end_ms

        ):

            confidence += float(bonus)



    return min(1.0, max(0.0, confidence))





def classify_sharp_braking(

    acceleration_values: list[float],

    severity_cfg: dict[str, Any],

) -> str | None:

    if not acceleration_values:

        return None



    minimum = min(acceleration_values)

    levels = severity_cfg.get("levels", {})



    high = levels.get("high", {})

    medium = levels.get("medium", {})

    low = levels.get("low", {})



    if "acceleration_less_or_equal" in high:

        if minimum <= float(high["acceleration_less_or_equal"]):

            return "high"



    if "acceleration_less_or_equal" in medium:

        if minimum <= float(medium["acceleration_less_or_equal"]):

            if "acceleration_greater_than" not in medium or (

                minimum > float(medium["acceleration_greater_than"])

            ):

                return "medium"



    if "acceleration_greater_than" in low:

        if minimum > float(low["acceleration_greater_than"]):

            return "low"



    return None





def detect_threshold_with_duration(

    rule: dict[str, Any],

    grouped: dict[str, list[Observation]],

) -> list[dict[str, Any]]:

    conditions = rule["rule"].get("conditions", [])

    duration_cfg = rule["rule"].get("duration", {})

    minimum_ms = int(duration_cfg.get("minimum_ms", 0))

    maximum_ms = int(duration_cfg.get("maximum_ms", 5000))



    if not conditions:

        return []



    # v1 threshold-with-duration rules use one required signal.

    primary_signal = conditions[0]["signal"]

    primary = valid_observations(grouped.get(primary_signal, []))



    if not primary:

        return []



    matches = [

        obs

        for obs in primary

        if all(condition_matches(obs, condition) for condition in conditions)

    ]



    if not matches:

        return []



    events: list[dict[str, Any]] = []

    run: list[Observation] = []



    for obs in matches:

        if not run:

            run = [obs]

            continue



        previous = run[-1]



        # A new run begins when the qualifying observations are separated

        # by an unusually large gap. The expected frequencies are normally

        # high enough that this also prevents merging unrelated events.

        if obs.timestamp_ms < previous.timestamp_ms:

            continue



        run.append(obs)



        duration = run[-1].timestamp_ms - run[0].timestamp_ms



        if duration > maximum_ms:

            candidate = run[:-1]

            candidate_duration = (

                candidate[-1].timestamp_ms - candidate[0].timestamp_ms

            )



            if candidate_duration >= minimum_ms:

                events.append(

                    build_threshold_event(

                        rule,

                        grouped,

                        candidate,

                    )

                )



            run = [obs]



    if run:

        duration = run[-1].timestamp_ms - run[0].timestamp_ms

        if duration >= minimum_ms:

            events.append(

                build_threshold_event(

                    rule,

                    grouped,

                    run,

                )

            )



    return events





def build_threshold_event(

    rule: dict[str, Any],

    grouped: dict[str, list[Observation]],

    run: list[Observation],

) -> dict[str, Any]:

    start_ms = run[0].timestamp_ms

    end_ms = run[-1].timestamp_ms



    acceleration_values = [

        float(obs.value)

        for obs in run

        if isinstance(obs.value, (int, float))

    ]



    severity = classify_sharp_braking(

        acceleration_values,

        rule.get("severity", {}),

    )



    confidence = calculate_confidence(

        rule,

        grouped,

        start_ms,

        end_ms,

    )



    trigger = min(

        run,

        key=lambda obs: float(obs.value)

        if isinstance(obs.value, (int, float))

        else 0.0,

    )



    return {

        "event_type": rule["event_type"],

        "event_category": rule["event_category"],

        "start_time_ms": start_ms,

        "end_time_ms": end_ms,

        "severity": severity,

        "confidence": confidence,

        "source": trigger.source,

        "detection_method": rule.get("detection_method", "rule"),

        "detection_version": rule.get(

            "detection_version", DETECTOR_VERSION

        ),

        "trigger_observation_id": trigger.observation_id,

        "description": rule.get("description", "").strip(),

        "road_context": trigger.road_context,

        "driving_context": trigger.driving_context,

        "latitude": trigger.latitude,

        "longitude": trigger.longitude,

        "data_origin": trigger.data_origin,

        "is_ground_truth": 0,

        "metadata": {

            "detector": "RaahiSense event detector",

            "detector_version": DETECTOR_VERSION,

            "rule_event_type": rule["event_type"],

            "observations_used": [obs.observation_id for obs in run],

            "min_acceleration_ms2": min(acceleration_values)

            if acceleration_values

            else None,

            "max_acceleration_ms2": max(acceleration_values)

            if acceleration_values

            else None,

        },

    }





def detect_boolean_state(

    rule: dict[str, Any],

    grouped: dict[str, list[Observation]],

) -> list[dict[str, Any]]:

    conditions = rule["rule"].get("conditions", [])

    if not conditions:

        return []



    primary_signal = conditions[0]["signal"]

    observations = valid_observations(

        grouped.get(primary_signal, [])

    )



    if not observations:

        return []



    events: list[dict[str, Any]] = []

    active_start: Observation | None = None

    active_observations: list[Observation] = []



    for obs in observations:

        matches = all(

            condition_matches(obs, condition)

            for condition in conditions

        )



        if matches and active_start is None:

            active_start = obs

            active_observations = [obs]

            continue



        if matches and active_start is not None:

            active_observations.append(obs)

            continue



        if not matches and active_start is not None:

            events.append(

                build_boolean_event(

                    rule,

                    grouped,

                    active_start,

                    active_observations[-1].timestamp_ms,

                    active_observations,

                )

            )

            active_start = None

            active_observations = []



    # Close an event that remains active at session end.

    if active_start is not None:

        last = active_observations[-1]

        events.append(

            build_boolean_event(

                rule,

                grouped,

                active_start,

                last.timestamp_ms,

                active_observations,

            )

        )



    return events





def build_boolean_event(

    rule: dict[str, Any],

    grouped: dict[str, list[Observation]],

    start_obs: Observation,

    end_ms: int,

    active_observations: list[Observation],

) -> dict[str, Any]:

    confidence = calculate_confidence(

        rule,

        grouped,

        start_obs.timestamp_ms,

        end_ms,

    )



    return {

        "event_type": rule["event_type"],

        "event_category": rule["event_category"],

        "start_time_ms": start_obs.timestamp_ms,

        "end_time_ms": end_ms,

        "severity": None,

        "confidence": confidence,

        "source": start_obs.source,

        "detection_method": rule.get("detection_method", "rule"),

        "detection_version": rule.get(

            "detection_version", DETECTOR_VERSION

        ),

        "trigger_observation_id": start_obs.observation_id,

        "description": rule.get("description", "").strip(),

        "road_context": start_obs.road_context,

        "driving_context": start_obs.driving_context,

        "latitude": start_obs.latitude,

        "longitude": start_obs.longitude,

        "data_origin": start_obs.data_origin,

        "is_ground_truth": 0,

        "metadata": {

            "detector": "RaahiSense event detector",

            "detector_version": DETECTOR_VERSION,

            "rule_event_type": rule["event_type"],

            "state_transition": rule["rule"].get(

                "state_transition"

            ),

            "end_condition": rule["rule"].get("end_condition"),

            "observations_used": [

                obs.observation_id for obs in active_observations

            ],

        },

    }





def detect_events(

    rules: dict[str, Any],

    grouped: dict[str, list[Observation]],

) -> tuple[list[dict[str, Any]], int]:

    detected: list[dict[str, Any]] = []

    """Detect events and apply the configured global confidence threshold."""
    minimum_confidence = float(
        rules.get("global", {})
        .get("detection", {})
        .get("minimum_confidence", 0.0)
    )
    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError(
            "minimum_confidence must be between 0.0 and 1.0; "
            f"got {minimum_confidence!r}"
        )
    abstained_count = 0



    for rule in rules.get("events", []):

        rule_type = rule.get("rule", {}).get("type")



        required_signals = rule.get("required_signals", [])

        if any(

            signal_name not in grouped

            or not valid_observations(grouped[signal_name])

            for signal_name in required_signals

        ):

            # Explicit insufficient-evidence behavior:

            # do not invent an event when required evidence is absent.

            continue



        if rule_type == "threshold_with_duration":

            detected.extend(

                detect_threshold_with_duration(rule, grouped)

            )

        elif rule_type == "boolean_state":

            detected.extend(

                detect_boolean_state(rule, grouped)

            )

        else:

            raise ValueError(

                f"Unsupported rule type: {rule_type!r} "

                f"for event {rule.get('event_type')!r}"

            )



    # Apply the configured confidence policy.
    # Below-threshold detections are treated as insufficient evidence.
    accepted: list[dict[str, Any]] = []
    for event in detected:
        confidence = float(event.get("confidence", 0.0))
        if confidence >= minimum_confidence:
            accepted.append(event)
        else:
            abstained_count += 1
    detected = accepted

    detected.sort(

        key=lambda event: (

            event["start_time_ms"],

            event["end_time_ms"],

            event["event_type"],

        )

    )

    return detected, abstained_count





def insert_event(

    conn: sqlite3.Connection,

    session_id: str,

    event: dict[str, Any],

) -> None:

    conn.execute(

        """

        INSERT INTO events (

            event_id,

            session_id,

            event_type,

            event_category,

            start_time_ms,

            end_time_ms,

            severity,

            confidence,

            source,

            detection_method,

            detection_version,

            trigger_observation_id,

            description,

            road_context,

            driving_context,

            latitude,

            longitude,

            data_origin,

            is_ground_truth,

            metadata_json

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        """,

        (

            uuid7(),

            session_id,

            event["event_type"],

            event["event_category"],

            event["start_time_ms"],

            event["end_time_ms"],

            event["severity"],

            event["confidence"],

            event["source"],

            event["detection_method"],

            event["detection_version"],

            event["trigger_observation_id"],

            event["description"],

            event["road_context"],

            event["driving_context"],

            event["latitude"],

            event["longitude"],

            event["data_origin"],

            0,

            json.dumps(

                event["metadata"],

                ensure_ascii=False,

                sort_keys=True,

            ),

        ),

    )





def choose_session(

    conn: sqlite3.Connection,

    session_id: str | None,

) -> str:

    if session_id:

        row = conn.execute(

            "SELECT session_id FROM sessions WHERE session_id = ?",

            (session_id,),

        ).fetchone()

        if row is None:

            raise ValueError(

                f"Session not found: {session_id}"

            )

        return session_id



    row = conn.execute(

        """

        SELECT session_id

        FROM sessions

        ORDER BY created_at_ms DESC, rowid DESC

        LIMIT 1

        """

    ).fetchone()



    if row is None:

        raise ValueError(

            "No sessions found. Run synthetic_generator.py first."

        )



    return row["session_id"]





def run_detector(

    session_id: str | None = None,

    replace_detected_events: bool = False,

) -> dict[str, Any]:

    rules = load_rules()



    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")



    try:

        selected_session = choose_session(conn, session_id)



        if replace_detected_events:

            conn.execute(

                """

                DELETE FROM events

                WHERE session_id = ?

                  AND is_ground_truth = 0

                  AND detection_method = 'rule'

                """,

                (selected_session,),

            )



        grouped = load_observations(

            conn,

            selected_session,

        )



        detected, abstained_count = detect_events(

            rules,

            grouped,

        )



        for event in detected:

            insert_event(

                conn,

                selected_session,

                event,

            )



        conn.commit()



        return {

            "session_id": selected_session,

            "detector_version": DETECTOR_VERSION,

            "schema_version": SCHEMA_VERSION,

            "minimum_confidence": float(
                rules.get("global", {})
                .get("detection", {})
                .get("minimum_confidence", 0.0)
            ),
            "events_detected": len(detected),
            "events_abstained": abstained_count,

            "event_types": [

                event["event_type"]

                for event in detected

            ],

        }



    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()





def main() -> None:

    parser = argparse.ArgumentParser(

        description="Run the RaahiSense rule-based event detector."

    )

    parser.add_argument(

        "--session-id",

        default=None,

        help="Specific session UUID. Defaults to the most recently created session.",

    )

    parser.add_argument(

        "--replace",

        action="store_true",

        help="Delete existing rule-detected events for this session before detection.",

    )



    args = parser.parse_args()



    result = run_detector(

        session_id=args.session_id,

        replace_detected_events=args.replace,

    )



    print("=" * 72)

    print("RaahiSense event detection completed")

    print("=" * 72)

    print(f"Session ID       : {result['session_id']}")

    print(f"Detector version : {result['detector_version']}")

    print(f"Min confidence   : {result['minimum_confidence']:.2f}")
    print(f"Events detected  : {result['events_detected']}")
    print(f"Events abstained : {result['events_abstained']}")



    if result["event_types"]:

        print("Detected events  :")

        for event_type in result["event_types"]:

            print(f"  - {event_type}")

    else:

        print("Detected events  : none")



    print("=" * 72)





if __name__ == "__main__":

    main()
