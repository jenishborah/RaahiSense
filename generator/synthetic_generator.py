"""
RaahiSense synthetic scenario generator
----------------------------------------

Purpose
-------
Generate deterministic synthetic vehicle/road-user observations from:
    config/signal_dictionary.json
    config/scenario_schema.yaml

This generator intentionally produces:
    1. one session
    2. raw/normalized observations
    3. hidden ground-truth JSON

It does NOT produce:
    - detected events
    - detected contexts
    - event relationships

Those outputs belong to the downstream event detector, context detector,
and relationship engine.

Design constraints
------------------
- All timestamps are Unix epoch milliseconds.
- Signal frequency comes from signal_dictionary.json expected_frequency_hz.
- Scenario-level frequency overrides are supported.
- Synthetic data is marked data_origin='synthetic'.
- Ground truth is kept outside the retrieval database.
- Generation is deterministic for a fixed seed, scenario, variant, and start time.
- Missing data, timestamp jitter, source delay, and conflicting evidence are
  supported as dataset variants.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "database" / "raahisense.db"
SIGNAL_DICT_PATH = PROJECT_ROOT / "config" / "signal_dictionary.json"
EVENT_RULES_PATH = PROJECT_ROOT / "config" / "event_rules.yaml"
SCENARIO_SCHEMA_PATH = PROJECT_ROOT / "config" / "scenario_schema.yaml"

GENERATED_DIR = PROJECT_ROOT / "data" / "generated"

# 2024-01-01T00:00:00Z. A deterministic Unix epoch default.
DEFAULT_START_TIME_MS = 1704067200000

SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = "1.0.0"

SUPPORTED_VARIANTS = {
    "clean",
    "measurement_noise",
    "missing_1",
    "missing_5",
    "missing_10",
    "missing_20",
    "jitter_50",
    "jitter_100",
    "jitter_500",
    "source_delay",
    "conflicting_evidence",
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def uuid7_like(rng: random.Random) -> str:
    """
    Generate a UUIDv7-compatible-looking UUID deterministically.

    Python 3.12 does not expose uuid.uuid7(), so this creates a UUID with
    millisecond time bits and deterministic random bits.
    """
    timestamp_ms = int(rng.random() * (2**48 - 1))
    random_a = rng.getrandbits(12)
    random_b = rng.getrandbits(62)

    value = (
        (timestamp_ms & ((1 << 48) - 1)) << 80
        | (0x7 << 76)
        | (random_a << 64)
        | (0x2 << 62)
        | random_b
    )
    return str(uuid.UUID(int=value))


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).lower() in {"true", "1", "yes", "on"}


def iso_from_epoch_ms(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(
        timestamp_ms / 1000.0, tz=timezone.utc
    ).isoformat()


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def ensure_signals(
    conn: sqlite3.Connection,
    signal_dictionary: dict[str, Any],
) -> dict[str, str]:
    """
    Insert signal definitions into the frozen v1 signals table if absent.

    Returns:
        canonical_name -> signal_id
    """
    signal_ids: dict[str, str] = {}

    signals = signal_dictionary.get("signals", [])

    # Support either:
    #   {"signals": [...]}
    # or:
    #   {"signals": {"vehicle_speed": {...}}}
    if isinstance(signals, dict):
        iterable = []
        for canonical_name, definition in signals.items():
            definition = dict(definition or {})
            definition.setdefault("canonical_name", canonical_name)
            iterable.append(definition)
    else:
        iterable = signals

    for definition in iterable:
        canonical_name = definition["canonical_name"]
        signal_id = str(definition.get("signal_id") or uuid.uuid4())

        row = conn.execute(
            """
            SELECT signal_id
            FROM signals
            WHERE canonical_name = ?
            """,
            (canonical_name,),
        ).fetchone()

        if row:
            signal_ids[canonical_name] = row[0]
            continue

        conn.execute(
            """
            INSERT INTO signals (
                signal_id,
                canonical_name,
                display_name,
                category,
                subcategory,
                data_type,
                default_unit,
                description,
                min_value,
                max_value,
                expected_frequency_hz,
                source_type,
                is_derived,
                is_required,
                aggregation_method,
                quality_rule,
                schema_version,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                canonical_name,
                definition.get("display_name", canonical_name),
                definition.get("category"),
                definition.get("subcategory"),
                definition.get("data_type", "numeric"),
                definition.get("default_unit"),
                definition.get("description"),
                definition.get("min_value"),
                definition.get("max_value"),
                definition.get("expected_frequency_hz"),
                definition.get("source_type"),
                int(bool(definition.get("is_derived", False))),
                int(bool(definition.get("is_required", False))),
                definition.get("aggregation_method"),
                definition.get("quality_rule"),
                definition.get("schema_version", SCHEMA_VERSION),
                json.dumps(definition.get("metadata", {}), sort_keys=True),
            ),
        )

        signal_ids[canonical_name] = signal_id

    conn.commit()
    return signal_ids


