
from pathlib import Path
import json
import numpy as np
import pandas as pd


# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

IDD = RAW / "idd_multimodal"
TIAND = RAW / "TIAND_MULTIMODAL_DATASET"

OUTPUT = (
    ROOT / "data" / "generated" /
    "phase1" / "content_validation"
)

OUTPUT.mkdir(parents=True, exist_ok=True)


# =========================================================
# 1. INSPECT NUMPY FILES
# =========================================================

def inspect_npy(path):

    result = {
        "file": str(path),
        "status": "unknown"
    }

    try:
        array = np.load(
            path,
            mmap_mode="r",
            allow_pickle=False
        )

        result.update({
            "status": "success",
            "shape": list(array.shape),
            "dimensions": int(array.ndim),
            "dtype": str(array.dtype),
            "size_bytes": int(path.stat().st_size),
            "size_mb": round(
                path.stat().st_size / (1024 ** 2), 4
            )
        })

        if array.size > 0 and array.dtype.kind in "iuf":
            sample = array.reshape(-1)[:10000]
            sample = np.asarray(sample)

            result["sample_min"] = float(np.nanmin(sample))
            result["sample_max"] = float(np.nanmax(sample))
            result["sample_mean"] = float(np.nanmean(sample))

    except Exception as error:
        result["status"] = "error"
        result["error"] = str(error)

    return result


def inspect_idd_npy():

    lidar_root = IDD / "supplement" / "lidar"

    files = sorted(lidar_root.rglob("*.npy"))

    print("\nIDD NUMPY INSPECTION")
    print("Total NPY files:", len(files))

    # Inspect representative files from each session.
    selected = []

    for session in ["d0", "d1", "d2"]:

        session_files = [
            f for f in files
            if session in f.parts
        ]

        if session_files:
            selected.extend([
                session_files[0],
                session_files[len(session_files) // 2],
                session_files[-1]
            ])

    records = [
        inspect_npy(path)
        for path in selected
    ]

    output = OUTPUT / "idd_lidar_npy_inspection.json"

    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)

    for record in records:
        print(
            record["file"],
            "|",
            record["status"],
            "| shape:",
            record.get("shape"),
            "| dtype:",
            record.get("dtype")
        )


# =========================================================
# 2. INSPECT CSV FILES
# =========================================================

def inspect_csv(path, header="infer", separator=None):

    try:

        if separator is None:
           df = pd.read_csv(
        path,
        header=header,
        sep=None,
        engine="python",
        nrows=5,
        encoding="utf-8",
        on_bad_lines="warn"
    ) 
        else:
           df = pd.read_csv(
        path,
        header=header,
        sep=separator,
        nrows=5,
        encoding="utf-8",
        on_bad_lines="warn"
    )

        return {
            "file": str(path),
            "status": "success",
            "rows_sampled": len(df),
            "column_count": len(df.columns),
            "columns": [str(c) for c in df.columns],
            "sample": (
                df.astype(object)
                .where(pd.notna(df), None)
                .to_dict(orient="records")
            )
        }

    except Exception as error:

        return {
            "file": str(path),
            "status": "error",
            "error": str(error)
        }


# =========================================================
# 3. IDD CSV INSPECTION
# =========================================================

def inspect_idd_csv():

    targets = [
        IDD / "primary" / "d0" / "train.csv",
        IDD / "primary" / "d0" / "test.csv",
        IDD / "supplement" / "obd" / "d0" / "obd.csv",
        IDD / "supplement" / "lidar" / "d0" / "timestamp.csv"
    ]

    records = []

    for path in targets:

        if path.exists():
            record = inspect_csv(path)
            records.append(record)

            print("\nIDD:", path.name)
            print("Status:", record["status"])
            print("Columns:", record.get("columns"))

    output = OUTPUT / "idd_csv_validation.json"

    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, default=str)


# =========================================================
# 4. TIAND CSV INSPECTION
# =========================================================

def inspect_tiand_csv():

    targets = [
        (
            TIAND / "GNSS" / "GNSS" /
            "scene3-novatel-oem7-inspva.csv",
            "infer",
            ","
        ),
        (
            TIAND / "RADAR" / "RADAR" /
            "RADAR_Front" / "13-19-16.525363.csv",
            None,
            ","
        ),
        (
            TIAND / "Synchronisation_timestamps" /
            "Synchronisation_timestamps" /
            "Lidar_Camera_synchronisation.csv",
            "infer",
            ","
        ),
        (
            TIAND / "Synchronisation_timestamps" /
            "Synchronisation_timestamps" /
            "Radar_Camera_Synchronization.csv",
            "infer",
            None
        )
    ]

    records = []

    for path, header, separator in targets:

        if not path.exists():
            print("\nMissing:", path)
            continue

        record = inspect_csv(
            path,
            header=header,
            separator=separator
        )

        records.append(record)

        print("\nTIAND:", path.name)
        print("Status:", record["status"])
        print("Column count:", record.get("column_count"))
        print("Columns:", record.get("columns"))

        if record.get("sample"):
            print("First sample row:", record["sample"][0])

    output = OUTPUT / "tiand_csv_validation.json"

    with open(output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, default=str)


# =========================================================
# MAIN
# =========================================================

def main():

    inspect_idd_npy()
    inspect_idd_csv()
    inspect_tiand_csv()

    print("\nContent validation completed.")
    print("Output:", OUTPUT)


if __name__ == "__main__":
    main()
