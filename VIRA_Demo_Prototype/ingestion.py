"""
VIRA — Data Ingestion Pipeline
Handles ingestion of genuine TIAND multimodal observations (GNSS, camera frames),
generation of synthetic Indian road-user activity demonstration scenarios,
and user-uploaded CSV validation.
"""

import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from database import (
    DEFAULT_DB_PATH,
    get_db_connection,
    init_database,
    insert_evidence_records_batch,
    upsert_scene,
)

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIAND_GNSS_REL_PATH = os.path.join(
    "data", "raw", "TIAND_MULTIMODAL_DATASET", "GNSS", "GNSS", "scene3-novatel-oem7-inspva.csv"
)
TIAND_CAM_FRONT_REL_PATH = os.path.join(
    "data", "raw", "TIAND_MULTIMODAL_DATASET", "CAMERA", "CAMERA", "CAMERA_Front"
)


def extract_genuine_tiand_observations(
    repo_root: str = REPO_ROOT,
    max_duration_s: float = 30.0,
    sample_interval_s: float = 1.0,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Extract genuine observations from TIAND GNSS and camera folders without synthesizing
    unobserved measurements.
    """
    gnss_full_path = os.path.join(repo_root, TIAND_GNSS_REL_PATH)
    cam_front_full_path = os.path.join(repo_root, TIAND_CAM_FRONT_REL_PATH)

    scene_id = "TIAND_SCENE_03_HYD"
    scene_meta = {
        "scene_id": scene_id,
        "name": "TIAND Genuine Multimodal Scene 03 (Hyderabad Urban Corridor)",
        "location": "Gachibowli, Hyderabad, Telangana, India",
        "duration_s": max_duration_s,
        "description": "Genuine recorded GNSS telemetry (NovAtel OEM7 INSPVA) and synchronized front camera recordings from the Indian driving TIAND dataset.",
        "data_origin": "TIAND",
        "primary_road_context": "Urban Multi-lane Arterial (TIAND Genuine Ground Truth)",
    }

    records: List[Dict[str, Any]] = []

    if not os.path.isfile(gnss_full_path):
        logger.warning("Genuine TIAND GNSS file not found at: %s", gnss_full_path)
        return scene_meta, records

    # Read GNSS file
    try:
        df_gnss = pd.read_csv(gnss_full_path)
    except Exception as e:
        logger.error("Failed to read TIAND GNSS file: %s", e)
        return scene_meta, records

    # Parse start time from header stamp or time string
    # e.g. time: '2023/09/02/13:19:16.462751'
    t0_secs = float(df_gnss.iloc[0][".header.stamp.secs"]) + float(df_gnss.iloc[0][".header.stamp.nsecs"]) * 1e-9

    # Find available front camera images for visual reference
    available_camera_files: List[Tuple[float, str]] = []
    if os.path.isdir(cam_front_full_path):
        for fname in sorted(os.listdir(cam_front_full_path)):
            if fname.lower().endswith((".jpg", ".png")):
                # Parse timestamp from filename: '13-19-16.476513.jpg'
                parts = fname.replace(".jpg", "").replace(".png", "").split("-")
                if len(parts) >= 3:
                    try:
                        h = int(parts[0])
                        m = int(parts[1])
                        s_float = float(parts[2])
                        # Seconds of day
                        t_sec_day = h * 3600 + m * 60 + s_float
                        available_camera_files.append((t_sec_day, fname))
                    except Exception:
                        pass

    # Downsample GNSS records
    last_sampled_t = -999.0
    rec_counter = 1

    for idx, row in df_gnss.iterrows():
        t_current = float(row[".header.stamp.secs"]) + float(row[".header.stamp.nsecs"]) * 1e-9
        rel_s = round(t_current - t0_secs, 2)
        if rel_s > max_duration_s:
            break
        if rel_s - last_sampled_t < sample_interval_s:
            continue

        last_sampled_t = rel_s

        # Speed calculation from genuine velocity vectors
        vn = float(row[".north_velocity"])
        ve = float(row[".east_velocity"])
        vu = float(row[".up_velocity"])
        speed_ms = math.sqrt(vn * vn + ve * ve + vu * vu)
        speed_kmh = round(speed_ms * 3.6, 1)

        lat = round(float(row[".latitude"]), 6)
        lon = round(float(row[".longitude"]), 6)
        alt = round(float(row[".height"]), 1)
        azimuth = round(float(row[".azimuth"]), 1)

        # Match front camera frame within 0.2s if available
        matched_cam = ""
        # 13:19:16 is starting time
        if available_camera_files:
            # Approx seconds of day for t_current
            dt_row = datetime.fromtimestamp(t_current, tz=timezone.utc)
            t_sec_row = dt_row.hour * 3600 + dt_row.minute * 60 + dt_row.second + dt_row.microsecond * 1e-6
            best_diff = 999.0
            for cam_t, cam_fn in available_camera_files:
                diff = abs(cam_t - t_sec_row)
                if diff < best_diff and diff < 0.5:
                    best_diff = diff
                    matched_cam = f"CAMERA_Front/{cam_fn}"

        rec_id = f"REC-TIAND-{rec_counter:04d}"
        iso_str = row["time"].replace("/", "-").replace("-", ":", 2)
        if len(iso_str) > 10 and iso_str[10] == ":":
            iso_str = iso_str[:10] + "T" + iso_str[11:] + "Z"

        desc = (
            f"Genuine TIAND GNSS Telemetry: Ego-vehicle speed {speed_kmh} km/h, heading {azimuth}° (azimuth). "
            f"Coordinates: {lat}°N, {lon}°E, altitude {alt}m. NovAtel OEM7 INS sequence {int(row['.header.seq'])}."
        )

        metadata = {
            "source_hardware": "NovAtel OEM7 INSPVA",
            "speed_kmh": speed_kmh,
            "latitude": lat,
            "longitude": lon,
            "altitude_m": alt,
            "heading_deg": azimuth,
            "matched_camera_frame": matched_cam,
            "raw_seq": int(row[".header.seq"]),
        }

        records.append(
            {
                "record_id": rec_id,
                "scene_id": scene_id,
                "timestamp_iso": iso_str,
                "timestamp_relative_s": rel_s,
                "event_type": "EGO_TELEMETRY",
                "road_user_category": "ego_vehicle",
                "observation_description": desc,
                "source_sensor": "TIAND_GNSS_OEM7",
                "confidence": 1.0,
                "road_context": "Urban Multi-lane Arterial (Hyderabad)",
                "evidence_reference": matched_cam or f"GNSS_ROW:{idx}",
                "data_origin": "TIAND",
                "status": "observed",
                "metadata_json": metadata,
            }
        )
        rec_counter += 1

    return scene_meta, records


def generate_synthetic_demonstration_scenes() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate rich synthetic Indian road-user activity demonstration scenarios.
    All records are explicitly marked data_origin='synthetic_demo_data'.
    Direct sensor/detector detections are status='observed'.
    Causal explanations/driver decisions are status='inferred'.
    """
    scenes: List[Dict[str, Any]] = [
        {
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "name": "Bengaluru Outer Ring Road Mixed Junction (Simulated Scenario)",
            "location": "Outer Ring Road (Bellandur Junction), Bengaluru, Karnataka, India",
            "duration_s": 25.0,
            "description": "Simulated multi-modal interaction scenario: sudden auto-rickshaw cut-in, ego emergency braking, and motorcycle evasion under high-density Indian traffic conditions.",
            "data_origin": "synthetic_demo_data",
            "primary_road_context": "Signalized Junction / Mixed Density / Two-Wheelers & Auto-Rickshaws",
        },
        {
            "scene_id": "DEMO_PEDESTRIAN_URBAN_02",
            "name": "Delhi MG Road Unmarked Pedestrian Crossing (Simulated Scenario)",
            "location": "MG Road Corridor, New Delhi / Gurugram Border, India",
            "duration_s": 20.0,
            "description": "Simulated mid-block pedestrian crossing scenario where pedestrians emerge from behind a stationary DTC bus near an informal median gap.",
            "data_origin": "synthetic_demo_data",
            "primary_road_context": "Unmarked Mid-block Pedestrian Crossing with Median Barrier Gap",
        },
    ]

    records: List[Dict[str, Any]] = []

    # ==========================================
    # SCENE 1: DEMO_INDIAN_JUNCTION_01
    # ==========================================
    s1_data = [
        {
            "record_id": "REC-SIM-001",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:00.000Z",
            "timestamp_relative_s": 0.0,
            "event_type": "EGO_TELEMETRY",
            "road_user_category": "ego_vehicle",
            "observation_description": "Ego-vehicle cruising steadily at 42.0 km/h in central lane. Throttle position: 22%. Steering angle: 0.2°.",
            "source_sensor": "SIM_VEHICLE_CAN",
            "confidence": 1.0,
            "road_context": "Signalized Junction Approach / 3-Lane Arterial",
            "evidence_reference": "SIM_CAN_FRAME:0001",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"speed_kmh": 42.0, "acceleration_ms2": 0.05, "lane_id": "center_lane"},
        },
        {
            "record_id": "REC-SIM-002",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:04.200Z",
            "timestamp_relative_s": 4.2,
            "event_type": "ROAD_USER_DETECTION",
            "road_user_category": "two_wheeler",
            "observation_description": "Two motorized two-wheelers (Hero Splendor, Honda Activa) detected on left flank at 1.8m lateral distance, overtaking ego vehicle at 48 km/h.",
            "source_sensor": "SIM_CAMERA_DETECTOR",
            "confidence": 0.94,
            "road_context": "Mixed Traffic / Lane Filtering Zone",
            "evidence_reference": "CAM_DET_FRAME:0126",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"users_detected": 2, "relative_speed_kmh": 6.0, "lateral_distance_m": 1.8},
        },
        {
            "record_id": "REC-SIM-003",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:08.500Z",
            "timestamp_relative_s": 8.5,
            "event_type": "ROAD_USER_DETECTION",
            "road_user_category": "auto_rickshaw",
            "observation_description": "Green-yellow Bajaj Compact auto-rickshaw detected in left nearside lane moving at 34 km/h, 14.5m ahead of ego vehicle.",
            "source_sensor": "SIM_CAMERA_RADAR_FUSION",
            "confidence": 0.96,
            "road_context": "Signalized Junction Approach",
            "evidence_reference": "FUSION_TRACK_ID:AR_44",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"target_id": "AR_44", "speed_kmh": 34.0, "longitudinal_distance_m": 14.5},
        },
        {
            "record_id": "REC-SIM-010",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:10.800Z",
            "timestamp_relative_s": 10.8,
            "event_type": "ROAD_USER_DETECTION",
            "road_user_category": "auto_rickshaw",
            "observation_description": "Auto-rickshaw AR_44 begins sharp rightward lateral drift from left lane without activating direction turn indicators.",
            "source_sensor": "SIM_CAMERA_DETECTOR",
            "confidence": 0.93,
            "road_context": "Signalized Junction Approach / Informal Merge",
            "evidence_reference": "CAM_DET_FRAME:0324",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"lateral_velocity_ms": 1.4, "indicator_status": "OFF"},
        },
        {
            "record_id": "REC-SIM-011",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:11.900Z",
            "timestamp_relative_s": 11.9,
            "event_type": "CUT_IN",
            "road_user_category": "auto_rickshaw",
            "observation_description": "Auto-rickshaw AR_44 executes sudden acute cut-in directly across ego trajectory at 2.4m longitudinal headway gap.",
            "source_sensor": "SIM_TEMPORAL_DETECTOR",
            "confidence": 0.95,
            "road_context": "Junction Merge Conflict Point",
            "evidence_reference": "CUTIN_EVENT:001",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"time_to_collision_s": 1.1, "headway_gap_m": 2.4, "yaw_angle_deg": 38.0},
        },
        {
            "record_id": "REC-SIM-012",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:12.400Z",
            "timestamp_relative_s": 12.4,
            "event_type": "SUDDEN_BRAKING",
            "road_user_category": "ego_vehicle",
            "observation_description": "Ego-vehicle executes emergency deceleration spike of -3.8 m/s²; ego speed drops rapidly from 40.5 km/h to 18.2 km/h in 1.2 seconds.",
            "source_sensor": "SIM_IMU_WHEEL_SPEED",
            "confidence": 0.99,
            "road_context": "Junction Center Lane",
            "evidence_reference": "IMU_PEAK_DECEL:12.4s",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"peak_deceleration_ms2": -3.8, "initial_speed_kmh": 40.5, "post_speed_kmh": 18.2},
        },
        {
            "record_id": "REC-SIM-013",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:12.800Z",
            "timestamp_relative_s": 12.8,
            "event_type": "INFERRED_DECISION",
            "road_user_category": "ego_vehicle",
            "observation_description": "INFERRED: Ego deceleration was provoked by the abrupt cut-in of auto-rickshaw AR_44 to avert imminent frontal collision. Driver intent itself is unobserved.",
            "source_sensor": "TEMPORAL_REASONING_ENGINE",
            "confidence": 0.88,
            "road_context": "Junction Center Lane",
            "evidence_reference": "INFERRED_RULE_TEMPORAL_PROXIMITY_CUTIN",
            "data_origin": "synthetic_demo_data",
            "status": "inferred",
            "metadata_json": {"hypothesis": "Collision Avoidance Deceleration", "causal_predecessor": "REC-SIM-011"},
        },
        {
            "record_id": "REC-SIM-014",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:13.600Z",
            "timestamp_relative_s": 13.6,
            "event_type": "NEAR_COLLISION",
            "road_user_category": "two_wheeler",
            "observation_description": "Trailing motorcycle in rear camera field swerves sharply towards road shoulder to avoid rear-ending the rapidly decelerating ego vehicle.",
            "source_sensor": "SIM_REAR_CAMERA_DETECTOR",
            "confidence": 0.91,
            "road_context": "Trailing Queue Dynamics",
            "evidence_reference": "REAR_CAM_EVASION:0408",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"min_rear_clearance_m": 1.2, "motorcycle_lateral_offset_m": 1.5},
        },
        {
            "record_id": "REC-SIM-015",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:16.200Z",
            "timestamp_relative_s": 16.2,
            "event_type": "TRAFFIC_SIGNAL_CHANGE",
            "road_user_category": "none",
            "observation_description": "Overhead gantry traffic signal transitions from Amber to Red ahead of junction stop line.",
            "source_sensor": "SIM_CAMERA_TRAFFIC_LIGHT_CLASSIFIER",
            "confidence": 0.98,
            "road_context": "Signalized Junction Stop Line",
            "evidence_reference": "TRAFFIC_LIGHT_DET:0486",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"signal_state": "RED", "distance_to_stop_line_m": 22.0},
        },
        {
            "record_id": "REC-SIM-016",
            "scene_id": "DEMO_INDIAN_JUNCTION_01",
            "timestamp_iso": "2024-03-15T09:30:20.000Z",
            "timestamp_relative_s": 20.0,
            "event_type": "EGO_TELEMETRY",
            "road_user_category": "ego_vehicle",
            "observation_description": "Ego-vehicle comes to complete standstill (0.0 km/h) behind queued auto-rickshaw AR_44 at the red signal.",
            "source_sensor": "SIM_VEHICLE_CAN",
            "confidence": 1.0,
            "road_context": "Signalized Junction Stop Line",
            "evidence_reference": "SIM_CAN_FRAME:0600",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"speed_kmh": 0.0, "stationary": True},
        },
    ]
    records.extend(s1_data)

    # ==========================================
    # SCENE 2: DEMO_PEDESTRIAN_URBAN_02
    # ==========================================
    s2_data = [
        {
            "record_id": "REC-SIM-020",
            "scene_id": "DEMO_PEDESTRIAN_URBAN_02",
            "timestamp_iso": "2024-03-15T11:15:02.000Z",
            "timestamp_relative_s": 2.0,
            "event_type": "ROAD_USER_DETECTION",
            "road_user_category": "bus",
            "observation_description": "Stationary green low-floor DTC transit bus stopped in curbside bus bay with hazard indicators flashing.",
            "source_sensor": "SIM_CAMERA_DETECTOR",
            "confidence": 0.97,
            "road_context": "Urban Arterial Corridor / Curbside Bus Stop",
            "evidence_reference": "CAM_BUS_DET:0060",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"vehicle_type": "DTC_bus", "state": "stationary", "lateral_position": "left_curb"},
        },
        {
            "record_id": "REC-SIM-021",
            "scene_id": "DEMO_PEDESTRIAN_URBAN_02",
            "timestamp_iso": "2024-03-15T11:15:06.100Z",
            "timestamp_relative_s": 6.1,
            "event_type": "ROAD_USER_DETECTION",
            "road_user_category": "pedestrian",
            "observation_description": "Pedestrian (adult male carrying shoulder bag) emerges from blind zone directly in front of the stationary bus onto the roadway.",
            "source_sensor": "SIM_CAMERA_DETECTOR",
            "confidence": 0.91,
            "road_context": "Unmarked Mid-block Crossing Point",
            "evidence_reference": "CAM_PED_DET:0183",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"pedestrian_speed_ms": 1.2, "occlusion_origin": "bus_frontal_blindspot"},
        },
        {
            "record_id": "REC-SIM-022",
            "scene_id": "DEMO_PEDESTRIAN_URBAN_02",
            "timestamp_iso": "2024-03-15T11:15:07.500Z",
            "timestamp_relative_s": 7.5,
            "event_type": "PEDESTRIAN_INTERACTION",
            "road_user_category": "pedestrian",
            "observation_description": "Pedestrian hesitates and raises right hand towards oncoming ego vehicle at 8.2m longitudinal distance.",
            "source_sensor": "SIM_CAMERA_POSE_ESTIMATION",
            "confidence": 0.89,
            "road_context": "Mid-block Carriageway",
            "evidence_reference": "POSE_GESTURE:0225",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"gesture": "hand_raise_caution", "longitudinal_distance_m": 8.2},
        },
        {
            "record_id": "REC-SIM-023",
            "scene_id": "DEMO_PEDESTRIAN_URBAN_02",
            "timestamp_iso": "2024-03-15T11:15:08.200Z",
            "timestamp_relative_s": 8.2,
            "event_type": "SUDDEN_BRAKING",
            "road_user_category": "ego_vehicle",
            "observation_description": "Ego-vehicle applies moderate-to-hard braking deceleration of -2.9 m/s², speed reducing from 38.0 km/h to 14.5 km/h; acoustic horn pulse logged.",
            "source_sensor": "SIM_VEHICLE_CAN",
            "confidence": 0.99,
            "road_context": "Mid-block Carriageway",
            "evidence_reference": "BRAKE_PRESSURE_LOG:0246",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"deceleration_ms2": -2.9, "speed_drop_kmh": 23.5, "horn_pulse": True},
        },
        {
            "record_id": "REC-SIM-024",
            "scene_id": "DEMO_PEDESTRIAN_URBAN_02",
            "timestamp_iso": "2024-03-15T11:15:10.500Z",
            "timestamp_relative_s": 10.5,
            "event_type": "PEDESTRIAN_INTERACTION",
            "road_user_category": "pedestrian",
            "observation_description": "Pedestrian expedites gait across ego lane and successfully crosses into the protected median barrier gap.",
            "source_sensor": "SIM_CAMERA_DETECTOR",
            "confidence": 0.95,
            "road_context": "Median Barrier Gap",
            "evidence_reference": "CAM_PED_DET:0315",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"pedestrian_exit_state": "median_island_cleared"},
        },
        {
            "record_id": "REC-SIM-025",
            "scene_id": "DEMO_PEDESTRIAN_URBAN_02",
            "timestamp_iso": "2024-03-15T11:15:13.000Z",
            "timestamp_relative_s": 13.0,
            "event_type": "EGO_TELEMETRY",
            "road_user_category": "ego_vehicle",
            "observation_description": "Ego-vehicle resumes forward acceleration; speed reaches 32.4 km/h as lane obstruction clears.",
            "source_sensor": "SIM_VEHICLE_CAN",
            "confidence": 1.0,
            "road_context": "Urban Arterial Corridor",
            "evidence_reference": "SIM_CAN_FRAME:0390",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
            "metadata_json": {"speed_kmh": 32.4, "acceleration_ms2": 1.1},
        },
    ]
    records.extend(s2_data)

    return scenes, records