# ---------------------------------------------------------------------------
# Scenario handling
# ---------------------------------------------------------------------------

def find_scenario(schema: dict[str, Any], scenario_id: str) -> dict[str, Any] | None:
    """
    Locate a named example scenario when present in the YAML.

    The current scenario_schema.yaml keeps the pedestrian crossing example
    under an examples section. This function also supports common alternative
    layouts so the generator is not tightly coupled to one nesting level.
    """
    candidates: list[Any] = []

    for key in ("examples", "example_scenarios", "scenarios"):
        value = schema.get(key)
        if isinstance(value, list):
            candidates.extend(value)
        elif isinstance(value, dict):
            candidates.extend(value.values())

    # Some versions may place an example directly at top level.
    for value in schema.values():
        if isinstance(value, dict) and value.get("scenario_id"):
            candidates.append(value)

    for item in candidates:
        if isinstance(item, dict) and item.get("scenario_id") == scenario_id:
            return item

    return None


def infer_family(scenario_id: str) -> str:
    value = scenario_id.lower()

    if "pedestrian" in value:
        return "PEDESTRIAN_CROSSING"
    if "cut" in value:
        return "VEHICLE_CUT_IN"
    if "highway" in value:
        return "HIGHWAY"
    if "stop" in value:
        return "STOP_AND_GO"
    if "dense" in value:
        return "DENSE_TRAFFIC"
    if "battery" in value:
        return "BATTERY_TEMPERATURE"
    if "sensor" in value:
        return "SENSOR_ANOMALY"
    if "communication" in value or "comm" in value:
        return "COMMUNICATION_ERROR"
    if "disengagement" in value or "adas" in value:
        return "ADAS_DISENGAGEMENT"

    return "NORMAL_CITY"


def default_scenario(scenario_id: str, seed: int, duration_s: float) -> dict[str, Any]:
    family = infer_family(scenario_id)

    scenario = {
        "scenario_id": scenario_id,
        "family": family,
        "seed": seed,
        "duration": duration_s,
        "environment": {
            "weather": "clear",
            "lighting": "day",
            "region": "India",
        },
        "road": {
            "road_type": "urban",
            "lanes": 2,
            "speed_limit_kmh": 50,
        },
        "traffic": {
            "traffic_level": "medium",
        },
        "ego": {
            "initial_speed_kmh": 40,
            "initial_soc": 78,
            "initial_battery_temp_c": 34,
            "initial_battery_power_kw": 18,
        },
        "signals": {
            "enabled": [],
        },
        "events": {
            "generation_enabled": False,
            "event_parameters": {
                "SHARP_BRAKING": {
                    "braking_threshold_ms2": -3.0,
                    "min_duration_ms": 200,
                }
            },
        },
        "contexts": {
            "generation_enabled": False,
        },
        "faults": {},
        "noise": {
            "measurement_noise": 0.05,
            "timestamp_jitter_ms": 0,
            "source_delay": False,
            "missing_data": {
                "enabled": False,
                "probability": 0.0,
            },
            "conflicting_evidence": False,
        },
        "ground_truth": {
            "enabled": True,
            "hidden_during_evaluation": True,
        },
    }

    # Family-specific parameters.
    if family == "HIGHWAY":
        scenario["road"].update({"road_type": "highway", "speed_limit_kmh": 100})
        scenario["ego"]["initial_speed_kmh"] = 85
        scenario["traffic"]["traffic_level"] = "low"

    elif family == "STOP_AND_GO":
        scenario["traffic"]["traffic_level"] = "high"
        scenario["ego"]["initial_speed_kmh"] = 20

    elif family == "DENSE_TRAFFIC":
        scenario["traffic"]["traffic_level"] = "very_high"
        scenario["ego"]["initial_speed_kmh"] = 25

    elif family == "PEDESTRIAN_CROSSING":
        scenario["ego"]["initial_speed_kmh"] = 40
        scenario["road"]["speed_limit_kmh"] = 50

    elif family == "BATTERY_TEMPERATURE":
        scenario["ego"]["initial_battery_temp_c"] = 38

    return scenario


# ---------------------------------------------------------------------------
# Frequency handling
# ---------------------------------------------------------------------------

def normalize_frequency(hz: float | int | None) -> float:
    if hz is None:
        return 1.0

    hz = float(hz)

    if hz <= 0:
        raise ValueError(f"Signal frequency must be > 0, got {hz}")

    return hz


def signal_frequency(
    definition: dict[str, Any],
    scenario: dict[str, Any],
    canonical_name: str,
) -> float:
    """
    Authoritative frequency:
        signal_dictionary.expected_frequency_hz
        overridden by scenario-level frequency override if supplied.
    """
    frequency = normalize_frequency(definition.get("expected_frequency_hz"))

    signals_cfg = scenario.get("signals", {})

    overrides = signals_cfg.get("frequency_overrides", {})
    if canonical_name in overrides:
        frequency = normalize_frequency(overrides[canonical_name])

    return frequency


