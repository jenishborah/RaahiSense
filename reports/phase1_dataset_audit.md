# Phase 1 Dataset Audit --- RaahiSense

**Project:** RaahiSense\
**Phase:** Phase 1 --- Dataset Inventory, Structural Inspection and
Validation\
**Status:** Audit findings consolidated; ready for Common Data Model
design\
**Project root:** `E:\JB_Mtech_Project\RaahiSense`

------------------------------------------------------------------------

## 1. Purpose and scope

This report consolidates the Phase 1 inspection of the two datasets
selected for RaahiSense:

-   **IDD Multimodal** --- primary development dataset.
-   **TIAND Multimodal Dataset** --- secondary dataset for independent
    ingestion and cross-environment validation.

The audit covers local file availability, file formats, sensor
structures, frame/index correspondence, timestamp parsing,
synchronization metadata, calibration-file structure and known data
limitations.

The audit distinguishes between:

1.  **Observed facts** --- directly established from the local files and
    inspection outputs.
2.  **Provisional interpretations** --- plausible interpretations that
    still require authoritative documentation.
3.  **Unavailable or unresolved information** --- items that must not be
    assumed during ingestion.

The raw datasets must remain unchanged. Dataset-specific sessions and
timelines must remain separate.

## 2. Dataset overview

  -----------------------------------------------------------------------
  Dataset                 Role                    Locally observed
                                                  modalities
  ----------------------- ----------------------- -----------------------
  IDD Multimodal          Primary                 Stereo camera images,
                                                  GPS fields in selected
                                                  CSV splits, LiDAR
                                                  point-cloud arrays, OBD

  TIAND Multimodal        Secondary               Camera images, six
                                                  directional radar
                                                  streams, GNSS,
                                                  synchronization files
                                                  and calibration files
  -----------------------------------------------------------------------

The IDD package README describes stereo front-camera images at 15 fps,
GPS points at 15 Hz, 16-channel LiDAR and OBD data. The local package
inventory did not find a README or other documentation file; this
modality description was available from the separately inspected README
content.

The two datasets must not be combined into one physical timeline. Each
record must retain its dataset and session identity, original timestamp,
normalized timestamp, sensor identity, source-file provenance and
calibration reference where applicable.

## 3. Directory and file inventory

### 3.1 IDD Multimodal

Local root:

``` text
data\raw\idd_multimodal
```

  Subset          Files   Approximate size Observed contents
  ------------ -------- ------------------ -----------------------------------
  Primary        13,552          6.5114 GB 13,543 JPG images and 9 CSV files
  Secondary      13,543          6.6311 GB 13,543 JPG images
  Supplement      8,954          8.5033 GB 8,948 NPY files and 6 CSV files

The primary subset contains three sequences: `d0`, `d1` and `d2`. The
supplement contains LiDAR timestamp CSVs and OBD CSVs for these
sequences.

The local documentation inventory searched for `.txt`, `.md`, `.json`,
`.yaml`, `.yml`, `.xml`, `.pdf`, `.csv`, `.py`, `.sh`, `.ini`, `.cfg`
and `.zip` files under the IDD package root. It found 15 files, all
CSVs:

-   9 primary split CSVs: train, validation and test for each of `d0`,
    `d1` and `d2`.
-   3 LiDAR timestamp CSVs: one for each sequence.
-   3 OBD CSVs: one for each sequence.

No additional README, PDF, JSON metadata, source code, configuration
file or archive was found by that local inventory.

### 3.2 TIAND

Local root:

``` text
data\raw\TIAND_MULTIMODAL_DATASET
```

  -----------------------------------------------------------------------
  Component                           Observed local contents
  ----------------------------------- -----------------------------------
  Camera                              10,919 JPG images, 1280 × 720

  Radar                               19,917 CSV files across six
                                      directional folders

  GNSS                                One CSV file,
                                      `scene3-novatel-oem7-inspva.csv`

  LiDAR                               Directory exists; recursive
                                      inventory found 0 files

  Calibration                         LiDAR matrices, radar-camera
                                      projection matrix and radar
                                      mounting JSON

  Synchronization                     LiDAR-camera and radar-camera
                                      timestamp files
  -----------------------------------------------------------------------

