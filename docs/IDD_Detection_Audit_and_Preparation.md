# RaahiSense — IDD Detection Dataset Audit and Preparation Notes

**Document status:** Dataset inspection and validation completed up to the pre-conversion stage  
**Project:** RaahiSense  
**Purpose:** Record the IDD Detection dataset location, structure, annotations, split integrity, quality findings, and agreed preparation policy before converting Pascal VOC annotations to YOLO format.

---

## 1. Role of IDD Detection in RaahiSense

RaahiSense currently has the **IDD Multimodal** dataset, which provides camera imagery and other sensor streams but does not provide the object-detection bounding-box annotations needed for supervised detector training in the inspected local files.

The separately downloaded **IDD Detection** dataset provides labelled road-scene images. It will be used to train and validate an object detector. The trained detector can subsequently be applied to the camera images in IDD Multimodal.

These are separate datasets. IDD Detection is being used as the labelled detector-training source; it does not provide frame-by-frame correspondence with IDD Multimodal.

The current work is limited to preparing the object-detection dataset. Tracking, trajectory estimation, motion analysis and multimodal fusion will be developed as separate downstream components.

## 2. Local dataset location

RaahiSense repository:

```text
E:\JB_Mtech_Project\RaahiSense
```

IDD Detection extracted directory:

```text
data/
└── raw/
    └── idd_detection/
        └── original/
            └── IDD_Detection/
```

The extracted dataset currently contains:

```text
IDD_Detection/
├── Annotations/
├── JPEGImages/
├── train.txt
├── val.txt
└── test.txt
```

The `Annotations` and `JPEGImages` directories contain nested subdirectories, including camera/sequence paths such as `frontFar/<sequence_name>/`.

**Data-preservation rule:** The original extracted dataset is treated as read-only. Conversion and cleaning outputs will be written to a separate processed-data directory. Do not rename, move, overwrite or delete original images, XML files or split lists.

## 3. Initial file inventory

The recursive file inventory reported:

| Extension | Count |
|---|---:|
| `.jpg` | 46,659 |
| `.xml` | 41,857 |
| `.txt` | 3 |
| `.DS_Store` | 2 |
| `.swp` | 1 |

The three text files are the official split lists: `train.txt`, `val.txt` and `test.txt`.

The split lists account for 46,588 image entries. The initial JPEG inventory contains 46,659 images, so 71 JPEG files are not represented by those split entries. This is an inventory difference only; it does not by itself indicate an error.

## 4. Annotation format and example

The inspected annotation is XML in a Pascal VOC-style structure.

Example file:

```text
Annotations/frontFar/BLR-2018-03-22_17-39-26_2_frontFar/0000060.xml
```

The sample XML contains:

- `<filename>`: image filename, e.g. `0000060.jpg`
- `<folder>`: sequence/folder information
- `<size>`: image width, height and depth
- One or more `<object>` elements
- `<object><name>`: object class
- `<bndbox>`: `xmin`, `ymin`, `xmax`, `ymax`

The inspected sample reports image dimensions of 1280 × 964 pixels and includes classes such as `truck`, `person`, `autorickshaw` and `car`.

The dataset therefore needs annotation conversion before it can be used directly by a YOLO training pipeline.

## 5. Official split counts and validation

The split-list counts are:

| Split | Image entries |
|---|---:|
| Train | 31,569 |
| Validation | 10,225 |
| Test | 4,794 |
| **Total** | **46,588** |

A path-matching validation checked each split entry against:

- `JPEGImages/<entry>.jpg`
- `Annotations/<entry>.xml`

Results:

| Split | Entries | Missing images | Missing XML |
|---|---:|---:|---:|
| Train | 31,569 | 0 | 0 |
| Validation | 10,225 | 0 | 0 |
| Test | 4,794 | 0 | 4,794 |

The train and validation entries all have matching images and XML annotations.

All test images exist, but no corresponding XML annotations were found in the local extracted dataset. The test split must therefore be treated as **unlabelled locally** unless its ground-truth annotations are obtained separately.

Split-integrity checks:

