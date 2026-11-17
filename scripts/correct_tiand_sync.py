
from pathlib import Path
import re
import numpy as np
import pandas as pd

# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ROOT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw\TIAND_MULTIMODAL_DATASET"
)

SYNC_DIR = (
    ROOT / "Synchronisation_timestamps"
    / "Synchronisation_timestamps"
)

RADAR_CAMERA_FILE = (
    SYNC_DIR / "Radar_Camera_Synchronization.csv"
)

LIDAR_CAMERA_FILE = (
    SYNC_DIR / "Lidar_Camera_synchronisation.csv"
)

OUTPUT_DIR = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\generated"
    r"\phase1\remaining_validation"
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# TIMESTAMP PARSER
# ---------------------------------------------------------

def parse_time(value):
    """Convert HH:MM:SS.ffffff into seconds since midnight."""

    if pd.isna(value):
        return np.nan

    value = str(value).strip()

    match = re.fullmatch(
        r"(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?",
        value
    )

    if not match:
        return np.nan

    hour, minute, second, fraction = match.groups()

    fraction = float("0." + fraction) if fraction else 0.0

    return (
        int(hour) * 3600
        + int(minute) * 60
        + int(second)
        + fraction
    )


def calculate_offset(first, second):
    """
    Calculate first - second.
    Correct for a possible midnight rollover.
    """

    offset = first - second

    if offset > 43200:
        offset -= 86400
    elif offset < -43200:
        offset += 86400

    return offset * 1000


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def validate_sync(file_path, sensor_a, sensor_b,
                  column_a, column_b, separator,
                  offset_name):

    print(f"\nReading: {file_path.name}")

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    df = pd.read_csv(
        file_path,
        sep=separator,
        engine="python"
    )

    df.columns = [str(c).strip() for c in df.columns]

    print("Columns:", list(df.columns))
    print("Total rows:", len(df))

    if column_a not in df.columns or column_b not in df.columns:
        raise ValueError(
            f"Expected columns {column_a!r} and {column_b!r}; "
            f"found {list(df.columns)}"
        )

    df["time_a_seconds"] = df[column_a].apply(parse_time)
    df["time_b_seconds"] = df[column_b].apply(parse_time)

    df[offset_name] = [
        calculate_offset(a, b)
        if np.isfinite(a) and np.isfinite(b)
        else np.nan
        for a, b in zip(
            df["time_a_seconds"],
            df["time_b_seconds"]
        )
    ]

    valid = df[offset_name].dropna().to_numpy()

    summary = {
        "sensor_pair": f"{sensor_a}-{sensor_b}",
        "total_rows": len(df),
        "valid_pairs": len(valid),
        "invalid_pairs": len(df) - len(valid),
        "mean_offset_ms": np.mean(valid) if len(valid) else np.nan,
        "median_offset_ms": np.median(valid) if len(valid) else np.nan,
        "std_offset_ms": (
            np.std(valid, ddof=1) if len(valid) > 1 else np.nan
        ),
        "minimum_offset_ms": np.min(valid) if len(valid) else np.nan,
        "maximum_offset_ms": np.max(valid) if len(valid) else np.nan,
        "p95_absolute_offset_ms": (
            np.percentile(np.abs(valid), 95)
            if len(valid) else np.nan
        ),
        "pairs_exceeding_50ms": (
            int(np.sum(np.abs(valid) > 50))
            if len(valid) else 0
        ),
        "offset_definition": f"{sensor_a} - {sensor_b}"
    }

    return df, summary


# ---------------------------------------------------------
# RADAR-CAMERA
# File is whitespace-separated, NOT comma-separated.
# Offset = Radar - Camera
# ---------------------------------------------------------

radar_details, radar_summary = validate_sync(
    file_path=RADAR_CAMERA_FILE,
    sensor_a="Radar",
    sensor_b="Camera",
    column_a="closest_radar_timestamp",
    column_b="camera_timestamp",
    separator=r"\s+",
    offset_name="radar_minus_camera_ms"
)


# ---------------------------------------------------------
# LIDAR-CAMERA
# File is comma-separated.
# Offset = Camera - LiDAR
# ---------------------------------------------------------

lidar_details, lidar_summary = validate_sync(
    file_path=LIDAR_CAMERA_FILE,
    sensor_a="Camera",
    sensor_b="LiDAR",
    column_a="camera_timestamps",
    column_b="lidar_timestamps",
    separator=",",
    offset_name="camera_minus_lidar_ms"
)


# ---------------------------------------------------------
# SAVE REPORTS
# ---------------------------------------------------------

summary_df = pd.DataFrame([
    radar_summary,
    lidar_summary
])

summary_path = OUTPUT_DIR / "09_corrected_tiand_sync_summary.csv"
details_path = OUTPUT_DIR / "09_corrected_tiand_sync_pair_details.csv"

summary_df.to_csv(summary_path, index=False)

all_details = pd.concat(
    [
        radar_details.assign(sensor_pair="Radar-Camera"),
        lidar_details.assign(sensor_pair="LiDAR-Camera")
    ],
    ignore_index=True,
    sort=False
)

all_details.to_csv(details_path, index=False)

print("\n========== CORRECTED SYNCHRONIZATION SUMMARY ==========")
print(summary_df.to_string(index=False))

print("\nSaved:")
print(summary_path)
print(details_path)

print("\nValidation completed.")
