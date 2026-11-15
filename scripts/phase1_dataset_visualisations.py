
from pathlib import Path
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from PIL import Image, ImageOps
from matplotlib.ticker import MaxNLocator


# ============================================================
# 1. PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
IDD = RAW / "idd_multimodal"
TIAND = RAW / "TIAND_MULTIMODAL_DATASET"

OUT = (
    ROOT / "data" / "generated" /
    "phase1" / "visualisations"
)

CHARTS = OUT / "charts"
GRIDS = OUT / "image_grids"
TABLES = OUT / "statistics"

for folder in [CHARTS, GRIDS, TABLES]:
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. GENERAL HELPERS
# ============================================================

def save_figure(path):
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()


def safe_read_csv(path, header="infer", sep=","):
    try:
        return pd.read_csv(
            path,
            header=header,
            sep=sep,
            low_memory=False,
            on_bad_lines="warn"
        )
    except Exception as error:
        print(f"[CSV ERROR] {path}: {error}")
        return None


def find_images(folder):
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    if not folder.exists():
        return []

    return sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in extensions
    )


# ============================================================
# 3. IMAGE STATISTICS
# ============================================================

def image_statistics(dataset_name, folder):

    files = find_images(folder)

    if not files:
        print(f"[WARNING] No images found: {folder}")
        return

    records = []

    for path in files:

        try:
            with Image.open(path) as img:
                width, height = img.size

                records.append({
                    "dataset": dataset_name,
                    "file_name": path.name,
                    "relative_path": str(path.relative_to(folder)),
                    "width": width,
                    "height": height,
                    "channels": len(img.getbands()),
                    "format": img.format,
                    "size_bytes": path.stat().st_size
                })

        except Exception as error:
            print(f"[IMAGE ERROR] {path}: {error}")

    df = pd.DataFrame(records)

    if df.empty:
        return

    df.to_csv(
        TABLES / f"{dataset_name}_image_statistics.csv",
        index=False
    )

    resolution = (
        df.groupby(["width", "height"])
        .size()
        .reset_index(name="image_count")
        .sort_values("image_count", ascending=False)
    )

    resolution.to_csv(
        TABLES / f"{dataset_name}_resolution_distribution.csv",
        index=False
    )

    print(f"\n{dataset_name} IMAGE STATISTICS")
    print("Valid images:", len(df))
    print("Average width:", round(df["width"].mean(), 2))
    print("Average height:", round(df["height"].mean(), 2))
    print("Unique resolutions:", len(resolution))
    print("\nMost common resolutions:")
    print(resolution.head(10).to_string(index=False))

    # Resolution chart
    top = resolution.head(10).copy()

    top["resolution"] = (
        top["width"].astype(str)
        + " x "
        + top["height"].astype(str)
    )

    plt.figure(figsize=(10, 6))
    plt.bar(top["resolution"], top["image_count"])
    plt.title(f"{dataset_name}: Image Resolution Distribution")
    plt.xlabel("Resolution")
    plt.ylabel("Number of Images")
    plt.xticks(rotation=35, ha="right")
    save_figure(CHARTS / f"{dataset_name}_resolution.png")

    # Image dimension distributions
    plt.figure(figsize=(10, 5))
    plt.hist(df["width"], bins=20)
    plt.title(f"{dataset_name}: Image Width Distribution")
    plt.xlabel("Width (pixels)")
    plt.ylabel("Number of Images")
    save_figure(CHARTS / f"{dataset_name}_width_distribution.png")

    plt.figure(figsize=(10, 5))
    plt.hist(df["height"], bins=20)
    plt.title(f"{dataset_name}: Image Height Distribution")
    plt.xlabel("Height (pixels)")
    plt.ylabel("Number of Images")
    save_figure(CHARTS / f"{dataset_name}_height_distribution.png")

    return df


# ============================================================
# 4. CAMERA SAMPLE GRIDS
# ============================================================