| Check | Result |
|---|---:|
| Duplicate train entries | 0 |
| Duplicate validation entries | 0 |
| Duplicate test entries | 0 |
| Train–validation path overlap | 0 |
| Train–test path overlap | 0 |
| Validation–test path overlap | 0 |

The official split lists will be preserved. Do not randomly re-split the images or move entries between splits.

### How the splits will be used

- **Train:** supervised detector training.
- **Validation:** validation during training and model/configuration selection.
- **Test:** inference-only on the locally available images. Do not report ground-truth-based test metrics without test labels.

Predictions on unlabelled test images are model outputs, not ground truth.

## 6. Object classes and annotation counts

The XML inspection found 15 classes and 507,576 annotated objects.

| Proposed class ID | Class name | Object annotations |
|---:|---|---:|
| 0 | motorcycle | 103,608 |
| 1 | rider | 97,626 |
| 2 | car | 90,520 |
| 3 | person | 88,397 |
| 4 | autorickshaw | 32,280 |
| 5 | truck | 27,837 |
| 6 | vehicle fallback | 21,081 |
| 7 | bus | 18,745 |
| 8 | traffic sign | 14,203 |
| 9 | animal | 6,224 |
| 10 | traffic light | 3,699 |
| 11 | bicycle | 3,142 |
| 12 | caravan | 136 |
| 13 | train | 60 |
| 14 | trailer | 18 |
| | **Total** | **507,576** |

The class distribution is imbalanced. Motorcycle, rider, car and person have the largest annotation counts. Caravan, train and trailer have very few annotations.

The proposed IDs above follow the order in which the classes were reported during inspection. They must be saved as a fixed class mapping in the processed dataset configuration and reused consistently during training, validation and inference. Do not independently regenerate or reorder IDs in later scripts.

The class name `vehicle fallback` must be preserved exactly unless the dataset documentation establishes a different canonical name. Do not merge it into another class without a documented research decision.

## 7. XML annotation quality audit

A read-only audit parsed all 41,857 XML files.

| Check | Result |
|---|---:|
| XML files checked | 41,857 |
| Objects counted | 507,576 |
| Invalid bounding boxes | 264 |
| Invalid image dimensions | 0 |
| XML files without objects | 63 |
| XML parsing errors | 0 |

The class counts from this quality audit match the earlier class-count inspection.

### 7.1 Invalid bounding-box categories

A second diagnostic classified the 264 invalid boxes:

| Issue | Count |
|---|---:|
| Coordinates outside image bounds | 263 |
| Reversed or zero-height box | 1 |

Examples of the boundary issue include:

```text
Image dimensions: width=1280, height=964
Example box: xmin=1101, ymin=0, xmax=1281, ymax=878
```

Here, `xmax=1281` exceeds the image width of 1280 by one pixel.

Another example:

```text
Image dimensions: width=1280, height=964
Example box: xmin=1024, ymin=2, xmax=1281, ymax=962
```

The remaining invalid box has:

```text
xmin=1087, ymin=530, xmax=1097, ymax=530
```

This box has zero height because `ymin` equals `ymax`.

### 7.2 Empty XML files

There are 63 XML files with no `<object>` elements.

A split-membership check found:

| Split | Empty XML files referenced |
|---|---:|
| Train | 0 |
| Validation | 0 |
| Test | 0 |

These 63 empty XML files are not referenced by the official train, validation or test lists. They will not be added to the training or validation set as negative samples.

## 8. Agreed annotation-cleaning policy for conversion

The conversion will be non-destructive. Original XML files remain unchanged.

1. **Valid boxes:** Convert to YOLO normalized coordinates.
2. **Boundary overflow:** Clip coordinates to the valid image boundary, then check that the resulting box still has positive width and height. Record every corrected box.
3. **Degenerate or invalid boxes:** Exclude the affected box if it remains invalid after clipping. Record the XML path, object/class and reason in the conversion report.
4. **Empty XML files:** Do not add them to the train/validation splits because none is referenced by the official split lists.
5. **Missing test XML:** Do not fabricate labels. Test images can be used for inference, but not for ground-truth evaluation.
6. **Split integrity:** Preserve the original train, validation and test lists exactly.
7. **Class mapping:** Use the fixed 15-class ID mapping in Section 6.
8. **Auditability:** Generate a machine-readable conversion report recording image counts, label counts, corrected boxes, excluded boxes, missing references and conversion errors.