def sample_times(
    duration_ms: int,
    frequency_hz: float,
) -> list[int]:
    """
    Generate relative timestamps for one signal.

    Supports:
        50 Hz -> 20 ms
        10 Hz -> 100 ms
        1 Hz  -> 1000 ms
        0.1 Hz -> 10000 ms
    """
    step = 1000.0 / frequency_hz
    times: list[int] = []

    t = 0.0
    while t <= duration_ms:
        times.append(int(round(t)))
        t += step

    return times


# ---------------------------------------------------------------------------
# Scenario signal synthesis
# ---------------------------------------------------------------------------

def event_time_ms(
    scenario: dict[str, Any],
    event_type: str,
    default_ms: int,
) -> int | None:
    for event in scenario.get("events", {}).get("targets", []) or []:
        if event.get("event_type") == event_type:
            if "start_time_ms" in event:
                return int(event["start_time_ms"])
            if "time_ms" in event:
                return int(event["time_ms"])

    for event in scenario.get("events", {}).get("events", []) or []:
        if event.get("event_type") == event_type:
            if "start_time_ms" in event:
                return int(event["start_time_ms"])
            if "time_ms" in event:
                return int(event["time_ms"])

    return default_ms


def scenario_event_targets(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    events_cfg = scenario.get("events", {})

    for key in ("targets", "events", "ground_truth_events"):
        value = events_cfg.get(key)
        if isinstance(value, list):
            return value

    gt = scenario.get("ground_truth", {})
    value = gt.get("events")
    if isinstance(value, list):
        return value

    return []


def interpolate_piecewise(
    t_ms: int,
    base: float,
    changes: list[tuple[int, float]],
) -> float:
    result = base
    for change_time, value in sorted(changes):
        if t_ms >= change_time:
            result = value
        else:
            break
    return result


def is_within(t_ms: int, center_ms: int, window_ms: int) -> bool:
    return abs(t_ms - center_ms) <= window_ms


def generate_signal_value(
    canonical_name: str,
    t_ms: int,
    duration_ms: int,
    scenario: dict[str, Any],
    rng: random.Random,
) -> Any:
    """
    Produce a deterministic synthetic value for a canonical signal.

    The generator models scenario effects but does not label detected events.
    """

    family = scenario.get("family", "NORMAL_CITY")
    ego = scenario.get("ego", {})
    traffic = scenario.get("traffic", {})
    road = scenario.get("road", {})

    initial_speed = float(ego.get("initial_speed_kmh", 40))
    speed_limit = float(road.get("speed_limit_kmh", 50))
    initial_soc = float(ego.get("initial_soc", 78))
    initial_temp = float(ego.get("initial_battery_temp_c", 34))
    initial_power = float(ego.get("initial_battery_power_kw", 18))

    pedestrian_t = event_time_ms(scenario, "PEDESTRIAN_DETECTED", 30_000)
    braking_t = event_time_ms(scenario, "SHARP_BRAKING", 42_000)

    # ------------------------------------------------------------------
    # Vehicle signals
    # ------------------------------------------------------------------

    if canonical_name == "vehicle_speed":
        value = initial_speed

        if family == "HIGHWAY":
            value = initial_speed + 3.0 * math.sin(t_ms / 12_000)
        elif family == "STOP_AND_GO":
            phase = (t_ms % 12_000) / 12_000
            value = 5 + 25 * abs(math.sin(phase * math.pi))
        elif family == "DENSE_TRAFFIC":
            value = 12 + 10 * abs(math.sin(t_ms / 7_000))
        else:
            value = initial_speed + 5 * math.sin(t_ms / 10_000)

        # Controlled braking episode.
        if braking_t is not None and braking_t <= t_ms <= braking_t + 2500:
            progress = (t_ms - braking_t) / 2500
            value = max(0.0, initial_speed * (1 - progress * 0.65))

        return clamp(value, 0, 250)

    if canonical_name == "vehicle_acceleration":
        value = 0.15 * math.sin(t_ms / 4000)

        if braking_t is not None and braking_t <= t_ms <= braking_t + 800:
            # Peak approximately -4.5 m/s² so it is detectable under -3.0.
            progress = (t_ms - braking_t) / 800
            value = -4.5 * math.sin(math.pi * progress)

        return clamp(value, -15, 15)

    if canonical_name == "vehicle_deceleration":
        acceleration = generate_signal_value(
            "vehicle_acceleration", t_ms, duration_ms, scenario, rng
        )
        return clamp(max(0.0, -float(acceleration)), 0, 15)

    if canonical_name == "brake_pressure":
        if braking_t is not None and braking_t <= t_ms <= braking_t + 1200:
            progress = (t_ms - braking_t) / 1200
            return clamp(80 * math.sin(math.pi * progress), 0, 100)

        return clamp(5 + rng.random() * 3, 0, 100)

    if canonical_name == "steering_angle":
        return clamp(
            3.0 * math.sin(t_ms / 3500),
            -720,
            720,
        )

    if canonical_name == "throttle_position":
        if braking_t is not None and braking_t <= t_ms <= braking_t + 1500:
            return 0.0
        return clamp(
            35 + 10 * math.sin(t_ms / 5000),
            0,
            100,
        )

    if canonical_name == "heading":
        return (90.0 + 2.0 * math.sin(t_ms / 20_000)) % 360

    # ------------------------------------------------------------------
    # Battery / energy
    # ------------------------------------------------------------------

    if canonical_name == "battery_soc":
        elapsed_h = t_ms / 3_600_000
        consumption = max(0.0, initial_power) * elapsed_h * 0.15
        return clamp(initial_soc - consumption, 0, 100)

    if canonical_name == "battery_temperature":
        if family == "BATTERY_TEMPERATURE":
            return initial_temp + 10 * (t_ms / max(duration_ms, 1))
        return initial_temp + 0.5 * math.sin(t_ms / 20_000)

    if canonical_name == "battery_power":
        value = initial_power
        if canonical_name == "battery_power":
            speed = float(
                generate_signal_value(
                    "vehicle_speed", t_ms, duration_ms, scenario, rng
                )
            )
            value = 8 + 0.12 * speed

        if braking_t is not None and braking_t <= t_ms <= braking_t + 1500:
            value += 4

        return clamp(value, 0, 500)

    if canonical_name == "energy_consumption":
        speed = float(
            generate_signal_value(
                "vehicle_speed", t_ms, duration_ms, scenario, rng
            )
        )
        return max(0.0, 0.01 * speed)

    # ------------------------------------------------------------------
    # Road users / perception
    # ------------------------------------------------------------------

    if canonical_name == "pedestrian_detected":
        return (
            pedestrian_t is not None
            and pedestrian_t <= t_ms <= pedestrian_t + 2500
        )

    if canonical_name == "pedestrian_distance":
        if pedestrian_t is None:
            return 100.0

        delta = t_ms - pedestrian_t

        if delta < -3000:
            return 100.0
        if -3000 <= delta < 0:
            return clamp(35 + abs(delta) / 3000 * 30, 35, 65)
        if 0 <= delta <= 2500:
            return clamp(35 - delta / 2500 * 28, 7, 35)

        return 100.0

    if canonical_name == "vehicle_detected":
        if family in {"VEHICLE_CUT_IN", "DENSE_TRAFFIC"}:
            return (t_ms % 8000) < 4500
        return False

    if canonical_name == "vehicle_distance":
        if family in {"VEHICLE_CUT_IN", "DENSE_TRAFFIC"}:
            return 12 + 8 * abs(math.sin(t_ms / 5000))
        return 60.0

    # ------------------------------------------------------------------
    # ADAS booleans
    # ------------------------------------------------------------------

    if canonical_name == "collision_warning":
        pedestrian = bool(
            generate_signal_value(
                "pedestrian_detected", t_ms, duration_ms, scenario, rng
            )
        )
        return pedestrian and is_within(t_ms, int(pedestrian_t or 0), 1000)

    if canonical_name == "forward_collision_warning":
        vehicle = bool(
            generate_signal_value(
                "vehicle_detected", t_ms, duration_ms, scenario, rng
            )
        )
        distance = float(
            generate_signal_value(
                "vehicle_distance", t_ms, duration_ms, scenario, rng
            )
        )
        return vehicle and distance < 15

    if canonical_name == "lane_departure_warning":
        return (
            family == "ADAS_DISENGAGEMENT"
            and 20_000 <= t_ms <= 24_000
        )

    if canonical_name == "emergency_braking_active":
        return (
            braking_t is not None
            and braking_t <= t_ms <= braking_t + 1000
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    if canonical_name in {
        "diagnostic_warning",
        "diagnostic_fault",
        "system_error",
    }:
        if family == "SENSOR_ANOMALY":
            return t_ms >= 30_000
        if family == "COMMUNICATION_ERROR":
            return 25_000 <= t_ms <= 35_000
        return False

    # ------------------------------------------------------------------
    # GPS
    # ------------------------------------------------------------------

    if canonical_name == "gps_latitude":
        return 26.1445 + 0.0001 * math.sin(t_ms / 30_000)

    if canonical_name == "gps_longitude":
        return 91.7362 + 0.0001 * math.cos(t_ms / 30_000)

    if canonical_name == "gps_altitude":
        return 55.0 + 2.0 * math.sin(t_ms / 25_000)

    # ------------------------------------------------------------------
    # IMU
    # ------------------------------------------------------------------

    if canonical_name == "imu_accel_x":
        return 0.1 * math.sin(t_ms / 500)

    if canonical_name == "imu_accel_y":
        return 0.1 * math.cos(t_ms / 700)

    if canonical_name == "imu_accel_z":
        value = 9.81
        if braking_t is not None and braking_t <= t_ms <= braking_t + 800:
            value += 0.5
        return value

    # Fallback for future signals.
    return 0.0


# ---------------------------------------------------------------------------
# Noise / data quality
# ---------------------------------------------------------------------------

def variant_settings(
    scenario: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    noise = scenario.get("noise", {}) or {}

    measurement_noise = float(noise.get("measurement_noise", 0.05))
    jitter_ms = int(noise.get("timestamp_jitter_ms", 0))
    source_delay = bool(noise.get("source_delay", False))
    conflicting = bool(noise.get("conflicting_evidence", False))

    missing_cfg = noise.get("missing_data", {}) or {}
    missing_probability = (
        float(missing_cfg.get("probability", 0.0))
        if bool(missing_cfg.get("enabled", False))
        else 0.0
    )

    if variant == "clean":
        measurement_noise = 0.0
        jitter_ms = 0
        source_delay = False
        missing_probability = 0.0
        conflicting = False

    elif variant == "measurement_noise":
        measurement_noise = max(measurement_noise, 0.05)

    elif variant.startswith("missing_"):
        percentage = float(variant.split("_")[1])
        missing_probability = percentage / 100.0

    elif variant.startswith("jitter_"):
        jitter_ms = int(variant.split("_")[1])

    elif variant == "source_delay":
        source_delay = True

    elif variant == "conflicting_evidence":
        conflicting = True

    return {
        "measurement_noise": measurement_noise,
        "jitter_ms": jitter_ms,
        "source_delay": source_delay,
        "missing_probability": missing_probability,
        "conflicting": conflicting,
    }


def apply_measurement_noise(
    value: Any,
    definition: dict[str, Any],
    noise_level: float,
    rng: random.Random,
) -> Any:
    if noise_level <= 0:
        return value

    data_type = definition.get("data_type", "numeric")

    if data_type in {"boolean", "bool"}:
        return value

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value

    minimum = definition.get("min_value")
    maximum = definition.get("max_value")

    scale = 1.0

    if minimum is not None and maximum is not None:
        scale = max(abs(float(maximum) - float(minimum)), 1.0) * 0.01

    noisy = float(value) + rng.gauss(0, scale * noise_level)

    if minimum is not None:
        noisy = max(float(minimum), noisy)

    if maximum is not None:
        noisy = min(float(maximum), noisy)

    return noisy


def apply_conflicting_evidence(
    canonical_name: str,
    value: Any,
    t_ms: int,
    scenario: dict[str, Any],
) -> Any:
    """
    Create a controlled conflict in a small window.

    This is intentionally simple: perception/ADAS signals can disagree with
    the vehicle dynamics for a short period. The downstream detector should
    tolerate this and expose uncertainty rather than treating one source as
    unquestionable truth.
    """
    braking_t = event_time_ms(scenario, "SHARP_BRAKING", 42_000)

    if braking_t is None:
        return value

    if braking_t <= t_ms <= braking_t + 500:
        if canonical_name == "emergency_braking_active":
            return False

        if canonical_name == "brake_pressure":
            return 0.0

    return value


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def build_hidden_ground_truth(
    scenario: dict[str, Any],
    start_time_ms: int,
) -> dict[str, Any]:
    targets = scenario_event_targets(scenario)

    events: list[dict[str, Any]] = []

    if targets:
        for item in targets:
            event_type = item.get("event_type")
            start_rel = item.get(
                "start_time_ms",
                item.get("time_ms"),
            )

            if event_type is None or start_rel is None:
                continue

            end_rel = item.get("end_time_ms", start_rel)

            events.append(
                {
                    "event_type": event_type,
                    "start_time_ms": start_time_ms + int(start_rel),
                    "end_time_ms": start_time_ms + int(end_rel),
                    "scenario_relative_start_time_ms": int(start_rel),
                    "scenario_relative_end_time_ms": int(end_rel),
                }
            )

    # The current pedestrian-crossing example stores its event targets in
    # ground_truth when explicit event targets are absent.
    if not events:
        gt = scenario.get("ground_truth", {})
        for item in gt.get("events", []) or []:
            event_type = item.get("event_type")
            start_rel = item.get("start_time_ms", item.get("time_ms"))
            if event_type is None or start_rel is None:
                continue

            end_rel = item.get("end_time_ms", start_rel)

            events.append(
                {
                    "event_type": event_type,
                    "start_time_ms": start_time_ms + int(start_rel),
                    "end_time_ms": start_time_ms + int(end_rel),
                    "scenario_relative_start_time_ms": int(start_rel),
                    "scenario_relative_end_time_ms": int(end_rel),
                }
            )

    # Ensure the current controlled pedestrian-crossing scenario has the
    # intended evaluation targets even if the YAML uses a compact example.
    if not events and scenario.get("family") == "PEDESTRIAN_CROSSING":
        events = [
            {
                "event_type": "PEDESTRIAN_DETECTED",
                "start_time_ms": start_time_ms + 30_000,
                "end_time_ms": start_time_ms + 32_500,
                "scenario_relative_start_time_ms": 30_000,
                "scenario_relative_end_time_ms": 32_500,
            },
            {
                "event_type": "SHARP_BRAKING",
                "start_time_ms": start_time_ms + 42_000,
                "end_time_ms": start_time_ms + 42_800,
                "scenario_relative_start_time_ms": 42_000,
                "scenario_relative_end_time_ms": 42_800,
            },
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "retrieval_visible": False,
        "evaluation_only": True,
        "scenario_id": scenario["scenario_id"],
        "family": scenario.get("family"),
        "seed": scenario.get("seed"),
        "session_start_time_ms": start_time_ms,
        "events": events,
        "relationships": [
            {
                "source_event_type": "PEDESTRIAN_DETECTED",
                "target_event_type": "SHARP_BRAKING",
                "relationship_type": "PRECEDES",
                "max_delta_ms": 10_000,
                "causal_claim_allowed": False,
            }
        ],
        "notes": [
            "Ground truth is hidden from retrieval.",
            "Ground truth must not replace detector output.",
            "Temporal association does not establish causation.",
        ],
    }


# ---------------------------------------------------------------------------
# Database insertion
# ---------------------------------------------------------------------------

def insert_session(
    conn: sqlite3.Connection,
    session_id: str,
    scenario: dict[str, Any],
    start_time_ms: int,
    end_time_ms: int,
) -> None:
    ego = scenario.get("ego", {})
    environment = scenario.get("environment", {})
    road = scenario.get("road", {})
    traffic = scenario.get("traffic", {})

    conn.execute(
        """
        INSERT INTO sessions (
            session_id,
            vehicle_id,
            scenario_id,
            session_name,
            start_time_ms,
            end_time_ms,
            data_origin,
            generator_version,
            schema_version,
            road_type,
            traffic_level,
            weather,
            lighting,
            region,
            latitude_start,
            longitude_start,
            latitude_end,
            longitude_end,
            distance_km,
            initial_soc,
            final_soc,
            initial_battery_temp_c,
            final_battery_temp_c,
            created_at_ms,
            metadata_json
        )
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            "synthetic_vehicle_001",
            scenario["scenario_id"],
            f"Synthetic {scenario['scenario_id']}",
            start_time_ms,
            end_time_ms,
            "synthetic",
            GENERATOR_VERSION,
            SCHEMA_VERSION,
            road.get("road_type"),
            traffic.get("traffic_level"),
            environment.get("weather"),
            environment.get("lighting"),
            environment.get("region"),
            26.1445,
            91.7362,
            26.1445,
            91.7362,
            None,
            ego.get("initial_soc"),
            None,
            ego.get("initial_battery_temp_c"),
            None,
            start_time_ms,
            json.dumps(
                {
                    "seed": scenario.get("seed"),
                    "family": scenario.get("family"),
                    "generator": GENERATOR_VERSION,
                },
                sort_keys=True,
            ),
        ),
    )


def insert_observation(
    conn: sqlite3.Connection,
    observation_id: str,
    session_id: str,
    signal_id: str,
    canonical_name: str,
    timestamp_ms: int,
    source_timestamp_ms: int,
    value: Any,
    definition: dict[str, Any],
    quality: str,
    quality_score: float,
    confidence: float,
    is_missing: bool,
    is_interpolated: bool,
    is_outlier: bool,
    scenario: dict[str, Any],
) -> None:
    data_type = definition.get("data_type", "numeric")

    value_num = None
    value_text = None
    value_bool = None
    value_int = None
    value_json = None

    if not is_missing:
        if data_type in {"numeric", "float"} and isinstance(value, (int, float)):
            value_num = float(value)
        elif data_type == "integer":
            value_int = int(value)
        elif data_type in {"boolean", "bool"}:
            value_bool = int(bool(value))
        elif data_type == "text":
            value_text = str(value)
        else:
            value_json = json.dumps(value, sort_keys=True)

    conn.execute(
        """
        INSERT INTO observations (
            observation_id,
            session_id,
            signal_id,
            timestamp_ms,
            sequence_no,
            source,
            value_num,
            value_text,
            value_bool,
            value_int,
            value_json,
            unit,
            quality,
            quality_score,
            confidence,
            is_missing,
            is_interpolated,
            is_outlier,
            road_context,
            driving_context,
            latitude,
            longitude,
            altitude_m,
            data_origin,
            source_reference,
            source_timestamp_ms,
            ingested_at_ms,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observation_id,
            session_id,
            signal_id,
            timestamp_ms,
            None,
            "synthetic_generator",
            value_num,
            value_text,
            value_bool,
            value_int,
            value_json,
            definition.get("default_unit"),
            quality,
            quality_score,
            confidence,
            int(is_missing),
            int(is_interpolated),
            int(is_outlier),
            scenario.get("road", {}).get("road_type"),
            scenario.get("family"),
            26.1445,
            91.7362,
            55.0,
            "synthetic",
            f"synthetic://{scenario['scenario_id']}/{canonical_name}",
            source_timestamp_ms,
            timestamp_ms,
            json.dumps(
                {
                    "generator_version": GENERATOR_VERSION,
                    "schema_version": SCHEMA_VERSION,
                },
                sort_keys=True,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate(
    scenario_id: str,
    seed: int,
    duration_s: float | None,
    variant: str,
    start_time_ms: int,
    replace_session: bool = True,
) -> dict[str, Any]:
    if variant not in SUPPORTED_VARIANTS:
        raise ValueError(
            f"Unsupported variant '{variant}'. "
            f"Choose one of: {', '.join(sorted(SUPPORTED_VARIANTS))}"
        )

    signal_dictionary = load_json(SIGNAL_DICT_PATH)
    event_rules = load_yaml(EVENT_RULES_PATH)
    scenario_schema = load_yaml(SCENARIO_SCHEMA_PATH)

    del event_rules  # Loaded intentionally so config validity is checked here.

    rng = random.Random(seed)

    scenario = find_scenario(scenario_schema, scenario_id)
    if scenario is None:
        scenario = default_scenario(
            scenario_id,
            seed,
            duration_s if duration_s is not None else 60.0,
        )
    else:
        scenario = json.loads(json.dumps(scenario))

        scenario["seed"] = seed

        if duration_s is not None:
            scenario["duration"] = duration_s

        scenario.setdefault("family", infer_family(scenario_id))
        scenario.setdefault("ego", {})
        scenario.setdefault("environment", {})
        scenario.setdefault("road", {})
        scenario.setdefault("traffic", {})
        scenario.setdefault("signals", {})
        scenario.setdefault("noise", {})

    duration_ms = int(float(scenario.get("duration", 60)) * 1000)

    session_id = uuid7_like(rng)
    end_time_ms = start_time_ms + duration_ms

    settings = variant_settings(scenario, variant)

    # Convert signal dictionary into a canonical mapping.
    raw_signals = signal_dictionary.get("signals", [])
    if isinstance(raw_signals, dict):
        signal_definitions = []
        for name, definition in raw_signals.items():
            item = dict(definition or {})
            item.setdefault("canonical_name", name)
            signal_definitions.append(item)
    else:
        signal_definitions = raw_signals

    enabled = scenario.get("signals", {}).get("enabled")

    enabled_set = set(enabled or [])

    if not enabled_set:
        enabled_set = {
            item["canonical_name"]
            for item in signal_definitions
            if item.get("is_required", False)
        }

    # If the scenario has an enabled list, only generate those signals.
    signal_definitions = [
        item
        for item in signal_definitions
        if item["canonical_name"] in enabled_set
    ]

    conn = connect_db()

    try:
        signal_ids = ensure_signals(conn, signal_dictionary)

        if replace_session:
            conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )

        insert_session(
            conn,
            session_id,
            scenario,
            start_time_ms,
            end_time_ms,
        )

        observation_count = 0
        missing_count = 0

        for definition in signal_definitions:
            canonical_name = definition["canonical_name"]
            signal_id = signal_ids.get(canonical_name)

            if signal_id is None:
                raise RuntimeError(
                    f"Signal '{canonical_name}' was not inserted/found in signals table."
                )

            frequency_hz = signal_frequency(
                definition,
                scenario,
                canonical_name,
            )

            relative_times = sample_times(duration_ms, frequency_hz)

            for sequence_no, relative_ms in enumerate(relative_times):
                source_timestamp_ms = start_time_ms + relative_ms

                jitter = 0
                if settings["jitter_ms"] > 0:
                    jitter = rng.randint(
                        -settings["jitter_ms"],
                        settings["jitter_ms"],
                    )

                timestamp_ms = source_timestamp_ms + jitter

                # Keep timestamps within the session bounds.
                timestamp_ms = max(
                    start_time_ms,
                    min(end_time_ms, timestamp_ms),
                )

                is_missing = (
                    settings["missing_probability"] > 0
                    and rng.random() < settings["missing_probability"]
                )

                value = generate_signal_value(
                    canonical_name,
                    relative_ms,
                    duration_ms,
                    scenario,
                    rng,
                )

                if settings["conflicting"]:
                    value = apply_conflicting_evidence(
                        canonical_name,
                        value,
                        relative_ms,
                        scenario,
                    )

                value = apply_measurement_noise(
                    value,
                    definition,
                    settings["measurement_noise"],
                    rng,
                )

                if is_missing:
                    quality = "missing"
                    quality_score = 0.0
                    confidence = 0.0
                    missing_count += 1
                elif settings["jitter_ms"] > 0:
                    quality = "valid"
                    quality_score = 0.95
                    confidence = 0.95
                elif settings["source_delay"]:
                    quality = "delayed"
                    quality_score = 0.90
                    confidence = 0.90
                elif settings["conflicting"]:
                    quality = "valid"
                    quality_score = 0.70
                    confidence = 0.70
                elif settings["measurement_noise"] > 0:
                    quality = "valid"
                    quality_score = 0.95
                    confidence = 0.95
                else:
                    quality = "valid"
                    quality_score = 1.0
                    confidence = 1.0

                if settings["source_delay"]:
                    # Keep source timestamp as the original measurement time.
                    timestamp_ms += 200

                    if timestamp_ms > end_time_ms:
                        timestamp_ms = end_time_ms

                observation_id = uuid7_like(rng)

                insert_observation(
                    conn=conn,
                    observation_id=observation_id,
                    session_id=session_id,
                    signal_id=signal_id,
                    canonical_name=canonical_name,
                    timestamp_ms=timestamp_ms,
                    source_timestamp_ms=source_timestamp_ms,
                    value=value,
                    definition=definition,
                    quality=quality,
                    quality_score=quality_score,
                    confidence=confidence,
                    is_missing=is_missing,
                    is_interpolated=False,
                    is_outlier=False,
                    scenario=scenario,
                )

                observation_count += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # Hidden ground truth is intentionally NOT inserted into events.
    ground_truth = build_hidden_ground_truth(
        scenario,
        start_time_ms,
    )

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    ground_truth_path = (
        GENERATED_DIR
        / f"{scenario_id}_{variant}_ground_truth.json"
    )

    metadata_path = (
        GENERATED_DIR
        / f"{scenario_id}_{variant}_metadata.json"
    )

    with ground_truth_path.open("w", encoding="utf-8") as f:
        json.dump(
            ground_truth,
            f,
            indent=2,
            sort_keys=True,
        )

    metadata = {
        "scenario_id": scenario_id,
        "session_id": session_id,
        "seed": seed,
        "variant": variant,
        "duration_ms": duration_ms,
        "start_time_ms": start_time_ms,
        "end_time_ms": end_time_ms,
        "start_time_utc": iso_from_epoch_ms(start_time_ms),
        "end_time_utc": iso_from_epoch_ms(end_time_ms),
        "data_origin": "synthetic",
        "generator_version": GENERATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "observation_count": observation_count,
        "missing_observation_count": missing_count,
        "ground_truth_file": str(ground_truth_path.relative_to(PROJECT_ROOT)),
        "retrieval_visible": False,
        "detected_events_generated": False,
        "detected_contexts_generated": False,
        "relationships_generated": False,
    }

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(
            metadata,
            f,
            indent=2,
            sort_keys=True,
        )

    return metadata


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one deterministic RaahiSense synthetic session."
    )

    parser.add_argument(
        "--scenario",
        default="pedestrian_crossing_001",
        help="Scenario ID.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=1042,
        help="Deterministic random seed.",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Override scenario duration in seconds.",
    )

    parser.add_argument(
        "--variant",
        choices=sorted(SUPPORTED_VARIANTS),
        default="clean",
        help="Controlled dataset variant.",
    )

    parser.add_argument(
        "--start-time-ms",
        type=int,
        default=DEFAULT_START_TIME_MS,
        help="Unix epoch start timestamp in milliseconds.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    metadata = generate(
        scenario_id=args.scenario,
        seed=args.seed,
        duration_s=args.duration,
        variant=args.variant,
        start_time_ms=args.start_time_ms,
    )

    print("=" * 72)
    print("RaahiSense synthetic generation completed")
    print("=" * 72)
    print(f"Scenario       : {metadata['scenario_id']}")
    print(f"Session ID     : {metadata['session_id']}")
    print(f"Seed           : {metadata['seed']}")
    print(f"Variant        : {metadata['variant']}")
    print(f"Start UTC      : {metadata['start_time_utc']}")
    print(f"End UTC        : {metadata['end_time_utc']}")
    print(f"Observations   : {metadata['observation_count']}")
    print(f"Missing        : {metadata['missing_observation_count']}")
    print(f"Ground truth   : {metadata['ground_truth_file']}")
    print()
    print("Detected events: NOT generated by this script")
    print("Contexts       : NOT generated by this script")
    print("Relationships   : NOT generated by this script")
    print("=" * 72)


if __name__ == "__main__":
    main()
