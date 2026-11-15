
"""
RaahiSense - Remaining Phase 1 Dataset Validation
=================================================

Checks:
1. IDD LiDAR numeric column profiles.
2. IDD camera/LiDAR frame-index correspondence.
3. IDD LiDAR timestamp-table inspection.
4. IDD OBD timestamp parsing and ordering.
5. TIAND sensor-file inventory.
6. TIAND radar CSV numeric profiling.
7. TIAND calibration-file inventory.
8. TIAND LiDAR-Camera and Radar-Camera synchronization.
9. TIAND camera/radar filename timestamp samples.

Install:
    pip install numpy pandas

Run from project root:
    python scripts/phase1_remaining_validation.py

Important:
- No sensor-column meanings are assumed.
- +/-50 ms is a diagnostic review threshold, not a documented tolerance.
- Synchronization offset = timestamp B minus timestamp A.
- Time-of-day differences use modulo 24 hours for midnight rollover.
- Filename/index overlap is not proof of synchronization.
"""

from __future__ import annotations

from pathlib import Path
import re
import json
import math
import warnings

import numpy as np
import pandas as pd


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(r"E:\JB_Mtech_Project\RaahiSense")
DATA_ROOT = PROJECT_ROOT / "data" / "raw"

IDD_PRIMARY = DATA_ROOT / "idd_multimodal" / "primary"
IDD_SECONDARY = DATA_ROOT / "idd_multimodal" / "secondary"
IDD_SUPPLEMENT = DATA_ROOT / "idd_multimodal" / "supplement"

TIAND_ROOT = DATA_ROOT / "TIAND_MULTIMODAL_DATASET"

TIAND_CAMERA = TIAND_ROOT / "CAMERA" / "CAMERA"
TIAND_GNSS = TIAND_ROOT / "GNSS" / "GNSS"
TIAND_LIDAR = TIAND_ROOT / "LIDAR"
TIAND_RADAR = TIAND_ROOT / "RADAR" / "RADAR"

TIAND_CALIBRATION = (
    TIAND_ROOT / "Calibration_files" / "Calibration_files"
)

TIAND_SYNC = (
    TIAND_ROOT
    / "Synchronisation_timestamps"
    / "Synchronisation_timestamps"
)

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "data"
    / "generated"
    / "phase1"
    / "remaining_validation"
)

IDD_SEQUENCES = ("d0", "d1", "d2")

SYNC_REVIEW_THRESHOLD_MS = 50.0

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp"
}

TEXT_EXTENSIONS = {
    ".json", ".txt", ".yaml", ".yml",
    ".xml", ".ini", ".cfg", ".csv",
    ".cal", ".conf"
}


# ============================================================
# 2. GENERAL HELPERS
# ============================================================

def ensure_output_dir():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def save_csv(rows, filename):
    ensure_output_dir()

    path = OUTPUT_ROOT / filename

    pd.DataFrame(rows).to_csv(
        path,
        index=False
    )

    print(f"[SAVED] {path}")

    return path


def find_files(folder, pattern="*"):

    if not folder.exists():
        print(f"[MISSING DIRECTORY] {folder}")
        return []

    return sorted(
        p for p in folder.rglob(pattern)
        if p.is_file()
    )


def read_csv_safely(path):

    last_error = None

    for encoding in (
        "utf-8",
        "utf-8-sig",
        "latin1"
    ):

        try:
            return pd.read_csv(
                path,
                encoding=encoding
            )

        except UnicodeDecodeError as exc:
            last_error = exc

    raise RuntimeError(
        f"Could not decode CSV {path}: {last_error}"
    )


def relative_to_root(path, root):

    try:
        return str(path.relative_to(root))

    except ValueError:
        return str(path)


def extract_numeric_stem(path):
    """
    Extract trailing integer from names such as:
    0001496.npy
    1496.jpg
    """

    match = re.search(
        r"(\d+)$",
        path.stem
    )

    return int(match.group(1)) if match else None


# ============================================================
# 3. TIMESTAMP PARSING
# ============================================================