def create_image_grid(dataset_name, folder, grid_size=12):

    files = find_images(folder)

    if not files:
        return

    # Select images at evenly spaced positions.
    indexes = np.linspace(
        0,
        len(files) - 1,
        min(grid_size, len(files)),
        dtype=int
    )

    selected = [files[i] for i in indexes]

    columns = 3
    rows = int(np.ceil(len(selected) / columns))

    fig, axes = plt.subplots(
        rows,
        columns,
        figsize=(15, rows * 4)
    )

    axes = np.array(axes).reshape(-1)

    for ax in axes:
        ax.axis("off")

    for ax, path in zip(axes, selected):

        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                ax.imshow(img)

            ax.set_title(path.name, fontsize=8)
            ax.axis("off")

        except Exception as error:
            ax.set_title(f"Could not read: {path.name}")
            print(f"[GRID ERROR] {path}: {error}")

    fig.suptitle(
        f"{dataset_name}: Representative Camera Images",
        fontsize=15
    )

    save_figure(GRIDS / f"{dataset_name}_sample_grid.png")


# ============================================================
# 5. IDD CAMERA ANALYSIS
# ============================================================

def analyze_idd_cameras():

    camera_folders = {
        "idd_left_d0": IDD / "primary" / "d0" / "leftCamImgs",
        "idd_left_d1": IDD / "primary" / "d1" / "leftCamImgs",
        "idd_left_d2": IDD / "primary" / "d2" / "leftCamImgs",
        "idd_right_d0": IDD / "secondary" / "d0" / "rightCamImgs",
        "idd_right_d1": IDD / "secondary" / "d1" / "rightCamImgs",
        "idd_right_d2": IDD / "secondary" / "d2" / "rightCamImgs"
    }

    all_stats = []

    for name, folder in camera_folders.items():

        print(f"\nProcessing {name}")

        stats = image_statistics(name, folder)

        if stats is not None:
            all_stats.append({
                "camera_collection": name,
                "image_count": len(stats),
                "mean_width": stats["width"].mean(),
                "mean_height": stats["height"].mean()
            })

        create_image_grid(name, folder)

    if all_stats:
        pd.DataFrame(all_stats).to_csv(
            TABLES / "idd_camera_collection_summary.csv",
            index=False
        )


# ============================================================
# 6. TIAND CAMERA ANALYSIS
# ============================================================

def analyze_tiand_camera():

    folder = TIAND / "CAMERA" / "CAMERA"

    print("\nProcessing TIAND camera")

    image_statistics("tiand_camera", folder)
    create_image_grid("tiand_camera", folder)


# ============================================================
# 7. IDD LIDAR STATISTICS
# ============================================================