def ingest_user_csv(file_obj_or_path: Any, db_path: str = DEFAULT_DB_PATH) -> Tuple[int, str]:
    """
    Validate and ingest a user-uploaded CSV file into the evidence store.
    Marks all imported records with data_origin='uploaded_data'.
    """
    try:
        if isinstance(file_obj_or_path, str):
            df = pd.read_csv(file_obj_or_path)
        else:
            df = pd.read_csv(file_obj_or_path)
    except Exception as e:
        return 0, f"CSV parsing error: {str(e)}"

    required_cols = {"record_id", "scene_id", "timestamp_relative_s", "observation_description"}
    missing = required_cols - set(df.columns)
    if missing:
        return 0, f"Missing required CSV columns: {', '.join(missing)}"

    # Register any new scenes
    scene_ids = df["scene_id"].unique()
    for s_id in scene_ids:
        upsert_scene(
            {
                "scene_id": str(s_id),
                "name": f"Uploaded Scene ({s_id})",
                "location": "User Defined Location",
                "duration_s": float(df[df["scene_id"] == s_id]["timestamp_relative_s"].max() or 0.0),
                "description": "User uploaded custom observation dataset.",
                "data_origin": "uploaded_data",
                "primary_road_context": "Custom Road Scene",
            },
            db_path=db_path,
        )

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        rec = {
            "record_id": str(row["record_id"]),
            "scene_id": str(row["scene_id"]),
            "timestamp_iso": str(row.get("timestamp_iso", datetime.now(timezone.utc).isoformat())),
            "timestamp_relative_s": float(row.get("timestamp_relative_s", 0.0)),
            "event_type": str(row.get("event_type", "USER_EVENT")),
            "road_user_category": str(row.get("road_user_category", "none")),
            "observation_description": str(row["observation_description"]),
            "source_sensor": str(row.get("source_sensor", "USER_UPLOAD")),
            "confidence": float(row.get("confidence", 1.0)),
            "road_context": str(row.get("road_context", "Custom Road Context")),
            "evidence_reference": str(row.get("evidence_reference", "CSV_ROW")),
            "data_origin": "uploaded_data",
            "status": str(row.get("status", "observed")),
            "metadata_json": str(row.get("metadata_json", "{}")),
        }
        records.append(rec)

    inserted = insert_evidence_records_batch(records, db_path=db_path)
    return inserted, f"Successfully imported {inserted} records from uploaded CSV."