def parse_time_to_seconds(value):
    """
    Supported formats:

    IDD:
        03-31-13-000000

    TIAND:
        13:19:16.491248
        13-19-16.516270

    Date-time:
        2023/09/02/13:19:16.462751

    Returns seconds since midnight.

    Does not infer timezone or clock synchronization.
    """

    if value is None:
        return np.nan

    if isinstance(value, float) and math.isnan(value):
        return np.nan

    text = str(value).strip()

    if not text or text.lower() in {
        "nan", "none", "nat"
    }:
        return np.nan

    # IDD: HH-MM-SS-ffffff

    match = re.fullmatch(
        r"(\d{1,2})-(\d{2})-(\d{2})-(\d{1,6})",
        text
    )

    if match:

        hour, minute, second, micros = match.groups()

        fraction = (
            int(micros.ljust(6, "0")[:6])
            / 1_000_000
        )

        return (
            int(hour) * 3600
            + int(minute) * 60
            + int(second)
            + fraction
        )

    # HH:MM:SS.fraction

    match = re.search(
        r"(?<!\d)(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?",
        text
    )

    if match:

        hour, minute, second, fraction = match.groups()

        fraction = (
            float("0." + fraction)
            if fraction else 0.0
        )

        return (
            int(hour) * 3600
            + int(minute) * 60
            + int(second)
            + fraction
        )

    # HH-MM-SS.fraction

    match = re.fullmatch(
        r"(\d{1,2})-(\d{2})-(\d{2})(?:\.(\d+))?",
        text
    )

    if match:

        hour, minute, second, fraction = match.groups()

        fraction = (
            float("0." + fraction)
            if fraction else 0.0
        )

        return (
            int(hour) * 3600
            + int(minute) * 60
            + int(second)
            + fraction
        )

    # Explicit date-time fallback

    try:

        with warnings.catch_warnings():

            warnings.simplefilter("ignore")

            dt = pd.to_datetime(
                text,
                errors="raise"
            )

        return (
            dt.hour * 3600
            + dt.minute * 60
            + dt.second
            + dt.microsecond / 1_000_000
        )

    except Exception:
        return np.nan


def parse_time_series(values):

    return values.map(
        parse_time_to_seconds
    ).astype("float64")


def modulo_day_difference_seconds(a, b):
    """
    Returns shortest signed difference b-a.

    Handles time-of-day rollover at midnight.
    """

    difference = b - a

    half_day = 12 * 60 * 60
    full_day = 24 * 60 * 60

    return (
        (difference + half_day) % full_day
    ) - half_day


def summarize_offsets(offset_ms, pair_name):

    values = pd.to_numeric(
        offset_ms,
        errors="coerce"
    ).dropna().to_numpy()

    invalid_count = int(
        pd.Series(offset_ms).isna().sum()
    )

    if len(values) == 0:

        return {
            "pair": pair_name,
            "valid_pairs": 0,
            "invalid_pairs": invalid_count,
            "mean_ms": np.nan,
            "median_ms": np.nan,
            "std_ms": np.nan,
            "min_ms": np.nan,
            "max_ms": np.nan,
            "p95_abs_ms": np.nan,
            "outliers_over_threshold": 0,
            "review_threshold_ms": SYNC_REVIEW_THRESHOLD_MS
        }

    return {

        "pair": pair_name,

        "valid_pairs": int(len(values)),

        "invalid_pairs": invalid_count,

        "mean_ms": float(np.mean(values)),

        "median_ms": float(np.median(values)),

        "std_ms": (
            float(np.std(values, ddof=1))
            if len(values) > 1 else 0.0
        ),

        "min_ms": float(np.min(values)),

        "max_ms": float(np.max(values)),

        "p95_abs_ms": float(
            np.percentile(np.abs(values), 95)
        ),

        "outliers_over_threshold": int(
            np.sum(
                np.abs(values) > SYNC_REVIEW_THRESHOLD_MS
            )
        ),

        "review_threshold_ms": SYNC_REVIEW_THRESHOLD_MS
    }


def print_path_status():

    paths = {

        "IDD primary": IDD_PRIMARY,

        "IDD secondary": IDD_SECONDARY,

        "IDD supplement": IDD_SUPPLEMENT,

        "TIAND root": TIAND_ROOT,

        "TIAND camera": TIAND_CAMERA,

        "TIAND GNSS": TIAND_GNSS,

        "TIAND LiDAR": TIAND_LIDAR,

        "TIAND radar": TIAND_RADAR,

        "TIAND calibration": TIAND_CALIBRATION,

        "TIAND synchronization": TIAND_SYNC
    }

    print("\n[PATH CHECK]")

    for name, path in paths.items():

        print(
            f"{name:24} | "
            f"exists={path.exists()} | {path}"
        )