def analyze_idd_lidar():

    lidar_root = IDD / "supplement" / "lidar"

    records = []
    column_samples = []

    files = sorted(lidar_root.rglob("*.npy"))

    print("\nIDD LIDAR FILES:", len(files))

    for i, path in enumerate(files):

        try:
            array = np.load(
                path,
                mmap_mode="r",
                allow_pickle=False
            )

            if array.ndim != 2:
                continue

            point_count, column_count = array.shape

            records.append({
                "session": path.parent.name,
                "file_name": path.name,
                "point_count": point_count,
                "column_count": column_count,
                "dtype": str(array.dtype),
                "size_bytes": path.stat().st_size
            })

            # Sample at most 2,000 rows per file for column statistics.
            sample = np.asarray(array[:2000, :], dtype=np.float64)

            if sample.size:
                for col in range(column_count):

                    values = sample[:, col]
                    values = values[np.isfinite(values)]

                    if len(values):
                        column_samples.append({
                            "session": path.parent.name,
                            "column_index": col,
                            "sample_count": len(values),
                            "sample_min": float(values.min()),
                            "sample_max": float(values.max()),
                            "sample_mean": float(values.mean()),
                            "sample_std": float(values.std())
                        })

        except Exception as error:
            print(f"[LIDAR ERROR] {path}: {error}")

        if (i + 1) % 1000 == 0:
            print(f"Processed {i + 1}/{len(files)} LiDAR files")

    df = pd.DataFrame(records)
    column_df = pd.DataFrame(column_samples)

    if df.empty:
        print("[WARNING] No valid LiDAR arrays found.")
        return

    df.to_csv(
        TABLES / "idd_lidar_point_counts.csv",
        index=False
    )

    column_df.to_csv(
        TABLES / "idd_lidar_column_statistics.csv",
        index=False
    )

    print("\nIDD LIDAR SUMMARY")
    print("Valid arrays:", len(df))
    print("Total points:", int(df["point_count"].sum()))
    print("Mean points per file:", round(df["point_count"].mean(), 2))
    print("Minimum points:", int(df["point_count"].min()))
    print("Maximum points:", int(df["point_count"].max()))

    # Point count distribution
    plt.figure(figsize=(10, 6))
    plt.hist(df["point_count"], bins=40)
    plt.title("IDD LiDAR: Points per Frame Distribution")
    plt.xlabel("Number of Points")
    plt.ylabel("Number of Frames")
    save_figure(CHARTS / "idd_lidar_point_count_distribution.png")

    # Point count by session
    session_counts = (
        df.groupby("session")["point_count"]
        .mean()
        .sort_index()
    )

    plt.figure(figsize=(8, 5))
    session_counts.plot(kind="bar")
    plt.title("IDD LiDAR: Average Points per Frame by Session")
    plt.xlabel("Session")
    plt.ylabel("Average Points")
    save_figure(CHARTS / "idd_lidar_session_comparison.png")

    # Exploratory plot of first three columns.
    # These are labelled by index, not assumed physical meaning.
    sample_path = files[len(files) // 2]
    sample_array = np.load(
        sample_path,
        mmap_mode="r",
        allow_pickle=False
    )

    sample = np.asarray(sample_array[:10000, :])

    if sample.shape[1] >= 3:

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")

        ax.scatter(
            sample[:, 0],
            sample[:, 1],
            sample[:, 2],
            s=0.5
        )

        ax.set_title(
            "IDD LiDAR: Exploratory Plot of Columns 0, 1 and 2"
        )

        ax.set_xlabel("Column 0")
        ax.set_ylabel("Column 1")
        ax.set_zlabel("Column 2")

        save_figure(CHARTS / "idd_lidar_exploratory_3d.png")


# ============================================================
# 8. IDD OBD VISUALISATION
# ============================================================

def analyze_idd_obd():

    obd_root = IDD / "supplement" / "obd"

    for session in ["d0", "d1", "d2"]:

        path = obd_root / session / "obd.csv"

        if not path.exists():
            print("[MISSING OBD]", path)
            continue

        df = safe_read_csv(path)

        if df is None or df.empty:
            continue

        df.to_csv(
            TABLES / f"idd_obd_{session}_inspected.csv",
            index=False
        )

        print(f"\nOBD {session}:")
        print(df.describe(include="all").to_string())

        # Convert timestamp when possible.
        if "timestamp" in df.columns:
            numeric_time = pd.to_numeric(
                df["timestamp"],
                errors="coerce"
            )

            if numeric_time.notna().all():
                x = numeric_time
                xlabel = "Timestamp"
            else:
                parsed_time = pd.to_datetime(
                    df["timestamp"],
                    errors="coerce"
                )

                if parsed_time.notna().any():
                    x = parsed_time
                    xlabel = "Timestamp"
                else:
                    x = np.arange(len(df))
                    xlabel = "Record Index"
        else:
            x = np.arange(len(df))
            xlabel = "Record Index"

        for column in ["speed", "rpm", "throttle_position", "clv"]:

            if column not in df.columns:
                continue

            values = pd.to_numeric(
                df[column],
                errors="coerce"
            )

            valid = values.notna()

            if not valid.any():
                continue

            plt.figure(figsize=(12, 5))
            plt.plot(
                np.asarray(x)[valid.to_numpy()],
                values[valid],
                linewidth=0.8
            )

            plt.title(f"IDD OBD {session}: {column}")
            plt.xlabel(xlabel)
            plt.ylabel(column)

            save_figure(
                CHARTS / f"idd_obd_{session}_{column}.png"
            )


# ============================================================
# 9. TIAND GNSS VISUALISATION
# ============================================================

def analyze_tiand_gnss():

    path = (
        TIAND / "GNSS" / "GNSS" /
        "scene3-novatel-oem7-inspva.csv"
    )

    if not path.exists():
        print("[WARNING] GNSS file not found.")
        return

    df = safe_read_csv(path)

    if df is None or df.empty:
        return

    df.to_csv(
        TABLES / "tiand_gnss_inspected.csv",
        index=False
    )

    for column in df.columns:
        if column != "time":
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # Geographic trajectory
    if {"latitude", "longitude"}.issubset(df.columns):

        valid = df.dropna(
            subset=["latitude", "longitude"]
        )

        plt.figure(figsize=(9, 7))
        plt.plot(
            valid["longitude"],
            valid["latitude"],
            linewidth=0.7
        )

        plt.title("TIAND GNSS: Geographic Trajectory")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")

        save_figure(CHARTS / "tiand_gnss_trajectory.png")

    # Velocity components
    velocity_columns = [
        "north_velocity",
        "east_velocity",
        "up_velocity"
    ]

    available = [
        col for col in velocity_columns
        if col in df.columns
    ]

    if available:

        plt.figure(figsize=(12, 6))

        for col in available:
            plt.plot(df.index, df[col], label=col, linewidth=0.8)

        plt.title("TIAND GNSS: Velocity Components")
        plt.xlabel("Record Index")
        plt.ylabel("Velocity (dataset units)")
        plt.legend()

        save_figure(CHARTS / "tiand_gnss_velocity.png")

    # Orientation
    orientation_columns = [
        "roll", "pitch", "azimuth"
    ]

    available = [
        col for col in orientation_columns
        if col in df.columns
    ]

    if available:

        plt.figure(figsize=(12, 6))

        for col in available:
            plt.plot(df.index, df[col], label=col, linewidth=0.8)

        plt.title("TIAND GNSS: Orientation Measurements")
        plt.xlabel("Record Index")
        plt.ylabel("Angle (dataset units)")
        plt.legend()

        save_figure(CHARTS / "tiand_gnss_orientation.png")


# ============================================================
# 10. TIAND RADAR EXPLORATION
# ============================================================

def analyze_tiand_radar():

    radar_folder = (
        TIAND / "RADAR" / "RADAR" / "RADAR_Front"
    )

    files = sorted(radar_folder.glob("*.csv"))

    if not files:
        print("[WARNING] No front radar CSV files found.")
        return

    # Inspect a maximum of 100 files for the first visualisation.
    selected = files[:100]

    rows = []

    for path in selected:

        try:
            df = pd.read_csv(
                path,
                header=None,
                sep=",",
                low_memory=False
            )

            numeric = df.apply(
                pd.to_numeric,
                errors="coerce"
            )

            if not numeric.empty:
                rows.extend(
                    numeric.to_numpy(dtype=float).tolist()
                )

        except Exception as error:
            print(f"[RADAR ERROR] {path}: {error}")

    if not rows:
        return

    # Retain only rows with a consistent width.
    widths = pd.Series([len(row) for row in rows])
    common_width = int(widths.mode().iloc[0])

    matrix_rows = [
        row for row in rows
        if len(row) == common_width
    ]

    matrix = np.asarray(matrix_rows, dtype=float)

    np.save(
        TABLES / "tiand_front_radar_sample_matrix.npy",
        matrix
    )

    print("\nTIAND FRONT RADAR")
    print("Files sampled:", len(selected))
    print("Radar matrix shape:", matrix.shape)
    print("Numeric values:", matrix.size)
    print("Finite values:", int(np.isfinite(matrix).sum()))

    plt.figure(figsize=(14, 7))

    plt.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest"
    )

    plt.title(
        "TIAND Front Radar: Exploratory Numeric Matrix"
    )

    plt.xlabel("Column Index")
    plt.ylabel("Sample Row Index")
    plt.colorbar(label="Recorded Value")

    save_figure(
        CHARTS / "tiand_front_radar_heatmap.png"
    )


