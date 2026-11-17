
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\raw"
    r"\idd_multimodal"
)

OUTPUT = Path(
    r"E:\JB_Mtech_Project\RaahiSense\data\generated"
    r"\phase1\idd_lidar_visualization"
)
OUTPUT.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# FIND A VALID LIDAR FRAME
# --------------------------------------------------

files = sorted(ROOT.rglob("*.npy"))

if not files:
    raise FileNotFoundError("No NPY files found in IDD directory.")

selected_file = None
points = None

for file in files:
    try:
        arr = np.load(file, allow_pickle=False)

        if arr.ndim == 2 and arr.shape[1] == 5:
            selected_file = file
            points = arr
            break

    except Exception:
        continue

if points is None:
    raise ValueError("No valid five-column LiDAR frame found.")

print("Selected file:", selected_file)
print("Point-cloud shape:", points.shape)
print("Data type:", points.dtype)

# --------------------------------------------------
# EXTRACT FIRST THREE COLUMNS
# Provisional X, Y, Z interpretation only
# --------------------------------------------------

xyz = points[:, :3]

valid_mask = np.isfinite(xyz).all(axis=1)
xyz = xyz[valid_mask]

print("Finite points:", len(xyz))
print("X range:", xyz[:, 0].min(), xyz[:, 0].max())
print("Y range:", xyz[:, 1].min(), xyz[:, 1].max())
print("Z range:", xyz[:, 2].min(), xyz[:, 2].max())

# Limit plotted points for performance.
MAX_POINTS = 50000

if len(xyz) > MAX_POINTS:
    indices = np.linspace(
        0, len(xyz) - 1, MAX_POINTS, dtype=int
    )
    plot_xyz = xyz[indices]
else:
    plot_xyz = xyz

# --------------------------------------------------
# 3D POINT-CLOUD VISUALIZATION
# --------------------------------------------------

fig = plt.figure(figsize=(12, 9), facecolor="white")
ax = fig.add_subplot(111, projection="3d")

ax.scatter(
    plot_xyz[:, 0],
    plot_xyz[:, 1],
    plot_xyz[:, 2],
    s=0.25,
    c=plot_xyz[:, 2],
    cmap="viridis",
    alpha=0.8
)

ax.set_title(
    f"IDD LiDAR Point Cloud\n{selected_file.name}",
    pad=18
)
ax.set_xlabel("Column 1 (provisional X)")
ax.set_ylabel("Column 2 (provisional Y)")
ax.set_zlabel("Column 3 (provisional Z)")

ax.set_facecolor("white")
fig.tight_layout()

path_3d = OUTPUT / "idd_lidar_3d_view.png"
fig.savefig(path_3d, dpi=200, bbox_inches="tight")
plt.close(fig)

# --------------------------------------------------
# TOP-DOWN XY VIEW
# --------------------------------------------------

fig, ax = plt.subplots(figsize=(10, 8), facecolor="white")

scatter = ax.scatter(
    plot_xyz[:, 0],
    plot_xyz[:, 1],
    c=plot_xyz[:, 2],
    s=0.25,
    cmap="viridis",
    alpha=0.8
)

ax.set_title("IDD LiDAR Point Cloud — XY Projection")
ax.set_xlabel("Column 1 (provisional X)")
ax.set_ylabel("Column 2 (provisional Y)")
ax.set_aspect("equal", adjustable="datalim")
ax.grid(True, alpha=0.2)

fig.colorbar(scatter, ax=ax, label="Column 3 value")
fig.tight_layout()

path_xy = OUTPUT / "idd_lidar_xy_view.png"
fig.savefig(path_xy, dpi=200, bbox_inches="tight")
plt.close(fig)

print("\nVisualization completed.")
print("3D view:", path_3d)
print("XY view:", path_xy)