# ============================================================
# 4. TASK 1 - IDD LIDAR NUMERIC COLUMN PROFILE
# ============================================================

def inspect_idd_lidar_columns():

    print("\n[1/8] IDD LiDAR numeric column profile")

    lidar_root = IDD_SUPPLEMENT / "lidar"

    files = find_files(
        lidar_root,
        "*.npy"
    )

    rows = []

    if not files:

        print("[WARNING] No IDD LiDAR .npy files found.")

        save_csv(
            rows,
            "01_idd_lidar_column_profile.csv"
        )

        return

    selected = []

    for sequence in IDD_SEQUENCES:

        sequence_files = [
            p for p in files
            if sequence in p.parts
        ]

        if sequence_files:

            indexes = sorted({
                0,
                len(sequence_files) // 2,
                len(sequence_files) - 1
            })

            selected.extend(
                sequence_files[i]
                for i in indexes
            )

    selected = list(dict.fromkeys(selected))

    for path in selected:

        try:

            array = np.load(
                path,
                mmap_mode="r",
                allow_pickle=False
            )

            if array.ndim != 2:

                rows.append({

                    "file": str(path),

                    "status": "unexpected_ndim",

                    "shape": str(array.shape),

                    "dtype": str(array.dtype)
                })

                continue

            for column_index in range(array.shape[1]):

                values = np.asarray(
                    array[:, column_index],
                    dtype=np.float64
                )

                finite = values[
                    np.isfinite(values)
                ]

                rows.append({

                    "file": str(path),

                    "sequence": next(
                        (
                            s for s in IDD_SEQUENCES
                            if s in path.parts
                        ),
                        ""
                    ),

                    "column_index": column_index,

                    "status": "success",

                    "point_count": int(len(values)),

                    "finite_count": int(len(finite)),

                    "nan_count": int(np.isnan(values).sum()),

                    "inf_count": int(np.isinf(values).sum()),

                    "min": (
                        float(np.min(finite))
                        if len(finite) else np.nan
                    ),

                    "p01": (
                        float(np.percentile(finite, 1))
                        if len(finite) else np.nan
                    ),

                    "median": (
                        float(np.median(finite))
                        if len(finite) else np.nan
                    ),

                    "mean": (
                        float(np.mean(finite))
                        if len(finite) else np.nan
                    ),

                    "p99": (
                        float(np.percentile(finite, 99))
                        if len(finite) else np.nan
                    ),

                    "max": (
                        float(np.max(finite))
                        if len(finite) else np.nan
                    ),

                    "std": (
                        float(np.std(finite))
                        if len(finite) else np.nan
                    ),

                    "unique_approx_first_10000": (
                        int(len(np.unique(finite[:10000])))
                        if len(finite) else 0
                    ),

                    "dtype": str(array.dtype),

                    "shape": str(array.shape)
                })

        except Exception as exc:

            rows.append({

                "file": str(path),

                "status": "error",

                "error": str(exc)
            })

    save_csv(
        rows,
        "01_idd_lidar_column_profile.csv"
    )

    print(
        "Numeric profiles only. "
        "Column meanings remain unverified."
    )


# ============================================================
# 5. TASK 2 - IDD CAMERA / LIDAR FRAME MAPPING
# ============================================================

