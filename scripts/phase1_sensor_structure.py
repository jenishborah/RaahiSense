
from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# 1. PATH CONFIGURATION
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifests" / "phase1"

OUTPUT = ROOT / "data" / "generated" / "phase1" / "sensor_structure"
CHARTS = OUTPUT / "charts"
SCHEMAS = OUTPUT / "csv_schemas"

for folder in [OUTPUT, CHARTS, SCHEMAS]:
    folder.mkdir(parents=True, exist_ok=True)


DATASETS = {
    "idd_primary": RAW / "idd_multimodal" / "primary",
    "idd_secondary": RAW / "idd_multimodal" / "secondary",
    "idd_supplement": RAW / "idd_multimodal" / "supplement",
    "tiand": RAW / "TIAND_MULTIMODAL_DATASET"
}


# =========================================================
# 2. LOAD EXISTING INVENTORY
# =========================================================

def load_inventory(dataset_name):

    inventory_path = (
        MANIFEST / f"{dataset_name}_inventory.csv"
    )

    if not inventory_path.exists():
        print(f"[WARNING] Inventory missing: {inventory_path}")
        return pd.DataFrame()

    return pd.read_csv(inventory_path)


# =========================================================
# 3. DIRECTORY STRUCTURE ANALYSIS
# =========================================================

def get_directory_level(relative_path, level=1):

    parts = Path(str(relative_path)).parts

    if not parts:
        return "[root]"

    return "/".join(parts[:level])


def analyze_directories(dataset_name, df):

    if df.empty:
        return pd.DataFrame()

    result = df.copy()

    result["directory_level_1"] = result[
        "relative_path"
    ].apply(lambda x: get_directory_level(x, 1))

    result["directory_level_2"] = result[
        "relative_path"
    ].apply(lambda x: get_directory_level(x, 2))

    summary = (
        result.groupby(
            ["directory_level_1", "directory_level_2"],
            dropna=False
        )
        .agg(
            total_files=("file_name", "count"),
            total_size_bytes=("size_bytes", "sum")
        )
        .reset_index()
    )

    summary["total_size_gb"] = (
        summary["total_size_bytes"] / (1024 ** 3)
    ).round(4)

    output = OUTPUT / f"{dataset_name}_directory_summary.csv"
    summary.to_csv(output, index=False)

    return summary


# =========================================================
# 4. FILE EXTENSION ANALYSIS
# =========================================================

def analyze_extensions(dataset_name, df):

    if df.empty:
        return pd.DataFrame()

    summary = (
        df.groupby("extension")
        .agg(
            file_count=("file_name", "count"),
            total_size_bytes=("size_bytes", "sum")
        )
        .reset_index()
        .sort_values("file_count", ascending=False)
    )

    summary["total_size_gb"] = (
        summary["total_size_bytes"] / (1024 ** 3)
    ).round(4)

    output = OUTPUT / f"{dataset_name}_extension_summary.csv"
    summary.to_csv(output, index=False)

    return summary


# =========================================================
# 5. PRELIMINARY MODALITY AVAILABILITY
# =========================================================

def analyze_modalities(dataset_name, df):

    if df.empty:
        return pd.DataFrame()

    summary = (
        df.groupby(
            ["possible_modality", "file_type"],
            dropna=False
        )
        .agg(
            file_count=("file_name", "count"),
            total_size_bytes=("size_bytes", "sum")
        )
        .reset_index()
    )

    summary["total_size_gb"] = (
        summary["total_size_bytes"] / (1024 ** 3)
    ).round(4)

    summary.insert(0, "dataset", dataset_name)

    output = OUTPUT / f"{dataset_name}_modality_candidates.csv"
    summary.to_csv(output, index=False)

    return summary


# =========================================================
# 6. CSV SCHEMA INSPECTION
# =========================================================

def inspect_csv_files(dataset_name, df, dataset_root):

    if df.empty:
        return []

    csv_records = []

    csv_rows = df[
    df["extension"].str.lower().isin([".csv", ".tsv"])
]