# ============================================================
# 11. TIAND SENSOR SYNCHRONISATION
# ============================================================

def analyse_sync_file(path, first_col, second_col, output_name):

    if not path.exists():
        print("[MISSING SYNC FILE]", path)
        return

    df = pd.read_csv(
    path,
    sep=None,
    engine="python"
)

    if df is None or df.empty:
        return

    if not {first_col, second_col}.issubset(df.columns):
        print("[SYNC COLUMNS NOT FOUND]", path)
        print("Available:", df.columns.tolist())
        return

    first = pd.to_timedelta(
        df[first_col].astype(str),
        errors="coerce"
    )

    second = pd.to_timedelta(
        df[second_col].astype(str),
        errors="coerce"
    )

    offset_ms = (
        second - first
    ).dt.total_seconds() * 1000

    valid = offset_ms.dropna()

    if valid.empty:
        print("[SYNC] No valid timestamp pairs:", path)
        return

    result = pd.DataFrame({
        first_col: df[first_col],
        second_col: df[second_col],
        "offset_ms": offset_ms
    })

    result.to_csv(
        TABLES / f"{output_name}_offsets.csv",
        index=False
    )

    print(f"\n{output_name} SYNC SUMMARY")
    print("Valid pairs:", len(valid))
    print("Mean offset ms:", round(valid.mean(), 4))
    print("Median offset ms:", round(valid.median(), 4))
    print("Minimum offset ms:", round(valid.min(), 4))
    print("Maximum offset ms:", round(valid.max(), 4))
    print("Std deviation ms:", round(valid.std(), 4))

    plt.figure(figsize=(10, 5))
    plt.hist(valid, bins=40)

    plt.title(f"{output_name}: Timestamp Offset Distribution")
    plt.xlabel("Timestamp Offset (milliseconds)")
    plt.ylabel("Number of Pairs")

    save_figure(
        CHARTS / f"{output_name}_offset_distribution.png"
    )


