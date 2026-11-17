
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd

ROOT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw"
    r"\idd_multimodal"
)

OUTPUT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\generated"
    r"\phase1\idd_lidar_attributes"
)
OUTPUT.mkdir(parents=True, exist_ok=True)

files = sorted(ROOT.rglob("*.npy"))

col4_counts = Counter()
col5_counts = Counter()
sample_records = []

total_points = 0
integer_col4 = 0
integer_col5 = 0

for i, path in enumerate(files, start=1):
    arr = np.load(path, allow_pickle=False)

    if arr.ndim != 2 or arr.shape[1] != 5:
        continue

    c4 = arr[:, 3]
    c5 = arr[:, 4]

    valid = np.isfinite(c4) & np.isfinite(c5)
    c4 = c4[valid]
    c5 = c5[valid]

    total_points += len(c4)
    integer_col4 += np.count_nonzero(c4 == np.floor(c4))
    integer_col5 += np.count_nonzero(c5 == np.floor(c5))

    col4_counts.update(c4.astype(float).tolist())
    col5_counts.update(c5.astype(float).tolist())

    if i <= 3:
        for idx in np.linspace(
            0, len(arr) - 1, min(10, len(arr)), dtype=int
        ):
            sample_records.append({
                "file": path.name,
                "column_1": arr[idx, 0],
                "column_2": arr[idx, 1],
                "column_3": arr[idx, 2],
                "column_4": arr[idx, 3],
                "column_5": arr[idx, 4]
            })

    if i % 1000 == 0:
        print(f"Processed {i}/{len(files)} files")

def make_summary(counter, name):
    values = np.array(list(counter.keys()), dtype=float)
    frequencies = np.array(list(counter.values()), dtype=np.int64)

    return {
        "column": name,
        "unique_values": len(values),
        "minimum": values.min(),
        "maximum": values.max(),
        "mean_weighted": np.average(values, weights=frequencies),
        "median_approx": np.median(values),
        "integer_value_fraction": (
            integer_col4 / total_points
            if name == "column_4"
            else integer_col5 / total_points
        )
    }

summary = pd.DataFrame([
    make_summary(col4_counts, "column_4"),
    make_summary(col5_counts, "column_5")
])

summary.to_csv(OUTPUT / "01_attribute_summary.csv", index=False)

pd.DataFrame(
    sorted(col4_counts.items()),
    columns=["value", "frequency"]
).to_csv(OUTPUT / "02_column_4_frequency.csv", index=False)

pd.DataFrame(
    sorted(col5_counts.items()),
    columns=["value", "frequency"]
).to_csv(OUTPUT / "03_column_5_frequency.csv", index=False)

pd.DataFrame(sample_records).to_csv(
    OUTPUT / "04_attribute_sample_points.csv",
    index=False
)

print("\nATTRIBUTE SUMMARY")
print(summary.to_string(index=False))

print("\nColumn 4 most frequent values:")
print(col4_counts.most_common(20))

print("\nColumn 5 most frequent values:")
print(col5_counts.most_common(20))

print("\nTotal points analysed:", total_points)
print("Reports saved to:", OUTPUT)
