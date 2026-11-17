
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd

# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw"
    r"\idd_multimodal"
)

OUTPUT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\generated"
    r"\phase1\idd_lidar_column_inspection"
)
OUTPUT.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# FIND LIDAR NPY FILES
# --------------------------------------------------

files = sorted(ROOT.rglob("*.npy"))

print("Total NPY files found:", len(files))

shape_counts = Counter()
dtype_counts = Counter()
column_values = {i: [] for i in range(5)}
sample_rows = []
file_checks = []

# --------------------------------------------------
# INSPECT ALL FILES
# --------------------------------------------------

for index, path in enumerate(files, start=1):
    try:
        arr = np.load(path, allow_pickle=False)

        shape_counts[str(arr.shape)] += 1
        dtype_counts[str(arr.dtype)] += 1

        valid_shape = (
            arr.ndim == 2
            and arr.shape[1] == 5
        )

        finite = bool(np.isfinite(arr).all())

        file_checks.append({
            "file": path.name,
            "relative_path": str(path.relative_to(ROOT)),
            "shape": str(arr.shape),
            "dtype": str(arr.dtype),
            "valid_5_column_shape": valid_shape,
            "all_finite": finite,
            "point_count": arr.shape[0] if arr.ndim == 2 else None
        })

        if valid_shape:
            for col in range(5):
                values = arr[:, col]
                finite_values = values[np.isfinite(values)]

                if finite_values.size:
                    # Sample values for distribution inspection.
                    column_values[col].extend(
                        finite_values[::max(1, len(finite_values) // 100)]
                        .tolist()
                    )

            if len(sample_rows) < 20 and arr.shape[0] > 0:
                for row_index in np.linspace(
                    0, arr.shape[0] - 1,
                    min(4, arr.shape[0]),
                    dtype=int
                ):
                    sample_rows.append({
                        "file": path.name,
                        "point_index": int(row_index),
                        **{
                            f"column_{c+1}": float(arr[row_index, c])
                            for c in range(5)
                        }
                    })

    except Exception as exc:
        file_checks.append({
            "file": path.name,
            "relative_path": str(path.relative_to(ROOT)),
            "error": str(exc)
        })

    if index % 1000 == 0:
        print(f"Inspected {index}/{len(files)} files")


# --------------------------------------------------
# COLUMN STATISTICS
# --------------------------------------------------

stats = []

for col, values in column_values.items():
    values = np.asarray(values, dtype=np.float64)

    if values.size == 0:
        continue

    stats.append({
        "column": f"column_{col+1}",
        "sample_count": len(values),
        "minimum": np.min(values),
        "maximum": np.max(values),
        "mean": np.mean(values),
        "median": np.median(values),
        "std": np.std(values),
        "p01": np.percentile(values, 1),
        "p25": np.percentile(values, 25),
        "p75": np.percentile(values, 75),
        "p99": np.percentile(values, 99),
        "unique_sampled_values": len(np.unique(values))
    })


# --------------------------------------------------
# SAVE REPORTS
# --------------------------------------------------

pd.DataFrame(stats).to_csv(
    OUTPUT / "01_lidar_column_statistics.csv",
    index=False
)

pd.DataFrame(file_checks).to_csv(
    OUTPUT / "02_lidar_file_validation.csv",
    index=False
)

pd.DataFrame(sample_rows).to_csv(
    OUTPUT / "03_lidar_sample_points.csv",
    index=False
)

summary = [
    f"Total files: {len(files)}",
    f"Shape distribution: {dict(shape_counts)}",
    f"Data type distribution: {dict(dtype_counts)}",
    f"Successfully inspected: {len(file_checks)}"
]

(OUTPUT / "04_lidar_inspection_summary.txt").write_text(
    "\n".join(summary),
    encoding="utf-8"
)

print("\n========== IDD LIDAR INSPECTION ==========")
for line in summary:
    print(line)

print("\nColumn statistics:")
print(pd.DataFrame(stats).to_string(index=False))

print("\nReports saved to:", OUTPUT)