def build_and_export_demonstration_dataset(
    db_path: str = DEFAULT_DB_PATH,
    export_csv_path: Optional[str] = None,
    export_json_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Populate database with genuine TIAND records and synthetic demonstration scenarios.
    Exports unified CSV and scenarios JSON.
    """
    init_database(db_path)

    # 1. Genuine TIAND
    tiand_scene, tiand_records = extract_genuine_tiand_observations(REPO_ROOT)
    upsert_scene(tiand_scene, db_path=db_path)
    tiand_inserted = insert_evidence_records_batch(tiand_records, db_path=db_path)

    # 2. Synthetic Indian scenarios
    synth_scenes, synth_records = generate_synthetic_demonstration_scenes()
    for s in synth_scenes:
        upsert_scene(s, db_path=db_path)
    synth_inserted = insert_evidence_records_batch(synth_records, db_path=db_path)

    all_scenes = [tiand_scene] + synth_scenes
    all_records = tiand_records + synth_records

    # 3. Export CSV if requested
    if export_csv_path:
        os.makedirs(os.path.dirname(os.path.abspath(export_csv_path)), exist_ok=True)
        df = pd.DataFrame(all_records)
        df.to_csv(export_csv_path, index=False)
        logger.info("Exported demonstration CSV to %s", export_csv_path)

    # 4. Export JSON if requested
    if export_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(export_json_path)), exist_ok=True)
        with open(export_json_path, "w", encoding="utf-8") as f:
            json.dump({"scenes": all_scenes, "records_count": len(all_records)}, f, indent=2)
        logger.info("Exported demonstration JSON to %s", export_json_path)

    return {
        "tiand_records_count": tiand_inserted,
        "synthetic_records_count": synth_inserted,
        "total_records": tiand_inserted + synth_inserted,
        "scenes_count": len(all_scenes),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    csv_out = os.path.join(data_dir, "sample_observations.csv")
    json_out = os.path.join(data_dir, "sample_scenarios.json")
    res = build_and_export_demonstration_dataset(
        export_csv_path=csv_out, export_json_path=json_out
    )
    print("Ingestion result:", res)
