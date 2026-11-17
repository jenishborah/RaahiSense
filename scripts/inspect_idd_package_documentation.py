
from pathlib import Path
import pandas as pd

ROOT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw\idd_multimodal"
)

OUTPUT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\generated"
    r"\phase1\idd_package_documentation"
)
OUTPUT.mkdir(parents=True, exist_ok=True)

extensions = {
    ".txt", ".md", ".json", ".yaml", ".yml",
    ".xml", ".pdf", ".csv", ".py", ".sh",
    ".ini", ".cfg", ".zip"
}

records = []

for path in ROOT.rglob("*"):
    if not path.is_file():
        continue

    if path.suffix.lower() not in extensions:
        continue

    records.append({
        "filename": path.name,
        "extension": path.suffix.lower(),
        "relative_path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size
    })

df = pd.DataFrame(records)

if not df.empty:
    df = df.sort_values(["extension", "relative_path"])

df.to_csv(
    OUTPUT / "idd_documentation_inventory.csv",
    index=False
)

print("\nDocumentation and metadata files:", len(df))

if not df.empty:
    print("\nFiles by extension:")
    print(df.groupby("extension").size().to_string())

    print("\nDiscovered files:")
    print(df.to_string(index=False))

print("\nReport saved to:", OUTPUT)