# Inspect a representative sample, not thousands of files.
    csv_rows = (
    csv_rows
    .groupby("parent_folder", group_keys=False)
    .head(3)
    .head(30)
)

    for _, record in csv_rows.iterrows():

        relative_path = Path(record["relative_path"])
        file_path = dataset_root / relative_path

        schema_record = {
            "dataset": dataset_name,
            "file_name": record["file_name"],
            "relative_path": record["relative_path"],
            "status": "not_inspected",
            "columns": [],
            "sample_records": []
        }

        try:
            # Inspect only a few records; do not load the whole file.
            separator = "\t" if file_path.suffix.lower() == ".tsv" else ","

            sample = pd.read_csv(
                file_path,
                sep=separator,
                nrows=5,
                encoding="utf-8",
                on_bad_lines="warn"
            )

            schema_record["status"] = "success"
            schema_record["columns"] = [
                str(col) for col in sample.columns
            ]

            schema_record["sample_records"] = (
                sample.head(3)
                .astype(object)
                .where(pd.notna(sample), None)
                .to_dict(orient="records")
            )

            schema_record["sample_dtypes"] = {
                str(col): str(dtype)
                for col, dtype in sample.dtypes.items()
            }

        except UnicodeDecodeError:
            try:
                sample = pd.read_csv(
                    file_path,
                    sep=separator,
                    nrows=5,
                    encoding="latin-1",
                    on_bad_lines="warn"
                )

                schema_record["status"] = "success_latin1"
                schema_record["columns"] = [
                    str(col) for col in sample.columns
                ]

                schema_record["sample_records"] = (
                    sample.head(3)
                    .astype(object)
                    .where(pd.notna(sample), None)
                    .to_dict(orient="records")
                )

                schema_record["sample_dtypes"] = {
                    str(col): str(dtype)
                    for col, dtype in sample.dtypes.items()
                }

            except Exception as error:
                schema_record["status"] = f"error: {error}"

        except Exception as error:
            schema_record["status"] = f"error: {error}"

        csv_records.append(schema_record)

        safe_name = (
            Path(record["file_name"]).stem
            + "_schema.json"
        )

        schema_path = SCHEMAS / dataset_name / safe_name
        schema_path.parent.mkdir(parents=True, exist_ok=True)

        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(
                schema_record,
                f,
                indent=4,
                ensure_ascii=False,
                default=str
            )

        print(
            f"CSV inspected: {dataset_name}/"
            f"{record['relative_path']} "
            f"-> {schema_record['status']}"
        )

    return csv_records


# =========================================================
# 7. CHART GENERATION
# =========================================================

def save_chart(series, title, xlabel, ylabel, output_path):

    if series.empty:
        return

    plt.figure(figsize=(11, 6))

    series.plot(kind="bar")

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)

    plt.xticks(rotation=40, ha="right")
    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()


def generate_charts(dataset_name, extension_df, directory_df, modality_df):

    # Extension chart
    if not extension_df.empty:

        top_extensions = (
            extension_df
            .set_index("extension")["file_count"]
            .head(15)
        )

        save_chart(
            top_extensions,
            f"{dataset_name}: File Extension Distribution",
            "Extension",
            "Number of Files",
            CHARTS / f"{dataset_name}_extensions.png"
        )

    # Directory chart
    if not directory_df.empty:

        top_directories = (
            directory_df
            .groupby("directory_level_1")["total_files"]
            .sum()
            .sort_values(ascending=False)
        )

        save_chart(
            top_directories,
            f"{dataset_name}: Directory Distribution",
            "Directory",
            "Number of Files",
            CHARTS / f"{dataset_name}_directories.png"
        )

    # Modality candidate chart
    if not modality_df.empty:

        modality_counts = (
            modality_df
            .groupby("possible_modality")["file_count"]
            .sum()
            .sort_values(ascending=False)
        )

        save_chart(
            modality_counts,
            f"{dataset_name}: Modality Candidates",
            "Candidate Modality",
            "Number of Files",
            CHARTS / f"{dataset_name}_modality_candidates.png"
        )


# =========================================================
# 8. MAIN EXECUTION
# =========================================================

def main():

    all_modality_summaries = []
    all_csv_schemas = []

    for dataset_name, dataset_root in DATASETS.items():

        print(f"\n{'=' * 60}")
        print(f"ANALYSING: {dataset_name}")
        print(f"{'=' * 60}")

        df = load_inventory(dataset_name)

        if df.empty:
            continue

        directory_summary = analyze_directories(
            dataset_name, df
        )

        extension_summary = analyze_extensions(
            dataset_name, df
        )

        modality_summary = analyze_modalities(
            dataset_name, df
        )

        csv_schemas = inspect_csv_files(
            dataset_name,
            df,
            dataset_root
        )

        all_csv_schemas.extend(csv_schemas)

        if not modality_summary.empty:
            all_modality_summaries.append(modality_summary)

        generate_charts(
            dataset_name,
            extension_summary,
            directory_summary,
            modality_summary
        )

        print(f"\nTop extensions for {dataset_name}:")
        if not extension_summary.empty:
            print(extension_summary.head(10).to_string(index=False))

        print(f"\nDirectory summary for {dataset_name}:")
        if not directory_summary.empty:
            print(directory_summary.head(15).to_string(index=False))

    # Combined candidate matrix across components
    if all_modality_summaries:

        combined = pd.concat(
            all_modality_summaries,
            ignore_index=True
        )

        combined.to_csv(
            OUTPUT / "sensor_availability_candidates.csv",
            index=False
        )

    # CSV schema index
    if all_csv_schemas:

        schema_index = []

        for item in all_csv_schemas:
            schema_index.append({
                "dataset": item["dataset"],
                "file_name": item["file_name"],
                "relative_path": item["relative_path"],
                "status": item["status"],
                "column_count": len(item["columns"]),
                "columns": " | ".join(item["columns"])
            })

        pd.DataFrame(schema_index).to_csv(
            OUTPUT / "csv_schema_index.csv",
            index=False
        )

    print("\nPhase 1 Step 3 completed.")
    print(f"Output directory: {OUTPUT}")


if __name__ == "__main__":
    main()