def inspect_idd_frame_mapping():

    print(
        "\n[2/8] IDD camera/LiDAR frame correspondence"
    )

    rows = []

    all_timestamp_files = find_files(
        IDD_SUPPLEMENT / "lidar",
        "timestamp.csv"
    )

    for sequence in IDD_SEQUENCES:

        left_dir = (
            IDD_PRIMARY / sequence / "leftCamImgs"
        )

        right_dir = (
            IDD_SECONDARY / sequence / "rightCamImgs"
        )

        lidar_dir = (
            IDD_SUPPLEMENT / "lidar" / sequence
        )

        timestamp_path = next(
            (
                p for p in all_timestamp_files
                if sequence in p.parts
            ),
            lidar_dir / "timestamp.csv"
        )

        left_files = [
            p for p in find_files(left_dir)
            if p.suffix.lower() in IMAGE_EXTENSIONS
        ]

        right_files = [
            p for p in find_files(right_dir)
            if p.suffix.lower() in IMAGE_EXTENSIONS
        ]

        lidar_files = find_files(
            lidar_dir,
            "*.npy"
        )

        left_ids = {
            extract_numeric_stem(p)
            for p in left_files
        }

        right_ids = {
            extract_numeric_stem(p)
            for p in right_files
        }

        lidar_ids = {
            extract_numeric_stem(p)
            for p in lidar_files
        }

        left_ids.discard(None)
        right_ids.discard(None)
        lidar_ids.discard(None)

        rows.append({

            "sequence": sequence,

            "check": "file_index_overlap",

            "left_camera_files": len(left_files),

            "right_camera_files": len(right_files),

            "lidar_files": len(lidar_files),

            "left_right_common_numeric_ids": len(
                left_ids & right_ids
            ),

            "left_lidar_common_numeric_ids": len(
                left_ids & lidar_ids
            ),

            "right_lidar_common_numeric_ids": len(
                right_ids & lidar_ids
            ),

            "left_only_vs_right": len(
                left_ids - right_ids
            ),

            "right_only_vs_left": len(
                right_ids - left_ids
            ),

            "lidar_only_vs_left": len(
                lidar_ids - left_ids
            ),

            "timestamp_csv": str(timestamp_path),

            "timestamp_csv_exists": timestamp_path.exists()
        })

        # Inspect train, validation and test split mappings.

        for split_name in (
            "train",
            "val",
            "test"
        ):

            split_path = (
                IDD_PRIMARY
                / sequence
                / f"{split_name}.csv"
            )

            if not split_path.exists():
                continue

            try:

                split_df = read_csv_safely(
                    split_path
                )

                if "image_idx" not in split_df.columns:

                    rows.append({

                        "sequence": sequence,

                        "check": "split_image_idx",

                        "split": split_name,

                        "status": "image_idx_column_missing"
                    })

                    continue

                numeric_ids = (
                    pd.to_numeric(
                        split_df["image_idx"],
                        errors="coerce"
                    )
                    .dropna()
                    .astype("int64")
                )

                split_ids = set(
                    numeric_ids.tolist()
                )

                rows.append({

                    "sequence": sequence,

                    "check": "split_image_idx",

                    "split": split_name,

                    "split_rows": len(split_df),

                    "valid_image_idx_rows": len(numeric_ids),

                    "unique_image_idx": len(split_ids),

                    "image_idx_left_overlap": len(
                        split_ids & left_ids
                    ),

                    "image_idx_right_overlap": len(
                        split_ids & right_ids
                    ),

                    "image_idx_lidar_overlap": len(
                        split_ids & lidar_ids
                    ),

                    "image_idx_missing_left": len(
                        split_ids - left_ids
                    ),

                    "image_idx_missing_lidar": len(
                        split_ids - lidar_ids
                    ),

                    "image_idx_min": (
                        min(split_ids)
                        if split_ids else np.nan
                    ),

                    "image_idx_max": (
                        max(split_ids)
                        if split_ids else np.nan
                    )
                })

            except Exception as exc:

                rows.append({

                    "sequence": sequence,

                    "check": "split_image_idx",

                    "split": split_name,

                    "error": str(exc)
                })

        # Inspect LiDAR timestamp table.

        if timestamp_path.exists():

            try:

                timestamp_df = read_csv_safely(
                    timestamp_path
                )

                timestamp_df.columns = [
                    str(c).strip()
                    for c in timestamp_df.columns
                ]

                timestamp_df.to_csv(
                    OUTPUT_ROOT
                    / f"idd_{sequence}_timestamp_table_copy.csv",
                    index=False
                )

                frame_col = next(
                    (
                        c for c in timestamp_df.columns
                        if c.lower() in {
                            "frame",
                            "image_idx",
                            "frame_idx",
                            "lidar_idx"
                        }
                    ),
                    None
                )

                time_col = next(
                    (
                        c for c in timestamp_df.columns
                        if (
                            "timestamp" in c.lower()
                            or "datetime" in c.lower()
                            or c.lower() == "time"
                        )
                    ),
                    None
                )

                frame_values = (
                    pd.to_numeric(
                        timestamp_df[frame_col],
                        errors="coerce"
                    )
                    if frame_col
                    else pd.Series(dtype="float64")
                )

                parsed_times = (
                    parse_time_series(
                        timestamp_df[time_col]
                    )
                    if time_col
                    else pd.Series(dtype="float64")
                )

                rows.append({

                    "sequence": sequence,

                    "check": "lidar_timestamp_table",

                    "timestamp_file": str(timestamp_path),

                    "row_count": len(timestamp_df),

                    "columns": " | ".join(
                        timestamp_df.columns
                    ),

                    "frame_column": frame_col or "",

                    "timestamp_column": time_col or "",

                    "unique_frame_values": (
                        int(frame_values.nunique())
                        if frame_col else np.nan
                    ),

                    "duplicate_frame_values": (
                        int(frame_values.duplicated().sum())
                        if frame_col else np.nan
                    ),

                    "frame_min": (
                        frame_values.min()
                        if frame_col else np.nan
                    ),

                    "frame_max": (
                        frame_values.max()
                        if frame_col else np.nan
                    ),

                    "timestamp_parse_success": (
                        int(parsed_times.notna().sum())
                        if time_col else np.nan
                    ),

                    "timestamp_parse_failure": (
                        int(parsed_times.isna().sum())
                        if time_col else np.nan
                    ),

                    "first_raw_timestamp": (
                        str(timestamp_df[time_col].iloc[0])
                        if time_col and len(timestamp_df)
                        else ""
                    ),

                    "last_raw_timestamp": (
                        str(timestamp_df[time_col].iloc[-1])
                        if time_col and len(timestamp_df)
                        else ""
                    )
                })

            except Exception as exc:

                rows.append({

                    "sequence": sequence,

                    "check": "timestamp_table_read",

                    "error": str(exc)
                })

        else:

            rows.append({

                "sequence": sequence,

                "check": "lidar_timestamp_table",

                "status": "timestamp_csv_missing",

                "expected_path": str(timestamp_path)
            })

    save_csv(
        rows,
        "02_idd_frame_mapping_checks.csv"
    )

    print(
        "Index overlap is only a candidate mapping. "
        "Verify frame conventions using official documentation."
    )


