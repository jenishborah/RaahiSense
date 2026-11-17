from __future__ import annotations

import argparse
import json
import math
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CLASS_NAMES = [
    "motorcycle",
    "rider",
    "car",
    "person",
    "autorickshaw",
    "truck",
    "vehicle fallback",
    "bus",
    "traffic sign",
    "animal",
    "traffic light",
    "bicycle",
    "caravan",
    "train",
    "trailer",
]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}


def read_split(path: Path) -> list[str]:
    entries = [line.strip().replace("\\", "/") for line in path.read_text(encoding="utf-8-sig").splitlines()]
    return [entry for entry in entries if entry]


def write_yaml(path: Path, dataset_root: Path) -> None:
    # Keep test out of data.yaml: local test ground-truth annotations are unavailable.
    lines = [
        f"path: {json.dumps(dataset_root.resolve().as_posix())}",
        "train: images/train",
        "val: images/val",
        "names:",
    ]
    for idx, name in enumerate(CLASS_NAMES):
        lines.append(f"  {idx}: {json.dumps(name, ensure_ascii=False)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def convert_box(obj: ET.Element, width: float, height: float):
    name = (obj.findtext("name") or "").strip()
    if not name:
        return None, "missing_class_name"

    if name not in CLASS_TO_ID:
        return None, f"unknown_class:{name}"

    box = obj.find("bndbox")
    if box is None:
        return None, "missing_bndbox"

    try:
        xmin = float(box.findtext("xmin"))
        ymin = float(box.findtext("ymin"))
        xmax = float(box.findtext("xmax"))
        ymax = float(box.findtext("ymax"))
    except (TypeError, ValueError):
        return None, "invalid_coordinates"

    values = (xmin, ymin, xmax, ymax)
    if not all(math.isfinite(v) for v in values):
        return None, "non_finite_coordinates"

    original = values

    # Clip boundary overflow to the image coordinate range.
    xmin = min(max(xmin, 0.0), width)
    xmax = min(max(xmax, 0.0), width)
    ymin = min(max(ymin, 0.0), height)
    ymax = min(max(ymax, 0.0), height)

    was_clipped = (xmin, ymin, xmax, ymax) != original

    if xmax <= xmin or ymax <= ymin:
        return None, "degenerate_after_clipping"

    x_center = ((xmin + xmax) / 2.0) / width
    y_center = ((ymin + ymax) / 2.0) / height
    box_width = (xmax - xmin) / width
    box_height = (ymax - ymin) / height

    normalized = (x_center, y_center, box_width, box_height)
    if not all(math.isfinite(v) for v in normalized):
        return None, "non_finite_normalized_coordinates"

    if not (
        0.0 <= x_center <= 1.0
        and 0.0 <= y_center <= 1.0
        and 0.0 < box_width <= 1.0
        and 0.0 < box_height <= 1.0
    ):
        return None, "normalized_box_out_of_range"

    line = f"{CLASS_TO_ID[name]} " + " ".join(f"{v:.8f}" for v in normalized)
    return (line, was_clipped, name), None


def copy_image(source: Path, destination: Path, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    if mode == "hardlink":
        try:
            destination.hardlink_to(source)
            return
        except OSError as exc:
            raise RuntimeError(
                f"Could not create hard link from {source} to {destination}. "
                "Use --image-mode copy instead. Hard links require the same volume."
            ) from exc

    shutil.copy2(source, destination)


def process_split(
    split: str,
    entries: list[str],
    source_root: Path,
    output_root: Path,
    image_mode: str,
    report: dict,
) -> None:
    image_source_root = source_root / "JPEGImages"
    xml_source_root = source_root / "Annotations"

    split_report = {
        "listed_entries": len(entries),
        "images_written": 0,
        "label_files_written": 0,
        "objects_written": 0,
        "boxes_clipped": 0,
        "boxes_excluded": 0,
        "empty_label_files": 0,
        "missing_images": [],
        "missing_xml": [],
        "xml_errors": [],
        "excluded_box_reasons": Counter(),
        "clipped_classes": Counter(),
    }

    for entry in entries:
        relative = Path(*entry.split("/"))
        image_src = image_source_root / relative.with_suffix(".jpg")
        xml_src = xml_source_root / relative.with_suffix(".xml")

        image_dst = output_root / "images" / split / relative.with_suffix(".jpg")
        label_dst = output_root / "labels" / split / relative.with_suffix(".txt")

        if not image_src.is_file():
            split_report["missing_images"].append(entry)
            continue

        copy_image(image_src, image_dst, image_mode)
        split_report["images_written"] += 1

        # Test labels are unavailable in this local dataset. Do not create
        # empty test label files because that would imply negative ground truth.
        if split == "test":
            continue

        if not xml_src.is_file():
            split_report["missing_xml"].append(entry)
            continue

        try:
            root = ET.parse(xml_src).getroot()
        except ET.ParseError as exc:
            split_report["xml_errors"].append({"entry": entry, "error": str(exc)})
            continue

        size = root.find("size")
        if size is None:
            split_report["xml_errors"].append({"entry": entry, "error": "missing_size"})
            continue

        try:
            width = float(size.findtext("width"))
            height = float(size.findtext("height"))
        except (TypeError, ValueError):
            split_report["xml_errors"].append({"entry": entry, "error": "invalid_dimensions"})
            continue

        if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
            split_report["xml_errors"].append({"entry": entry, "error": "non_positive_or_non_finite_dimensions"})
            continue

        yolo_lines = []
        for obj in root.findall("object"):
            result, reason = convert_box(obj, width, height)
            if reason:
                split_report["boxes_excluded"] += 1
                split_report["excluded_box_reasons"][reason] += 1
                continue

            line, was_clipped, class_name = result
            yolo_lines.append(line)
            split_report["objects_written"] += 1

            if was_clipped:
                split_report["boxes_clipped"] += 1
                split_report["clipped_classes"][class_name] += 1

        label_dst.parent.mkdir(parents=True, exist_ok=True)
        label_dst.write_text("\n".join(yolo_lines) + ("\n" if yolo_lines else ""), encoding="utf-8")
        split_report["label_files_written"] += 1

        if not yolo_lines:
            split_report["empty_label_files"] += 1

    split_report["excluded_box_reasons"] = dict(split_report["excluded_box_reasons"])
    split_report["clipped_classes"] = dict(split_report["clipped_classes"])
    report["splits"][split] = split_report


def main():
    parser = argparse.ArgumentParser(
        description="Non-destructively convert IDD Detection Pascal VOC XML annotations to YOLO format."
    )
    parser.add_argument(
        "--source",
        default="data/raw/idd_detection/original/IDD_Detection",
        help="Original IDD_Detection directory.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/idd_detection_yolo",
        help="Processed YOLO dataset output directory.",
    )
    parser.add_argument(
        "--image-mode",
        choices=["copy", "hardlink"],
        default="copy",
        help="copy is safer but uses extra disk space; hardlink saves space but shares file data with originals.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow writing into an existing output directory. Existing files at matching paths may be replaced.",
    )
    args = parser.parse_args()

    source_root = Path(args.source).resolve()
    output_root = Path(args.output).resolve()

    required = [
        source_root / "JPEGImages",
        source_root / "Annotations",
        source_root / "train.txt",
        source_root / "val.txt",
        source_root / "test.txt",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Required source paths are missing:\n" + "\n".join(missing))

    if output_root.exists() and any(output_root.iterdir()) and not args.force:
        raise SystemExit(
            f"Output directory already exists and is not empty: {output_root}\n"
            "Inspect it first, or choose another --output path. Use --force only if replacement is intended."
        )

    output_root.mkdir(parents=True, exist_ok=True)

    splits = {
        "train": read_split(source_root / "train.txt"),
        "val": read_split(source_root / "val.txt"),
        "test": read_split(source_root / "test.txt"),
    }

    report = {
        "dataset": "IDD Detection",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source_root),
        "output_root": str(output_root),
        "image_mode": args.image_mode,
        "test_ground_truth_available_locally": False,
        "class_names": CLASS_NAMES,
        "class_to_id": CLASS_TO_ID,
        "split_overlap": {
            "train_val": len(set(splits["train"]) & set(splits["val"])),
            "train_test": len(set(splits["train"]) & set(splits["test"])),
            "val_test": len(set(splits["val"]) & set(splits["test"])),
        },
        "splits": {},
    }

    for split in ("train", "val", "test"):
        print(f"Processing {split}: {len(splits[split]):,} entries")
        process_split(
            split=split,
            entries=splits[split],
            source_root=source_root,
            output_root=output_root,
            image_mode=args.image_mode,
            report=report,
        )
        print(
            f"  images written: {report['splits'][split]['images_written']:,}; "
            f"labels written: {report['splits'][split]['label_files_written']:,}; "
            f"objects written: {report['splits'][split]['objects_written']:,}"
        )

    write_yaml(output_root / "data.yaml", output_root)

    report_path = output_root / "conversion_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nConversion finished.")
    print("Dataset YAML:", output_root / "data.yaml")
    print("Conversion report:", report_path)
    print("\nImportant: test images were copied without label files because local test XML annotations are unavailable.")
    print("Review conversion_report.json before training.")


if __name__ == "__main__":
    main()