Radar CSV counts by direction:

  Direction            Files
  ------------- ------------
  Back                 3,507
  Back_Left            3,493
  Back_Right           3,527
  Front                2,368
  Front_Left           3,485
  Front_Right          3,537
  **Total**       **19,917**

The six radar directions must remain separately identifiable during
ingestion.

## 4. IDD sensor inspection

### 4.1 Stereo camera

The IDD primary and secondary subsets contain 13,543 left-camera images
and 13,543 right-camera images, for 27,086 stereo images in total.

Observed properties:

-   Image format: JPG.
-   Resolution: 1920 × 1080.
-   Sequences: `d0`, `d1`, `d2`.

Frame counts:

  Sequence      Left images   Right images
  ----------- ------------- --------------
  d0                  4,531          4,531
  d1                  4,351          4,351
  d2                  4,661          4,661
  **Total**      **13,543**     **13,543**

The inspected filename/index sets showed complete left/right index
correspondence for all three sequences. This is index correspondence,
not independent proof of camera clock synchronization.

### 4.2 GPS

The primary split CSVs contain timestamp and image-index fields. The
inspected training CSVs also contain latitude, longitude and altitude.
The inspected test CSVs contain only timestamp and image index.

The validation CSV schema was not separately confirmed in the supplied
audit results. GPS availability must therefore be represented at
record/split level rather than assumed for every image.

### 4.3 LiDAR

The supplement contains 8,948 NPY files.

Observed array properties:

  Property                                    Result
  ------------------------------------ -------------
  Number of files                              8,948
  Total points                           228,223,591
  Array shape                                  N × 5
  Data type                                  float64
  Invalid arrays in inspected set                  0
  Non-finite values in inspected set               0
  Minimum points per file                     19,602
  Maximum points per file                     28,425
  Mean points per file                     25,505.54

The first three columns exhibit continuous values and spatial
point-cloud structure in the inspected visualizations. The fourth column
contains integer values from 0 to 15. The fifth contains integer values
from 0 to 255.

Provisional interpretations only:

  -----------------------------------------------------------------------
  Column                  Provisional             Evidence and limitation
                          interpretation          
  ----------------------- ----------------------- -----------------------
  1--3                    Spatial coordinates,    Continuous values and
                          possibly X, Y and Z     spatial point-cloud
                                                  structure; units and
                                                  coordinate frame are
                                                  not confirmed

  4                       Ring/channel identifier Exactly 16 observed
                                                  integer values, 0--15,
                                                  consistent with a
                                                  16-channel sensor;
                                                  official column
                                                  definition not found

  5                       Intensity-like          Integer values 0--255;
                          attribute               physical meaning and
                                                  encoding are not
                                                  confirmed
  -----------------------------------------------------------------------

**Ingestion rule:** Preserve all five columns without renaming or
transforming them. Until authoritative documentation is found, represent
them as `attribute_1` through `attribute_5` or preserve the original
array unchanged with a versioned interpretation layer.

The weighted statistics from the value-frequency analysis were:

-   Column 4 weighted mean: approximately 7.100384; weighted median: 7.
-   Column 5 weighted mean: approximately 17.794377; weighted median:
    13.

These are descriptive statistics, not semantic definitions.

### 4.4 OBD

Three OBD CSV files were found, one per sequence.

  Sequence         Rows
  ----------- ---------
  d0                155
  d1                149
  d2                161
  **Total**     **465**

Observed fields:

``` text
timestamp, speed, rpm, gear, clv, throttle_position
```

The timestamp strings use the form `HH-MM-SS-ffffff`. All timestamps in
the inspected files were parsed. After rollover adjustment, no
non-increasing timestamp steps were reported.