# ============================================================
# 6. TASK 3 - IDD OBD TIMESTAMP VALIDATION
# ============================================================

def inspect_idd_obd_timestamps():

    print("\n[3/8] IDD OBD timestamp validation")

    rows = []

    obd_files = find_files(
        IDD_SUPPLEMENT / "obd",
        "obd.csv"
    )

    for sequence in IDD_SEQUENCES:

        path = next(
            (
                p for p in obd_files
                if sequence in p.parts
            ),
            None
        )

        if path is None:

            rows.append({

                "sequence": sequence,

                "status": "missing_obd_csv"
            })

            continue

        try:

            df = read_csv_safely(path)

            if "timestamp" not in df.columns:

                rows.append({

                    "sequence": sequence,

                    "status": "timestamp_column_missing",

                    "columns": " | ".join(
                        map(str, df.columns)
                    )
                })

                continue

            raw = df["timestamp"].astype(str)

            seconds = parse_time_series(raw)

            valid_seconds = seconds.dropna()

            # Calculate differences in original row order.
            # Adjust only large negative jumps as midnight rollover.

            diffs = valid_seconds.diff()

            adjusted = diffs.copy()

            rollover_count = 0

            for index in adjusted.index:

                value = adjusted.loc[index]

                if (
                    pd.notna(value)
                    and value < -(12 * 60 * 60)
                ):

                    adjusted.loc[index] = (
                        value + 24 * 60 * 60
                    )

                    rollover_count += 1

            output = df.copy()

            output["timestamp_raw"] = raw

            output[
                "timestamp_seconds_since_midnight"
            ] = seconds

            output[
                "timestamp_step_seconds_raw"
            ] = seconds.diff()

            output[
                "timestamp_step_seconds_midnight_adjusted"
            ] = adjusted.reindex(seconds.index)

            output.to_csv(
                OUTPUT_ROOT
                / f"idd_{sequence}_obd_timestamp_validation.csv",
                index=False
            )

            rows.append({

                "sequence": sequence,

                "status": "success",

                "file": str(path),

                "row_count": len(df),

                "valid_timestamps": int(
                    seconds.notna().sum()
                ),

                "invalid_timestamps": int(
                    seconds.isna().sum()
                ),

                "first_raw": (
                    raw.iloc[0] if len(raw) else ""
                ),

                "last_raw": (
                    raw.iloc[-1] if len(raw) else ""
                ),

                "first_seconds_since_midnight": (
                    seconds.iloc[0]
                    if len(seconds) else np.nan
                ),

                "last_seconds_since_midnight": (
                    seconds.iloc[-1]
                    if len(seconds) else np.nan
                ),

                "midnight_rollovers_detected": rollover_count,

                "non_increasing_steps_after_rollover_adjustment": int(
                    (adjusted.dropna() <= 0).sum()
                ),

                "median_interval_ms": (
                    float(adjusted.dropna().median() * 1000)
                    if adjusted.notna().any()
                    else np.nan
                ),

                "min_interval_ms": (
                    float(adjusted.dropna().min() * 1000)
                    if adjusted.notna().any()
                    else np.nan
                ),

                "max_interval_ms": (
                    float(adjusted.dropna().max() * 1000)
                    if adjusted.notna().any()
                    else np.nan
                )
            })

        except Exception as exc:

            rows.append({

                "sequence": sequence,

                "status": "error",

                "file": str(path),

                "error": str(exc)
            })

    save_csv(
        rows,
        "03_idd_obd_timestamp_report.csv"
    )

    print(
        "Time-of-day parsing does not establish "
        "clock synchronization with camera or LiDAR."
    )


