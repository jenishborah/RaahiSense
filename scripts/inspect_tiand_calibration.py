
from pathlib import Path
import json
import numpy as np
import pandas as pd

# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw"
    r"\TIAND_MULTIMODAL_DATASET"
)

CALIBRATION = (
    ROOT / "Calibration_files" / "Calibration_files"
)

LIDAR_DIR = CALIBRATION / "LIDAR"
RADAR_DIR = CALIBRATION / "RADAR"

OUTPUT_DIR = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\generated"
    r"\phase1\calibration_inspection"
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

report_lines = []
summary_rows = []


def log(message=""):
    print(message)
    report_lines.append(str(message))


# --------------------------------------------------
# NUMPY MATRIX INSPECTION
# --------------------------------------------------

def inspect_npy(path, label):
    log("\n" + "=" * 65)
    log(label)
    log("=" * 65)

    if not path.exists():
        log(f"FILE NOT FOUND: {path}")
        return

    try:
        matrix = np.load(path, allow_pickle=False)
        log(f"File: {path.name}")
        log(f"Shape: {matrix.shape}")
        log(f"Dimensions: {matrix.ndim}")
        log(f"Data type: {matrix.dtype}")
        log(f"All finite: {bool(np.isfinite(matrix).all())}")

        log("\nMatrix values:")
        log(np.array2string(
            matrix,
            precision=8,
            suppress_small=True,
            threshold=200
        ))

        row = {
            "file": path.name,
            "label": label,
            "shape": str(matrix.shape),
            "dtype": str(matrix.dtype),
            "all_finite": bool(np.isfinite(matrix).all()),
            "minimum": (
                float(np.min(matrix))
                if matrix.size else np.nan
            ),
            "maximum": (
                float(np.max(matrix))
                if matrix.size else np.nan
            )
        }

        # Additional numerical checks for a 3x3 matrix.
        # These checks do not establish coordinate conventions.
        if matrix.shape == (3, 3) and np.isfinite(matrix).all():
            determinant = np.linalg.det(matrix)
            orthogonality_error = np.linalg.norm(
                matrix.T @ matrix - np.eye(3)
            )

            row["determinant"] = float(determinant)
            row["orthogonality_error"] = float(
                orthogonality_error
            )

            log(f"Determinant: {determinant:.8f}")
            log(
                "Orthogonality error (R.T @ R - I): "
                f"{orthogonality_error:.8e}"
            )

        summary_rows.append(row)

    except Exception as exc:
        log(f"ERROR: {exc}")


# --------------------------------------------------
# JSON INSPECTION
# --------------------------------------------------

def inspect_json(path):
    log("\n" + "=" * 65)
    log("RADAR MOUNTING POSITIONS JSON")
    log("=" * 65)

    if not path.exists():
        log(f"FILE NOT FOUND: {path}")
        return

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        formatted = json.dumps(data, indent=4)

        log(f"File: {path.name}")
        log("\nJSON contents:")
        log(formatted)

        # Save a readable copy.
        (OUTPUT_DIR / "radar_mounting_positions_readable.json").write_text(
            formatted,
            encoding="utf-8"
        )

    except Exception as exc:
        log(f"ERROR: {exc}")


# --------------------------------------------------
# FILE INVENTORY
# --------------------------------------------------

log("TIAND CALIBRATION INSPECTION")
log(f"Calibration directory: {CALIBRATION}")

for folder in [LIDAR_DIR, RADAR_DIR]:
    log(f"\nDirectory: {folder}")
    log(f"Exists: {folder.exists()}")

    if folder.exists():
        for file in sorted(folder.iterdir()):
            if file.is_file():
                log(f"  {file.name} ({file.stat().st_size} bytes)")


# --------------------------------------------------
# LIDAR CALIBRATION
# --------------------------------------------------

inspect_npy(
    LIDAR_DIR / "LiDAR_rotation_matrix.npy",
    "LiDAR rotation matrix"
)

inspect_npy(
    LIDAR_DIR / "LiDAR_translation_matrix.npy",
    "LiDAR translation matrix"
)


# --------------------------------------------------
# RADAR CALIBRATION
# --------------------------------------------------

inspect_npy(
    RADAR_DIR / "Radar_camera_Projection_matrix.npy",
    "Radar-camera projection matrix"
)

inspect_json(
    RADAR_DIR / "Radar_mounting_positions.json"
)


# --------------------------------------------------
# SAVE REPORTS
# --------------------------------------------------

summary_path = OUTPUT_DIR / "calibration_matrix_summary.csv"
report_path = OUTPUT_DIR / "calibration_inspection_report.txt"

pd.DataFrame(summary_rows).to_csv(
    summary_path,
    index=False
)

report_path.write_text(
    "\n".join(report_lines),
    encoding="utf-8"
)

log("\n" + "=" * 65)
log("INSPECTION COMPLETED")
log(f"Summary CSV: {summary_path}")
log(f"Detailed report: {report_path}")
log("=" * 65)