def analyze_tiand_synchronisation():

    sync_root = (
        TIAND / "Synchronisation_timestamps" /
        "Synchronisation_timestamps"
    )

    analyse_sync_file(
        sync_root / "Lidar_Camera_synchronisation.csv",
        "lidar_timestamps",
        "camera_timestamps",
        "tiand_lidar_camera"
    )

    analyse_sync_file(
        sync_root / "Radar_Camera_Synchronization.csv",
        "camera_timestamp",
        "closest_radar_timestamp",
        "tiand_radar_camera"
    )


# ============================================================
# 12. MAIN
# ============================================================

def main():

    print("\n========== IDD CAMERA ANALYSIS ==========")
    analyze_idd_cameras()

    print("\n========== TIAND CAMERA ANALYSIS ==========")
    analyze_tiand_camera()

    print("\n========== IDD LIDAR ANALYSIS ==========")
    analyze_idd_lidar()

    print("\n========== IDD OBD ANALYSIS ==========")
    analyze_idd_obd()

    print("\n========== TIAND GNSS ANALYSIS ==========")
    analyze_tiand_gnss()

    print("\n========== TIAND RADAR ANALYSIS ==========")
    analyze_tiand_radar()

    print("\n========== TIAND SYNCHRONISATION ==========")
    analyze_tiand_synchronisation()

    print("\nAll visualisation tasks completed.")
    print("Output directory:", OUT)


if __name__ == "__main__":
    main()
