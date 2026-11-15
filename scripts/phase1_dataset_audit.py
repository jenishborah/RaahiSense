
from pathlib import Path
from collections import Counter
import json
import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# 1. PROJECT PATHS
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw"

IDD_DIR = RAW_DIR / "idd_multimodal"
TIAND_DIR = RAW_DIR / "TIAND_MULTIMODAL_DATASET"

MANIFEST_DIR = PROJECT_ROOT / "data" / "manifests" / "phase1"
REPORT_DIR = PROJECT_ROOT / "data" / "generated" / "phase1"

MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# 2. FILE TYPE DEFINITIONS
# =========================================================

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".webp"
}

POINTCLOUD_EXTENSIONS = {
    ".pcd", ".ply", ".las", ".laz"
}

TABULAR_EXTENSIONS = {
    ".csv", ".tsv", ".xlsx", ".xls"
}

STRUCTURED_EXTENSIONS = {
    ".json", ".jsonl", ".xml", ".yaml", ".yml"
}

MODALITY_KEYWORDS = {
    "camera": [
        "camera", "cam", "image", "rgb",
        "leftcam", "rightcam", "stereo"
    ],
    "lidar": [
        "lidar", "pointcloud", "point_cloud",
        "velodyne", "ouster"
    ],
    "obd": [
        "obd", "vehicle", "engine", "rpm",
        "odometer", "canbus", "can_bus"
    ],
    "gps_gnss": [
        "gps", "gnss", "navigation"
    ],
    "radar": [
        "radar"
    ],
    "imu": [
        "imu", "accelerometer", "gyroscope"
    ],
    "calibration": [
        "calibration", "calib", "intrinsic",
        "extrinsic"
    ]
}


# =========================================================
# 3. FILE CLASSIFICATION
# =========================================================

def get_file_type(path):

    ext = path.suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        return "image"

    if ext in POINTCLOUD_EXTENSIONS:
        return "pointcloud"

    if ext in TABULAR_EXTENSIONS:
        return "tabular"

    if ext in STRUCTURED_EXTENSIONS:
        return "structured"

    if ext in {".bag", ".mcap"}:
        return "sensor_container"

    return "other"


def get_possible_modality(path):

    text = str(path).lower()

    matches = []

    for modality, keywords in MODALITY_KEYWORDS.items():

        if any(keyword in text for keyword in keywords):
            matches.append(modality)

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        return "ambiguous"

    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return "camera_candidate"

    if path.suffix.lower() in POINTCLOUD_EXTENSIONS:
        return "lidar_candidate"

    return "unknown"


def get_split(path):

    text = str(path).lower()

    for split in ["train", "test", "val", "validation"]:
        if split in text:
            return split

    return "unspecified"


# =========================================================
# 4. BUILD INVENTORY
# =========================================================

def build_inventory(dataset_name, dataset_path):

    if not dataset_path.exists():
        print(f"[WARNING] Missing: {dataset_path}")
        return pd.DataFrame()

    if not dataset_path.is_dir():
        print(f"[WARNING] Not a directory: {dataset_path}")
        return pd.DataFrame()

    records = []

    files = sorted(
        p for p in dataset_path.rglob("*")
        if p.is_file()
    )

    for file_path in files:

        try:
            size_bytes = file_path.stat().st_size
        except OSError:
            size_bytes = None

        records.append({
            "dataset": dataset_name,
            "file_name": file_path.name,
            "relative_path": str(
                file_path.relative_to(dataset_path)
            ),
            "extension": file_path.suffix.lower() or "[no extension]",
            "file_type": get_file_type(file_path),
            "possible_modality": get_possible_modality(file_path),
            "split": get_split(file_path),
            "parent_folder": file_path.parent.name,
            "size_bytes": size_bytes,
            "size_mb": (
                round(size_bytes / (1024 ** 2), 4)
                if size_bytes is not None else None
            )
        })

    return pd.DataFrame(records)


# =========================================================
# 5. GENERATE STATISTICS
# =========================================================

