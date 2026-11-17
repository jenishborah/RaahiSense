
from pathlib import Path
from collections import Counter
import pandas as pd
import numpy as np

ROOT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw"
    r"\TIAND_MULTIMODAL_DATASET\RADAR\RADAR"
)

OUTPUT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\generated"
    r"\phase1\radar_layout"
)
OUTPUT.mkdir(parents=True, exist_ok=True)

results = []
samples = []

for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    files = sorted(folder.glob("*.csv"))

    print(f"\n{folder.name}: {len(files)} files")

    shapes = Counter()
    numeric_status = Counter()

    for path in files:
        try:
            df = pd.read_csv(
                path,
                header=None,
                sep=",",
                engine="python"
            )

            shapes[(len(df), len(df.columns))] += 1

            numeric = df.apply(pd.to_numeric, errors="coerce")
            numeric_status[
                "all_numeric" if numeric.notna().all().all()
                else "contains_non_numeric"
            ] += 1

            if len(samples) < 12:
                samples.append({
                    "direction": folder.name,
                    "filename": path.name,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "sample": df.head(3).to_string(index=False)
                })

        except Exception as exc:
            results.append({
                "direction": folder.name,
                "filename": path.name,
                "status": "read_error",
                "error": str(exc)
            })

    for (rows, columns), count in shapes.items():
        results.append({
            "direction": folder.name,
            "total_files": len(files),
            "rows_per_file": rows,
            "columns_per_file": columns,
            "files_with_this_shape": count,
            "numeric_status": str(dict(numeric_status))
        })

summary = pd.DataFrame(results)
summary.to_csv(OUTPUT / "radar_shape_summary.csv", index=False)

pd.DataFrame(samples).to_csv(
    OUTPUT / "radar_sample_files.csv",
    index=False
)

print("\n========== RADAR FILE STRUCTURE ==========")
print(summary.to_string(index=False))
print("\nReports saved to:", OUTPUT)