# ============================================================
# 7. TASK 4 - TIAND SENSOR INVENTORY
# ============================================================

def inspect_tiand_sensor_inventory():

    print("\n[4/8] TIAND sensor file inventory")

    sensor_roots = {

        "camera": TIAND_CAMERA,

        "gnss": TIAND_GNSS,

        "lidar": TIAND_LIDAR,

        "radar": TIAND_RADAR,

        "calibration": TIAND_CALIBRATION,

        "synchronization": TIAND_SYNC
    }

    rows = []

    for sensor, folder in sensor_roots.items():

        files = find_files(folder)

        extension_counts = {}

        total_bytes = 0

        for path in files:

            extension = (
                path.suffix.lower()
                or "[no extension]"
            )

            extension_counts[extension] = (
                extension_counts.get(extension, 0) + 1
            )

            try:
                total_bytes += path.stat().st_size

            except OSError:
                pass

        rows.append({

            "component": sensor,

            "directory": str(folder),

            "directory_exists": folder.exists(),

            "file_count": len(files),

            "total_size_bytes": total_bytes,

            "total_size_gb": total_bytes / (1024 ** 3),

            "extension_counts_json": json.dumps(
                extension_counts,
                sort_keys=True
            ),

            "sample_files": " | ".join(
                str(p) for p in files[:5]
            )
        })

    save_csv(
        rows,
        "04_tiand_sensor_file_inventory.csv"
    )

    lidar_files = find_files(TIAND_LIDAR)

    print(
        f"TIAND LiDAR files actually found: {len(lidar_files)}"
    )

    if not lidar_files:

        print(
            "TIAND LiDAR directory exists but "
            "contains no files found by recursive inventory."
        )


# ============================================================
# 8. TASK 5 - TIAND RADAR COLUMN PROFILE
# ============================================================

def inspect_tiand_radar_columns():

    print(
        "\n[5/8] TIAND radar CSV structure and numeric profile"
    )

    files = find_files(
        TIAND_RADAR,
        "*.csv"
    )

    file_rows = []

    column_rows = []

    for path in files:

        try:

            df = read_csv_safely(path)

            numeric = df.apply(
                pd.to_numeric,
                errors="coerce"
            )

            relative_file = relative_to_root(
                path,
                TIAND_ROOT
            )

            file_rows.append({

                "relative_file": relative_file,

                "row_count": len(df),

                "column_count": len(df.columns),

                "numeric_columns_with_values": int(
                    numeric.notna().any(axis=0).sum()
                ),

                "columns_without_numeric_values": int(
                    (~numeric.notna().any(axis=0)).sum()
                ),

                "all_numeric_values_finite": bool(
                    np.isfinite(
                        numeric.to_numpy(dtype=float)
                    ).all()
                ),

                "columns": " | ".join(
                    map(str, df.columns)
                )
            })

            for column in numeric.columns:

                values = numeric[column].dropna().to_numpy(
                    dtype=float
                )

                if not len(values):
                    continue

                column_rows.append({

                    "relative_file": relative_file,

                    "column_label": str(column),

                    "sample_count": int(len(values)),

                    "min": float(np.min(values)),

                    "p01": float(
                        np.percentile(values, 1)
                    ),

                    "median": float(np.median(values)),

                    "mean": float(np.mean(values)),

                    "p99": float(
                        np.percentile(values, 99)
                    ),

                    "max": float(np.max(values)),

                    "std": float(np.std(values)),

                    "unique_count": int(
                        pd.Series(values).nunique()
                    )
                })

        except Exception as exc:

            file_rows.append({

                "relative_file": relative_to_root(
                    path,
                    TIAND_ROOT
                ),

                "error": str(exc)
            })

    save_csv(
        file_rows,
        "05_tiand_radar_file_structure.csv"
    )

    save_csv(
        column_rows,
        "05_tiand_radar_column_profile.csv"
    )

    print(
        "Radar columns are profiled numerically. "
        "Physical meanings remain unverified."
    )