def generate_statistics(dataset_name, df):

    if df.empty:
        print(f"[WARNING] No files found for {dataset_name}")
        return

    total_files = len(df)

    valid_sizes = df["size_bytes"].dropna()

    total_bytes = int(valid_sizes.sum())

    stats = {
        "dataset": dataset_name,
        "total_files": total_files,
        "total_size_bytes": total_bytes,
        "total_size_gb": round(
            total_bytes / (1024 ** 3), 4
        ),
        "image_files": int(
            (df["file_type"] == "image").sum()
        ),
        "pointcloud_files": int(
            (df["file_type"] == "pointcloud").sum()
        ),
        "tabular_files": int(
            (df["file_type"] == "tabular").sum()
        ),
        "structured_files": int(
            (df["file_type"] == "structured").sum()
        ),
        "other_files": int(
            (df["file_type"] == "other").sum()
        ),
        "unique_extensions": int(
            df["extension"].nunique()
        ),
        "unique_parent_folders": int(
            df["parent_folder"].nunique()
        )
    }

    output_json = REPORT_DIR / f"{dataset_name}_statistics.json"

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)

    print(f"\n========== {dataset_name} ==========")

    for key, value in stats.items():
        print(f"{key}: {value}")

    return stats


# =========================================================
# 6. GENERATE REPORT CHARTS
# =========================================================

def save_bar_chart(series, title, xlabel, ylabel, output_path):

    if series.empty:
        return

    plt.figure(figsize=(10, 6))

    series.plot(kind="bar")

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)

    plt.xticks(rotation=40, ha="right")
    plt.tight_layout()

    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def generate_charts(dataset_name, df):

    if df.empty:
        return

    chart_dir = REPORT_DIR / dataset_name / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    # Chart 1: File type distribution
    file_type_counts = df["file_type"].value_counts()

    save_bar_chart(
        file_type_counts,
        f"{dataset_name}: File Type Distribution",
        "File Type",
        "Number of Files",
        chart_dir / "file_type_distribution.png"
    )

    # Chart 2: File extension distribution
    extension_counts = df["extension"].value_counts().head(15)

    save_bar_chart(
        extension_counts,
        f"{dataset_name}: File Extension Distribution",
        "Extension",
        "Number of Files",
        chart_dir / "extension_distribution.png"
    )

    # Chart 3: Preliminary modality distribution
    modality_counts = df[
        "possible_modality"
    ].value_counts()

    save_bar_chart(
        modality_counts,
        f"{dataset_name}: Preliminary Modality Distribution",
        "Possible Modality",
        "Number of Files",
        chart_dir / "modality_distribution.png"
    )

    # Chart 4: Train, test and validation file distribution
    split_counts = df["split"].value_counts()

    save_bar_chart(
        split_counts,
        f"{dataset_name}: File Distribution by Split",
        "Split",
        "Number of Files",
        chart_dir / "split_distribution.png"
    )

    # Chart 5: Storage size by extension
    size_by_extension = (
        df.groupby("extension")["size_bytes"]
        .sum()
        .dropna()
        .sort_values(ascending=False)
        .head(15)
        / (1024 ** 3)
    )

    save_bar_chart(
        size_by_extension,
        f"{dataset_name}: Storage Size by Extension",
        "Extension",
        "Size (GB)",
        chart_dir / "storage_by_extension.png"
    )


# =========================================================
# 7. AUDIT ALL DATASET COMPONENTS
# =========================================================

def main():

    dataset_paths = {
        "idd_primary": IDD_DIR / "primary",
        "idd_secondary": IDD_DIR / "secondary",
        "idd_supplement": IDD_DIR / "supplement",
        "tiand": TIAND_DIR
    }

    all_statistics = []

    for dataset_name, dataset_path in dataset_paths.items():

        print(f"\nScanning {dataset_name}...")

        df = build_inventory(
            dataset_name,
            dataset_path
        )

        if df.empty:
            continue

        # Save file-level inventory
        inventory_path = (
            MANIFEST_DIR / f"{dataset_name}_inventory.csv"
        )

        df.to_csv(inventory_path, index=False)

        print(f"Inventory saved: {inventory_path}")

        # Save summary statistics
        stats = generate_statistics(
            dataset_name,
            df
        )

        if stats:
            all_statistics.append(stats)

        # Generate report charts
        generate_charts(
            dataset_name,
            df
        )

    # Combined summary of components, not merged observations
    if all_statistics:

        summary_df = pd.DataFrame(all_statistics)

        summary_df.to_csv(
            REPORT_DIR / "dataset_component_summary.csv",
            index=False
        )

        print("\nPhase 1 inventory and statistics completed.")
        print(f"Manifests: {MANIFEST_DIR}")
        print(f"Reports: {REPORT_DIR}")


if __name__ == "__main__":
    main()