Observed interval characteristics:

-   Median interval: approximately 1.536 seconds.
-   Maximum gap in `d0`: 6.144 seconds.
-   Maximum gap in `d1`: 17 seconds.
-   Maximum gap in `d2`: 12.288 seconds.

Parsing these strings as time-of-day values does not establish clock
synchronization with camera or LiDAR timestamps.

## 5. IDD frame/index correspondence

The following table summarizes the inspected filename/index overlap.

  -----------------------------------------------------------------------------------
  Sequence         Left      Right      LiDAR   Left/right   Left/LiDAR   Right/LiDAR
                                                    common       common        common
  ---------- ---------- ---------- ---------- ------------ ------------ -------------
  d0              4,531      4,531      2,993        4,531        2,993         2,993

  d1              4,351      4,351      2,875        4,351        2,875         2,875

  d2              4,661      4,661      3,080        4,661        3,080         3,080
  -----------------------------------------------------------------------------------

No left-only or right-only image indices were reported.

### 5.1 Split-wise LiDAR overlap

  ------------------------------------------------------------------------
  Sequence    Split          Image indices   LiDAR overlap  No LiDAR index
                                                                   overlap
  ----------- ------------ --------------- --------------- ---------------
  d0          Train                  2,211           2,211               0

  d0          Validation               930             782             148

  d0          Test                   1,390               0           1,390

  d1          Train                  2,166           2,166               0

  d1          Validation               870             709             161

  d1          Test                   1,315               0           1,315

  d2          Train                  2,046           2,046               0

  d2          Validation             1,110           1,034              76

  d2          Test                   1,505               0           1,505
  ------------------------------------------------------------------------

All inspected split `image_idx` values were valid and unique.

**Interpretation:** The training split has complete LiDAR index overlap
in the inspected sequences. Validation has partial overlap. Test has no
LiDAR overlap under the current index mapping. Index overlap is a
candidate correspondence only; it does not prove temporal
synchronization or physical sensor alignment.

The initial multimodal development pipeline should therefore use the IDD
training split. Validation processing must explicitly handle missing
LiDAR. Do not claim LiDAR-supported test evaluation unless a valid
correspondence is established.

### 5.2 LiDAR timestamp tables

  ---------------------------------------------------------------------------------
  Sequence                   Rows Frame range   First raw         Last raw
                                                timestamp         timestamp
  ------------- ----------------- ------------- ----------------- -----------------
  d0                        2,993 0--2,992      09-00-31-462000   09-05-33-235000

  d1                        2,875 0--2,874      13-00-06-254000   13-04-56-132000

  d2                        3,080 0--3,079      10-30-38-536000   10-35-12-680000
  ---------------------------------------------------------------------------------

The inspected tables had unique frame IDs, no duplicate frame values and
no timestamp parse failures.

## 6. TIAND sensor inspection

### 6.1 Camera

-   10,919 JPG images.
-   Resolution: 1280 × 720.

The local inventory establishes file count and image dimensions. It does
not, by itself, establish the complete camera capture rate or the exact
mapping of every image to every radar/GNSS record.

### 6.2 Radar

There are 19,917 CSV files across six directional folders.

The inspected files were readable and contained numeric comma-separated
values. The number of columns varied between files and directions.
Sample files contained 13 rows, but this should not be treated as a
universal fixed row count without a full per-file validation.

Variable row/column structures may represent variable-length radar
observations, but that interpretation remains a hypothesis until the
dataset's radar format is documented.

**Ingestion rule:** Preserve direction, original file identity, row
order and raw numeric values. Do not assign physical names to columns
without documentation.

### 6.3 GNSS

One GNSS CSV was found:

``` text
scene3-novatel-oem7-inspva.csv
```

It contains 13 columns:

``` text
time
.header.seq
.header.stamp.secs
.header.stamp.nsecs
.latitude
.longitude
.height
.north_velocity
.east_velocity
.up_velocity
.roll
.pitch
.azimuth
```

An inspected example timestamp was:

``` text
2023/09/02/13:19:16.462751
```

The inspected example included latitude, longitude, height,
north/east/up velocity, roll, pitch and azimuth values. Units, reference
frames and angular conventions should be taken from authoritative
dataset documentation before applying transformations.

### 6.4 LiDAR

The TIAND LiDAR directory exists, but the recursive local inventory
found **zero files**.

For the current local copy, TIAND LiDAR must be marked unavailable. The
presence of calibration files or synchronization metadata does not
establish that LiDAR measurements are present.

## 7. Timestamp and synchronization inspection

### 7.1 TIAND radar--camera synchronization

The radar-camera synchronization file is whitespace-separated, with
fields:

``` text
camera_timestamp
closest_radar_timestamp
```

An initial parser treated the header as one combined column and produced
invalid zero-offset results. Those initial results must be discarded.

The corrected parser successfully read 2,740 rows:

  Metric                              Corrected result
  --------------------------------- ------------------
  Total rows                                     2,740
  Valid pairs                                    2,740
  Invalid pairs                                      0
  Mean offset                              0.425616 ms
  Median offset                               1.183 ms
  Standard deviation                         24.319 ms
  Minimum offset                            −64.643 ms
  Maximum offset                            +86.179 ms
  95th percentile absolute offset            42.895 ms

Offset convention:

``` text
radar offset = radar timestamp − camera timestamp
```

### 7.2 TIAND LiDAR--camera synchronization

The LiDAR-camera synchronization file is comma-separated, with fields:

``` text
lidar_timestamps
camera_timestamps
```

The corrected parser successfully read 1,840 rows:

  Metric                              Corrected result
  --------------------------------- ------------------
  Total rows                                     1,840
  Valid pairs                                    1,840
  Invalid pairs                                      0
  Mean offset                                 1.986 ms
  Median offset                              −0.868 ms
  Standard deviation                         22.311 ms
  Minimum offset                            −61.744 ms
  Maximum offset                           +103.707 ms
  95th percentile absolute offset            38.906 ms

Offset convention:

``` text
LiDAR offset = camera timestamp − LiDAR timestamp
```

These values describe differences in the supplied timestamp pairs. They
do not independently prove synchronization accuracy, sensor capture
alignment or a suitable tolerance for RaahiSense. The LiDAR-camera
timestamp file exists even though no TIAND LiDAR measurement files were
found locally.

### 7.3 Synchronization policy

No synchronization tolerance should be silently assumed from the above
summary statistics. Phase 2 must:

-   Preserve each sensor's original timestamp.
-   Store normalized timestamps separately.
-   Record the offset convention and source synchronization file.
-   Keep dataset/session boundaries intact.
-   Make any matching tolerance an explicit, configurable policy.
-   Record unmatched or out-of-tolerance observations rather than
    silently dropping them.

## 8. Calibration inspection

### 8.1 Files found

``` text
Calibration_files/Calibration_files/LIDAR/LiDAR_rotation_matrix.npy
Calibration_files/Calibration_files/LIDAR/LiDAR_translation_matrix.npy
Calibration_files/Calibration_files/RADAR/Radar_camera_Projection_matrix.npy
Calibration_files/Calibration_files/RADAR/Radar_mounting_positions.json
```

### 8.2 LiDAR rotation matrix

Observed shape: `(3, 3)`, dtype `float64`, all values finite.

``` text
[[ 0.271545  -0.9994872 -0.0169693]
 [-0.0296895  0.0161617 -0.9994285]
 [ 0.9991903  0.0276428 -0.0292354]]
```

Reported determinant: approximately `1.00663634`.

Reported orthogonality error: approximately `0.35312073645`.

The matrix is not sufficiently close to a clean orthogonal rotation
matrix to apply without further investigation. Its coordinate convention
and intended use are not confirmed.