# ============================================================
# 9. TASK 6 - TIAND CALIBRATION FILE INVENTORY
# ============================================================

def inspect_tiand_calibration_files():

    print("\n[6/8] TIAND calibration-file inventory")

    rows = []

    for path in find_files(TIAND_CALIBRATION):

        item = {

            "file": str(path),

            "relative_file": relative_to_root(
                path,
                TIAND_ROOT
            ),

            "extension": path.suffix.lower(),

            "size_bytes": path.stat().st_size,

            "read_status": "",

            "preview": ""
        }

        if path.suffix.lower() in TEXT_EXTENSIONS:

            try:

                content = path.read_text(
                    encoding="utf-8",
                    errors="replace"
                )

                item["read_status"] = "text_read"

                item["preview"] = (
                    content[:3000]
                    .replace("\n", " | ")
                    .replace("\r", "")
                )

            except Exception as exc:

                item["read_status"] = "read_error"

                item["preview"] = str(exc)

        else:

            item["read_status"] = (
                "binary_or_unclassified"
            )

        rows.append(item)

    save_csv(
        rows,
        "06_tiand_calibration_file_inventory.csv"
    )

    print(
        "File inventory does not verify calibration correctness "
        "or sensor coordinate frames."
    )


# ============================================================
# 10. TASK 7 - TIAND SYNCHRONIZATION
# ============================================================

def identify_sync_schema(columns):

    lower_map = {
        str(column).strip().lower(): column
        for column in columns
    }

    # Known LiDAR-Camera schema.

    if (
        "lidar_timestamps" in lower_map
        and "camera_timestamps" in lower_map
    ):

        return (
            "lidar_camera",
            lower_map["lidar_timestamps"],
            lower_map["camera_timestamps"]
        )

    # Known Radar-Camera schema.

    if (
        "camera_timestamp" in lower_map
        and "closest_radar_timestamp" in lower_map
    ):

        return (
            "radar_camera",
            lower_map["camera_timestamp"],
            lower_map["closest_radar_timestamp"]
        )

    # Flexible fallback for spelling/case variations.

    lidar_col = next(
        (
            lower_map[c]
            for c in lower_map
            if "lidar" in c and "timestamp" in c
        ),
        None
    )

    camera_cols = [
        lower_map[c]
        for c in lower_map
        if "camera" in c and "timestamp" in c
    ]

    radar_col = next(
        (
            lower_map[c]
            for c in lower_map
            if "radar" in c and "timestamp" in c
        ),
        None
    )

    if lidar_col is not None and camera_cols:

        return (
            "lidar_camera",
            lidar_col,
            camera_cols[0]
        )

    if radar_col is not None and camera_cols:

        return (
            "radar_camera",
            camera_cols[0],
            radar_col
        )

    return None