Clipping a boundary coordinate is a data-cleaning decision, not a claim that the original annotation was correct. The report must retain evidence of every such correction.

## 9. Pascal VOC to YOLO coordinate conversion

For an image with width \(W\) and height \(H\), and a valid box with corners \((x_{\min}, y_{\min}, x_{\max}, y_{\max})\):

\[
x_c = \frac{x_{\min}+x_{\max}}{2W}
\]

\[
y_c = \frac{y_{\min}+y_{\max}}{2H}
\]

\[
w = \frac{x_{\max}-x_{\min}}{W}
\]

\[
h = \frac{y_{\max}-y_{\min}}{H}
\]

Each YOLO label line will have the form:

```text
class_id x_center y_center width height
```

The four box values are normalized relative to image dimensions. The class ID is an integer from 0 to 14 according to the fixed mapping.

The implementation must validate that each converted coordinate is finite and that normalized width and height are positive. The conversion must not silently accept malformed or degenerate boxes.

## 10. Planned processed-data structure

The proposed output directory is:

```text
data/
├── raw/
│   └── idd_detection/
│       └── original/
│           └── IDD_Detection/
│               ├── Annotations/
│               ├── JPEGImages/
│               ├── train.txt
│               ├── val.txt
│               └── test.txt
│
└── processed/
    └── idd_detection_yolo/
        ├── images/
        │   ├── train/
        │   ├── val/
        │   └── test/
        ├── labels/
        │   ├── train/
        │   ├── val/
        │   └── test/
        ├── data.yaml
        └── conversion_report.json
```

This is the planned processed-data layout, not yet a created or validated output. The conversion implementation must preserve a consistent relative path mapping between each image and its label so that repeated filenames in different sequences do not overwrite one another.

For the test split, image files will be included. Label files should not be represented as genuine ground truth. The implementation should make the absence of test labels explicit in the report and dataset configuration.

## 11. Planned model-development sequence

After conversion and a second validation of the generated YOLO dataset:

1. Inspect the generated dataset configuration and class mapping.
2. Verify image-label pairs and count valid labels per split.
3. Visualize a sample of converted labels overlaid on images.
4. Confirm that boxes align with the visible objects.
5. Select a YOLO model/checkpoint and record its version.
6. Train the first baseline using the train split and validate using the validation split.
7. Record training configuration, environment, checkpoint, metrics and experiment outputs.
8. Use the unlabelled test images only for inference unless test annotations become available.
9. Later apply the trained detector to IDD Multimodal camera frames, keeping dataset provenance explicit.

Object detection is the first model component. Tracking methods such as ByteTrack or BoT-SORT will consume detections later; they are not trained by this XML-to-YOLO conversion. Trajectory estimation and motion analysis follow tracking. Multimodal fusion requires verified sensor timing and calibration.

## 12. Current status and immediate next action

**Completed:**

- Downloaded and extracted IDD Detection into the RaahiSense data directory.
- Identified the nested `Annotations` and `JPEGImages` structure.
- Confirmed Pascal VOC-style XML annotation format.
- Counted official train, validation and test entries.
- Verified image and annotation references for train and validation.
- Confirmed all test images exist but test XML annotations are unavailable locally.
- Checked duplicate entries and split overlap.
- Counted all 15 object classes and 507,576 object annotations.
- Audited XML parsing, dimensions, empty annotations and invalid boxes.
- Defined a non-destructive cleaning and conversion policy.

**Not yet done:**

- No XML annotations have been modified.
- No YOLO labels have been generated.
- No processed dataset has been created.
- No model has been trained.
- No training metrics have been measured.

**Immediate next action:** Implement and run a Python conversion script that creates `data/processed/idd_detection_yolo/`, converts the train and validation XML annotations into YOLO labels, handles the documented boundary and degenerate-box cases, preserves the official splits, and writes a detailed conversion report. Keep the original dataset unchanged.

---

*This document records the local inspection results and implementation decisions established in the RaahiSense project conversation. It does not replace the dataset's official documentation or establish annotation semantics beyond what was directly inspected.*