### 8.3 LiDAR translation vector

Observed vector:

``` text
[91.6755436, -0.9723143, 88.4437449]
```

All values are finite. Units, axis order, reference frame and transform
direction are unknown.

### 8.4 Radar-camera projection matrix

Observed shape: `(3, 4)`, all values finite.

``` text
[[-24.70428698, 37.46050432, -21.82521016, -27.98080325],
 [-15.89052547,  0.63735301, -39.19509130, -50.25022366],
 [ -0.08038182,  0.00188930,  -0.59391497,   0.31224364]]
```

The coordinate convention and projection procedure are not confirmed. Do
not use this matrix for projection until its intended input frame,
output convention and units are established.

### 8.5 Radar mounting positions

The JSON contains six radar sensor entries with names, IDs and mounting
parameters.

  Sensor               ID Position (as stored)        Yaw (as stored)
  ------------------ ---- ------------------------- -----------------
  srr_back_left         0 `[-0.62, 0.725, 0.55]`               1.9183
  srr_back_right        1 `[-0.62, -0.725, 0.55]`             −1.8311
  srr_front_right       2 `[3.07, -0.718, 0.48]`              −1.2217
  srr_front_left        3 `[3.07, 0.718, 0.48]`                1.2217
  srr_back              4 `[-0.95, 0, 0.8]`                     3.141
  ars_front_center     20 `[3.1, 0, 0.4]`                           0

The front-center radar also has a stored pitch value of 0.

The coordinate axes, position units and angular units are not yet
confirmed. Preserve the source values and JSON structure. Do not apply
transforms based only on assumed conventions.

## 9. Data quality assessment

### 9.1 Checks completed

-   Recursive file inventories were generated for IDD and TIAND.
-   Image formats and dimensions were inspected.
-   IDD LiDAR NPY arrays were checked for validity, shape, dtype and
    finite values.
-   IDD split image indices were checked for validity and uniqueness.
-   IDD left/right/LiDAR index overlaps were calculated.
-   IDD LiDAR timestamp tables were checked for parse failures and
    duplicate frame identifiers.
-   IDD OBD timestamps were parsed and checked for non-increasing steps
    after rollover adjustment.
-   TIAND radar CSV readability and numeric structure were inspected.
-   TIAND GNSS columns were inspected.
-   TIAND synchronization files were parsed using their respective
    delimiters.
-   TIAND calibration file shapes, values and mounting JSON entries were
    inspected.

### 9.2 Known limitations and unresolved checks

1.  IDD LiDAR five-column semantics, units and coordinate frame remain
    unconfirmed.
2.  IDD filename/index overlap does not prove temporal synchronization.
3.  IDD test split has no LiDAR index overlap under the current mapping.
4.  IDD validation GPS schema was not separately confirmed in the
    supplied findings.
5.  IDD OBD time-of-day timestamps are not proven to share a clock with
    camera or LiDAR.
6.  TIAND LiDAR measurement files are absent from the local copy.
7.  TIAND radar column meanings and variable-length structure are not
    documented in the inspected local files.
8.  TIAND synchronization offsets do not establish an application-level
    synchronization tolerance.
9.  TIAND calibration coordinate conventions, units and transform
    directions remain unconfirmed.
10. The TIAND GNSS file's units and reference conventions require
    documentation before coordinate or orientation transformations.

## 10. Phase 1 decisions and ingestion readiness

### 10.1 Dataset roles

**IDD Multimodal --- primary development dataset**

-   Begin initial multimodal ingestion with the training split.
-   Preserve left and right camera streams separately.
-   Preserve LiDAR arrays in their original five-column form.
-   Preserve GPS and OBD availability at record level.
-   Represent missing LiDAR in validation explicitly.
-   Do not claim LiDAR-supported test evaluation using the current index
    mapping.

**TIAND --- secondary ingestion and cross-environment dataset**