def inspect_tiand_synchronization():

    print(
        "\n[7/8] TIAND LiDAR-Camera and Radar-Camera synchronization"
    )

    sync_files = find_files(
        TIAND_SYNC,
        "*.csv"
    )

    summary_rows = []

    detail_rows = []

    if not sync_files:

        print(
            "[WARNING] No TIAND synchronization CSV files found."
        )

    for path in sync_files:

        try:

            df = read_csv_safely(path)

            schema = identify_sync_schema(
                df.columns
            )

            if schema is None:

                summary_rows.append({

                    "file": str(path),

                    "status": "unrecognized_schema",

                    "columns": " | ".join(
                        map(str, df.columns)
                    )
                })

                print(
                    f"[UNRECOGNIZED SYNC SCHEMA] {path}"
                )

                continue

            pair_name, column_a, column_b = schema

            seconds_a = parse_time_series(
                df[column_a]
            )

            seconds_b = parse_time_series(
                df[column_b]
            )

            # LiDAR-Camera:
            # camera timestamp minus LiDAR timestamp.
            #
            # Radar-Camera:
            # radar timestamp minus camera timestamp.

            offset_ms = (
                modulo_day_difference_seconds(
                    seconds_a,
                    seconds_b
                )
                * 1000.0
            )

            stats = summarize_offsets(
                offset_ms,
                pair_name
            )

            stats.update({

                "file": str(path),

                "status": "success",

                "timestamp_a_column": str(column_a),

                "timestamp_b_column": str(column_b),

                "offset_definition": (
                    f"{column_b} minus {column_a}"
                ),

                "rows_in_file": len(df)
            })

            summary_rows.append(stats)

            for row_index in range(len(df)):

                offset_value = offset_ms.iloc[row_index]

                detail_rows.append({

                    "pair": pair_name,

                    "source_file": str(path),

                    "row_index": row_index,

                    "timestamp_a_column": str(column_a),

                    "timestamp_a": df.iloc[row_index][column_a],

                    "timestamp_b_column": str(column_b),

                    "timestamp_b": df.iloc[row_index][column_b],

                    "offset_b_minus_a_ms": offset_value,

                    "absolute_offset_ms": (
                        abs(offset_value)
                        if pd.notna(offset_value)
                        else np.nan
                    ),

                    "flag_over_review_threshold": (

                        bool(
                            abs(offset_value)
                            > SYNC_REVIEW_THRESHOLD_MS
                        )

                        if pd.notna(offset_value)
                        else None
                    )
                })

        except Exception as exc:

            summary_rows.append({

                "file": str(path),

                "status": "error",

                "error": str(exc)
            })

    save_csv(
        summary_rows,
        "07_tiand_sync_summary.csv"
    )

    save_csv(
        detail_rows,
        "07_tiand_sync_pair_details.csv"
    )

    print(
        f"Review threshold: +/-{SYNC_REVIEW_THRESHOLD_MS:.1f} ms "
        "(diagnostic only)."
    )

    print(
        "Compare this threshold with documented sensor timing tolerance."
    )


# ============================================================
# 11. TASK 8 - TIAND FILENAME TIMESTAMP SAMPLES
# ============================================================

def timestamp_from_filename(path):

    return parse_time_to_seconds(
        path.stem
    )


def inspect_tiand_filename_timestamps():

    print(
        "\n[8/8] TIAND camera/radar filename timestamp samples"
    )

    rows = []

    camera_files = [
        p for p in find_files(TIAND_CAMERA)
        if p.suffix.lower() in IMAGE_EXTENSIONS
    ]

    radar_files = find_files(
        TIAND_RADAR,
        "*.csv"
    )

    for sensor, files in (
        ("camera", camera_files),
        ("radar", radar_files)
    ):

        for path in files[:200]:

            parsed_time = timestamp_from_filename(
                path
            )

            rows.append({

                "sensor": sensor,

                "relative_file": relative_to_root(
                    path,
                    TIAND_ROOT
                ),

                "filename_stem": path.stem,

                "time_seconds_since_midnight": parsed_time,

                "parse_success": pd.notna(parsed_time)
            })

    save_csv(
        rows,
        "08_tiand_filename_timestamp_samples.csv"
    )


# ============================================================
# 12. MAIN
# ============================================================

def main():

    ensure_output_dir()

    print("=" * 78)

    print(
        "RAAHISENSE - REMAINING PHASE 1 DATASET VALIDATION"
    )

    print("=" * 78)

    print_path_status()

    print(
        f"\nOutput directory: {OUTPUT_ROOT}"
    )

    inspect_idd_lidar_columns()

    inspect_idd_frame_mapping()

    inspect_idd_obd_timestamps()

    inspect_tiand_sensor_inventory()

    inspect_tiand_radar_columns()

    inspect_tiand_calibration_files()

    inspect_tiand_synchronization()

    inspect_tiand_filename_timestamps()

    print("\n" + "=" * 78)

    print("VALIDATION RUN COMPLETED")

    print("=" * 78)

    print(
        f"Review reports in: {OUTPUT_ROOT}"
    )

    print(
        "Do not mark sensor semantics, calibration validity, "
        "or cross-sensor clock alignment as verified until "
        "supported by official dataset documentation."
    )


if __name__ == "__main__":

    main()
