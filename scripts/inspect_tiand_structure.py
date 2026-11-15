
from pathlib import Path

root = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw\TIAND_MULTIMODAL_DATASET"
)

print("\nTIAND ROOT:", root)
print("Exists:", root.exists())

if root.exists():
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            relative = path.relative_to(root)
            depth = len(relative.parts)

            if depth <= 4:
                print("  " * depth + path.name + "/")