-   Use camera, radar and GNSS for independent ingestion testing.
-   Preserve all six radar directions separately.
-   Mark LiDAR as unavailable in the current local copy.
-   Preserve calibration and synchronization files as source metadata.
-   Do not apply unverified calibration transforms.
-   Do not combine TIAND timestamps with IDD timestamps.

### 10.2 Common ingestion requirements

Every ingested observation should retain, where applicable:

-   `dataset_id`
-   `session_id` or sequence identifier
-   `sensor_id`
-   `sensor_type`
-   `source_file`
-   `source_record_id` or frame/index identifier
-   `original_timestamp`
-   `normalized_timestamp`
-   `timestamp_unit` and parsing convention
-   `calibration_reference`
-   `modality_available`
-   `ingestion_status`
-   `provenance` and validation flags

These are proposed ingestion requirements, not claims that the source
datasets already provide all these fields. Dataset-specific adapters
should map source fields into the common representation while preserving
original values.

### 10.3 Phase 1 completion checklist

-   [x] IDD and TIAND directory inventories generated.
-   [x] Image formats and dimensions inspected.
-   [x] IDD LiDAR array structure inspected.
-   [x] IDD OBD and timestamp files inspected.
-   [x] IDD split/index overlap calculated.
-   [x] TIAND radar and GNSS structures inspected.
-   [x] TIAND LiDAR local availability checked.
-   [x] TIAND synchronization files parsed with corrected delimiters.
-   [x] TIAND calibration file structures inspected.
-   [x] Unresolved semantics and limitations identified.
-   [ ] Final audit report reviewed and committed to project
    documentation.

## 11. Phase 1 conclusion

The local dataset inventory and structural validation provide a
sufficient basis to begin **Phase 2 Common Data Model design**. The IDD
training split is the strongest current starting point for multimodal
development because the inspected training image indices have
corresponding LiDAR indices across all three sequences.

This does not mean that all sensor semantics, calibration conventions or
clock relationships are fully understood. Those uncertainties must
remain explicit in the data model and ingestion metadata. TIAND can be
used for camera, radar and GNSS ingestion validation, but its LiDAR
modality is unavailable in the current local copy.

Phase 2 should begin with schema design and a small, reversible
ingestion prototype. Raw files must remain untouched, source timestamps
and values must be preserved, and all missing or unverified information
must be represented explicitly.

------------------------------------------------------------------------

## Appendix A --- Phase 1 scripts and generated manifests

Known inspection scripts:

``` text
scripts/inspect_tiand_structure.py
scripts/phase1_content_validation.py
scripts/phase1_dataset_audit.py
scripts/phase1_dataset_visualisations.py
scripts/phase1_remaining_validation.py
scripts/phase1_sensor_structure.py
scripts/correct_tiand_sync.py
scripts/inspect_idd_lidar_columns.py
scripts/visualize_idd_lidar.py
scripts/inspect_idd_lidar_attributes.py
scripts/inspect_idd_package_documentation.py
```

Known inventory manifests:

``` text
data/manifests/phase1/idd_primary_inventory.csv
data/manifests/phase1/idd_secondary_inventory.csv
data/manifests/phase1/idd_supplement_inventory.csv
data/manifests/phase1/tiand_inventory.csv
```

The documentation inventory was saved at:

``` text
data/generated/phase1/idd_package_documentation/idd_documentation_inventory.csv
```

## Appendix B --- Interpretation policy

The following labels should be used consistently in later implementation
and reporting:

-   **Observed:** directly inspected in local files.
-   **Derived:** calculated from observed records using a documented
    procedure.
-   **Provisional:** plausible interpretation not yet confirmed by
    authoritative documentation.
-   **Unavailable:** not present in the current local copy.
-   **Unresolved:** insufficient evidence to determine the value or
    meaning.

Do not convert provisional or unresolved properties into confirmed
metadata during ingestion.
