# RaahiSense Common Data Model (CDM)

**Document status:** Draft for technical review\
**Project phase:** Phase 2 --- Common Data Model\
**Methodology:** Real-data-first\
**Current baseline commit:** `f854ceb Dataset Audit & Report`

------------------------------------------------------------------------

## 1. Purpose

The Common Data Model (CDM) defines how RaahiSense represents
observations and derived information from heterogeneous real-world road
and vehicle data sources in a consistent, traceable structure.

The initial sources are:

-   **IDD Multimodal:** stereo camera images, LiDAR files, OBD records
    and GPS information where present in the inspected files.
-   **TIAND:** camera images, radar records and GNSS information.
-   **Physical collection (later validation):** whichever CAN/OBD, GPS,
    IMU and camera devices are actually connected and documented.

The CDM is an integration contract. It does not imply that all datasets
contain the same sensors, share a clock, or provide equivalent labels.

The primary goals are to:

1.  preserve original observations and their source references;
2.  represent different modalities with a common observation envelope;
3.  keep dataset and recording-session boundaries explicit;
4.  preserve original timestamps and distinguish them from normalized
    timestamps;
5.  record synchronization evidence rather than assume synchronization;
6.  represent missing modalities without fabricating measurements;
7.  trace every normalized or derived record back to its source;
8.  support later event detection, temporal analysis, retrieval and
    grounded explanation.

## 2. Scope and non-goals

### In scope

-   Dataset and session identity.
-   Sensor/source metadata.
-   Observation metadata and typed values or artifact references.
-   Original and normalized timestamp representation.
-   Synchronization metadata and uncertainty.
-   Data quality and missingness.
-   Provenance and transformation history.
-   Derived event and context records.
-   Dataset-specific adapters and mappings.

### Out of scope for this draft

-   Choosing a final cross-dataset synchronization tolerance.
-   Claiming that IDD and TIAND timestamps are directly comparable.
-   Assigning undocumented meanings to IDD LiDAR or TIAND radar columns.
-   Defining a universal event taxonomy beyond what the available data
    supports.
-   Replacing the existing SQLite schema before the CDM is reviewed.
-   Treating the existing synthetic scenario generator as a primary data
    source.
-   Assuming that every physical sensor will be present in every
    recording.

## 3. Core design principles

### 3.1 Preserve source data

Raw dataset files are immutable inputs. Adapters must read them and
write normalized outputs to separate locations. No adapter may
overwrite, rename, or modify the original source files.

### 3.2 Dataset and session isolation

A session belongs to one dataset or one physical collection
campaign/source namespace. IDD sequences and TIAND sessions remain
separate. Similar frame numbers or timestamps do not make two sessions
the same recording.

### 3.3 Missing modalities are valid

A session may contain camera data but no LiDAR, radar, OBD or GNSS. The
CDM records what is available. It must not create placeholder
measurements or synthetic sensor values to make sessions look complete.

### 3.4 Unknown metadata remains unknown

Unknown units, coordinate frames, sensor orientation, calibration,
timestamp reference, radar fields and LiDAR fields must be represented
as unknown or unverified. Do not infer them from column position or
plausible numeric ranges alone.

### 3.5 Time is evidence, not an assumption

Store the source timestamp exactly as observed, together with its unit
and documented clock/reference. A normalized timestamp is a separate
derived field. A normalized timestamp does not prove that two sensors
are synchronized.

### 3.6 Derived data is distinguishable

Every derived observation, event or context must record the
method/version and its input provenance. Source measurements and
model/rule outputs must not be indistinguishable.

### 3.7 Real-data-first

The primary ingestion and evaluation path uses IDD, TIAND and later
documented physical recordings. Synthetic scenario generation is not a
required source in the primary pipeline. Controlled perturbations of
copies of real recordings may be used in robustness experiments and must
be labelled as experimental transformations.

## 4. Conceptual model

The CDM has the following logical entities:

  ------------------------------------------------------------------------
  Entity                  Meaning                  Example
  ----------------------- ------------------------ -----------------------
  Dataset                 A named source           IDD Multimodal
                          collection and version   

  Session                 A recording sequence     IDD `d0` sequence
                          within a dataset         

  Sensor/source           A physical or logical    Left camera, OBD
                          producer of data         logger, radar

  Observation             One measurement, frame,  OBD speed sample
                          detection or record      

  Artifact                A file or binary payload JPG, NPY, video clip
                          referenced by an         
                          observation              

  Synchronization record  Evidence about clock     Documented offset
                          relationship/alignment   estimate

  Event                   A time-bounded or        Pedestrian detected
                          instantaneous            
                          interpreted occurrence   

  Context                 A state or condition     Traffic context
                          valid over an interval   

  Transformation          A versioned processing   Timestamp normalization
                          operation                
  ------------------------------------------------------------------------

Logical relationships:

-   One dataset contains one or more sessions.
-   One session may contain zero or more sensors/sources.
-   One sensor/source may produce zero or more observations in a
    session.
-   An observation belongs to one session and has a source reference.
-   An observation may reference a file artifact or contain a
    scalar/structured value.
-   Events and contexts belong to a session and reference supporting
    observations where available.
-   Transformations record how source records become normalized
    observations, events or contexts.
-   Synchronization records apply only to the specific sessions/sources
    and evidence used to establish them.

## 5. Entity definitions

### 5.1 Dataset

A dataset record identifies the source collection independently of any
individual recording.

Recommended fields:

  -----------------------------------------------------------------------------
  Field                Type                          Required Description
  -------------------- ---------------- --------------------- -----------------
  `dataset_id`         string                             Yes Stable internal
                                                              identifier

  `dataset_name`       string                             Yes Human-readable
                                                              collection name

  `dataset_version`    string/null                         No Published or
                                                              locally recorded
                                                              version

  `source_uri`         string/null                         No Source location
                                                              or citation

  `license_or_terms`   string/null                         No Usage
                                                              restrictions, if
                                                              known

  `description`        string/null                         No Dataset
                                                              description

  `metadata_json`      object                              No Additional
                                                              source-specific
                                                              metadata
  -----------------------------------------------------------------------------

Do not place credentials or private access tokens in dataset metadata.

### 5.2 Session

A session identifies one recording sequence or collection run. Session
identity is scoped to its dataset/source.

Recommended fields:

  ----------------------------------------------------------------------------------------------
  Field                      Type                              Required Description
  -------------------------- -------------------- --------------------- ------------------------
  `session_id`               string                                 Yes Stable internal
                                                                        identifier

  `dataset_id`               string                     Yes for dataset Parent dataset
                                                               sessions 

  `source_session_id`        string/null                             No Original
                                                                        sequence/session
                                                                        identifier

  `session_name`             string/null                             No Human-readable label

  `start_source_timestamp`   string/number/null                      No Original start time,
                                                                        unchanged

  `end_source_timestamp`     string/number/null                      No Original end time,
                                                                        unchanged

  `timestamp_unit`           string/null                             No Unit of source
                                                                        timestamps

  `timestamp_reference`      string/null                             No Clock/epoch/reference,
                                                                        only if documented

  `available_modalities`     array                                  Yes Modalities actually
                                                                        present

  `source_files_manifest`    array/reference                        Yes Files belonging to the
                                                                        session

  `data_origin`              enum                                   Yes `real_dataset` or
                                                                        `physical` for the
                                                                        primary path

  `metadata_json`            object                                  No Dataset-specific details
  ----------------------------------------------------------------------------------------------

A session's start/end time must not be invented from file ordering. If
timestamps are absent or their reference is unknown, leave the
corresponding normalized field unset and record the limitation.

### 5.3 Sensor/source

The sensor entity describes the producer of observations. A source may
be a physical sensor, an ECU/logger, or a dataset-provided logical
stream.

Recommended fields:

  --------------------------------------------------------------------------------------------
  Field                       Type                          Required Description
  --------------------------- ---------------- --------------------- -------------------------
  `sensor_id`                 string                             Yes Stable identifier within
                                                                     the session/source
                                                                     namespace

  `session_id`                string                             Yes Session in which this
                                                                     source is present

  `modality`                  string                             Yes Camera, LiDAR, radar,
                                                                     OBD, GPS/GNSS, IMU, etc.

  `sensor_name`               string/null                         No Source-provided name

  `sensor_type`               string/null                         No Exact type/model, if
                                                                     known

  `source_stream_name`        string/null                         No Original
                                                                     stream/file/column group

  `position`                  object/null                         No Position only if
                                                                     documented

  `orientation`               object/null                         No Direction only if
                                                                     documented

  `coordinate_frame`          string/null                         No Frame convention, if
                                                                     documented

  `calibration_reference`     string/null                         No Calibration
                                                                     file/reference, if
                                                                     available

  `configuration_reference`   string/null                         No Original configuration
                                                                     reference

  `metadata_status`           enum                               Yes `documented`,
                                                                     `partially_documented`,
                                                                     `unknown`
  --------------------------------------------------------------------------------------------

`source_type` or modality is not a unique sensor identity. If a session
contains multiple cameras, each camera needs its own sensor/source
record.

### 5.4 Observation

An observation is the central CDM record. It represents one source
measurement, frame, detection, packet-derived value or structured
record.

Recommended fields:

  ---------------------------------------------------------------------------------------------
  Field                       Type                               Required Description
  --------------------------- --------------------- --------------------- ---------------------
  `observation_id`            string                                  Yes Unique internal ID

  `dataset_id`                string/null                     Conditional Dataset for
                                                                          dataset-backed
                                                                          records

  `session_id`                string                                  Yes Owning session

  `sensor_id`                 string/null                     Conditional Source sensor/stream,
                                                                          if identified

  `modality`                  string                                  Yes Camera, LiDAR, radar,
                                                                          OBD, GNSS, IMU, etc.

  `observation_type`          string                                  Yes Measurement, frame,
                                                                          point cloud,
                                                                          detection, record,
                                                                          etc.

  `source_timestamp_raw`      string/number/null                       No Exact original
                                                                          timestamp value

  `source_timestamp_unit`     string/null                              No Unit exactly as
                                                                          documented or
                                                                          observed

  `source_clock_reference`    string/null                              No Epoch, device clock
                                                                          or relative clock, if
                                                                          known

  `timestamp_normalized`      integer/null                             No Normalized time in
                                                                          the project time
                                                                          representation

  `normalized_time_unit`      string/null                     Conditional For example,
                                                                          milliseconds

  `normalization_method`      string/null                              No Method/version used
                                                                          to derive normalized
                                                                          time

  `sequence_index`            integer/string/null                      No Original frame/record
                                                                          index

  `value_type`                string/null                              No Numeric, integer,
                                                                          boolean, text,
                                                                          structured, artifact
                                                                          reference

  `value`                     scalar/object/null              Conditional Decoded value when
                                                                          suitable

  `unit`                      string/null                              No Unit only when known

  `artifact_uri`              string/null                     Conditional Reference to
                                                                          image/NPY/video/raw
                                                                          file

  `quality_status`            string                                  Yes Validity/quality
                                                                          state

  `quality_score`             number/null                              No Score only when a
                                                                          defined method exists

  `data_origin`               enum                                    Yes `real_dataset`,
                                                                          `physical`, or
                                                                          `derived`

  `source_file`               string                                  Yes Original relative
                                                                          file path or stable
                                                                          file ID

  `source_record_reference`   string/null                              No Row, frame, array
                                                                          index, packet or
                                                                          record reference

  `transformation_id`         string/null                              No Processing operation
                                                                          that created this
                                                                          representation

  `metadata_json`             object                                   No Source-specific
                                                                          fields not yet
                                                                          standardized
  ---------------------------------------------------------------------------------------------

For large binary data, store an artifact reference and metadata rather
than copying the entire image or point cloud into a relational row.
Preserve the original file path/reference and, where practical, a
checksum.

#### Value representation

Use typed values where the schema can identify the type safely. Do not
coerce unknown arrays or records into numeric columns. For a multimodal
record, the observation may primarily point to an artifact.

The CDM must support both:

-   **Scalar observations:** e.g. a documented OBD speed value.
-   **Artifact observations:** e.g. an image or LiDAR array whose
    payload remains in a file.

### 5.5 Event

An event is an interpreted occurrence derived from one or more
observations or supplied by an authoritative annotation source.

Recommended fields:

  -----------------------------------------------------------------------------------------------
  Field                           Type                           Required Description
  ------------------------------- ----------------- --------------------- -----------------------
  `event_id`                      string                              Yes Unique event ID

  `session_id`                    string                              Yes Owning session

  `event_type`                    string                              Yes Event label

  `event_category`                string/null                          No Category

  `start_time_normalized`         integer/null                         No Start time in
                                                                          normalized project
                                                                          units

  `end_time_normalized`           integer/null                         No End time, if interval
                                                                          event

  `time_unit`                     string/null                 Conditional Unit of event times

  `confidence`                    number/null                          No Confidence from a
                                                                          documented method

  `severity`                      string/null                          No Only where defined

  `event_origin`                  enum                                Yes `dataset_annotation`,
                                                                          `rule_detection`,
                                                                          `model_detection`,
                                                                          `manual_annotation`

  `method_name`                   string/null                          No Rule/model/annotation
                                                                          method

  `method_version`                string/null                          No Version

  `supporting_observation_ids`    array/reference                      No Evidence used

  `source_annotation_reference`   string/null                          No Original
                                                                          label/annotation
                                                                          location

  `is_ground_truth`               boolean                             Yes Whether this is a
                                                                          reference label

  `metadata_json`                 object                               No Additional details
  -----------------------------------------------------------------------------------------------

An event without a defensible time must not be assigned an invented
timestamp. A point event may have the same start and end time if the
event semantics and source support that representation; otherwise
represent its time as an instant explicitly.

Ground-truth annotations and system-detected events must remain
distinguishable. Evaluation labels must not be exposed to the retrieval
or explanation component when that would cause label leakage.

### 5.6 Context

A context represents a condition or state that applies over a time
interval or at a point in time.

Examples may include road type, lighting, traffic level, driving state
or road-user activity, but only when supported by the dataset or a
defined inference method.

Recommended fields:

-   `context_id`
-   `session_id`
-   `context_type`
-   `context_label`
-   `start_time_normalized`
-   `end_time_normalized`
-   `time_unit`
-   `confidence`
-   `source_type`
-   `method_name`
-   `method_version`
-   `supporting_observation_ids`
-   `metadata_json`

Keep directly supplied annotations separate from inferred contexts. For
example, a pedestrian detection is evidence of a pedestrian in the
scene; it does not by itself prove that the pedestrian crossed the
vehicle's path or caused braking.

### 5.7 Synchronization record

Synchronization is represented separately from ordinary observation data
because clock relationships are properties of sources and sessions, not
just individual measurements.

Recommended fields:

-   `sync_id`
-   `session_id`
-   `source_a_id`
-   `source_b_id`
-   `clock_reference_a`
-   `clock_reference_b`
-   `method`
-   `estimated_offset`
-   `estimated_drift`
-   `uncertainty`
-   `time_unit`
-   `valid_from`
-   `valid_to`
-   `evidence_reference`
-   `status` (`unverified`, `estimated`, `validated`, `rejected`)
-   `method_version`
-   `metadata_json`

Do not create a validated synchronization record merely because two
files have matching frame indices or similar timestamp values. Record
the method and evidence used. If the relationship is unknown, leave it
unknown.

## 6. Timestamp and temporal policy

### 6.1 Preserve three distinct notions of time

The implementation should distinguish:

1.  **Source/measurement time:** the timestamp as supplied by the
    source.
2.  **Normalized event time:** a derived representation used for
    indexing and temporal operations.
3.  **Ingestion/arrival time:** when RaahiSense actually received or
    processed the record.

These fields must not be substituted for one another.

### 6.2 Timestamp fields

For every timestamped source, preserve:

-   raw timestamp value;
-   original unit;
-   source clock/reference;
-   timezone or epoch only when known;
-   normalized timestamp, if a documented conversion is possible;
-   normalization method/version;
-   ingestion time, when collected by the pipeline.

The existing database uses millisecond timestamp columns. This is an
implementation convention, not proof that every source timestamp is Unix
epoch milliseconds. Store the original source representation and
conversion metadata alongside any millisecond value.

### 6.3 No premature synchronization tolerance

Do not define a universal matching tolerance in this document. First
inspect each dataset's timestamp fields, frame rates, clock references
and available documentation. Then choose and evaluate a tolerance for a
specific source pair and task.

### 6.4 Frame indices

Frame indices are useful provenance and candidate matching keys. They
are not timestamps and do not prove synchronization between different
modalities.

## 7. Initial dataset mapping

This section records only what was established in the Phase 1 audit. It
is not a complete field-level adapter specification.

### 7.1 IDD Multimodal

Audited structure:

-   Local source root: `data/raw/idd_multimodal/`
-   Subdirectories: `primary`, `secondary`, `supplement`
-   Three inspected sequences: `d0`, `d1`, `d2`
-   Stereo camera: 13,543 left images and 13,543 right images, each
    inspected as 1920×1080
-   LiDAR: 8,948 NPY files
-   OBD: three CSV files, one per sequence
-   GPS information was present in inspected training CSV files

Known OBD fields:

-   `timestamp`
-   `speed`
-   `rpm`
-   `gear`
-   `clv`
-   `throttle_position`

Mapping rules:

-   Keep each IDD sequence as its own session.
-   Represent left and right camera streams as distinct sensor/source
    identities when the source structure supports it.
-   Represent each LiDAR file as an artifact observation, preserving the
    original file and array reference.
-   Preserve OBD column names and raw values in the source layer. Map to
    canonical signal names only after confirming units and semantics.
-   Record GPS fields only for files/splits where they are actually
    present.
-   Do not assume all train/validation/test partitions have the same
    modality availability.
-   Do not treat the observed camera/LiDAR frame-index overlap as proof
    of synchronization.

LiDAR uncertainty:

The inspected NPY arrays have five columns. The audit noted that some
columns appear numerically consistent with spatial coordinates, a
channel/ring identifier and an intensity-like value. These
interpretations are hypotheses only. Until authoritative dataset
documentation confirms the schema, preserve the five columns as unnamed
source fields (for example, `column_0` through `column_4`) and record
their shape and dtype. Do not assign physical meanings or units.

### 7.2 TIAND

Audited modalities:

-   Camera images
-   Radar directional CSV records
-   GNSS position, velocity and orientation information

Mapping rules:

-   Keep each TIAND recording/session separate from IDD sessions.
-   Preserve radar CSV column names and values without assigning
    meanings until authoritative metadata is available.
-   Preserve GNSS field names, units and reference conventions as
    provided by the dataset documentation/files.
-   Do not infer radar-camera-GNSS synchronization from row order or
    matching indices alone.
-   Record modality availability at session level.

### 7.3 Physical data

Physical data will be added after the relevant devices and collection
configuration are known. Each device needs a sensor/source record,
documented timestamp source, units, configuration and calibration
details where available.

Do not make the physical collection schema depend on hardware that has
not been selected or connected.

## 8. Mapping to the current SQLite implementation

The current `database/schema.sql` contains six main tables:

-   `sessions`
-   `signals`
-   `observations`
-   `events`
-   `contexts`
-   `event_relationships`

This is a useful starting implementation for the existing
synthetic/temporal prototype. It is not yet a complete implementation of
the real-data CDM.

  -----------------------------------------------------------------------
  Current table           CDM role                Review point
  ----------------------- ----------------------- -----------------------
  `sessions`              Session                 Add/clarify dataset
                                                  identity and
                                                  source-session identity

  `signals`               Signal vocabulary       Keep canonical
                                                  definitions separate
                                                  from per-session sensor
                                                  instances

  `observations`          Observation             Preserve raw timestamp
                                                  unit/reference and
                                                  artifact/source record
                                                  provenance

  `events`                Event                   Distinguish dataset
                                                  annotations from
                                                  detected events and
                                                  link multiple
                                                  supporting observations

  `contexts`              Context                 Preserve source/method
                                                  and supporting evidence

  `event_relationships`   Event relationships     Keep temporal
                                                  association separate
                                                  from causality
  -----------------------------------------------------------------------

Existing observation fields include `timestamp_ms`,
`source_timestamp_ms` and `ingested_at_ms`. Their semantics must be
clarified before relying on them for real datasets. In particular,
`source_timestamp_ms` must not silently assume that every source
timestamp is already milliseconds or shares a Unix epoch.

The current schema also has `source_reference` and `metadata_json`,
which may help retain source-specific references during the first
adapter iteration. A structured sensor table and synchronization
metadata may be needed after the CDM review.

**No database migration is authorized by this draft.** Review the design
and inspect actual adapter requirements first.

## 9. Signal dictionary policy

`config/signal_dictionary.json` is a canonical signal vocabulary, not a
complete sensor inventory or CDM.

Keep it as a reusable vocabulary, but do not assume every listed signal
exists in IDD, TIAND or every physical session.

Before mapping a source field to a canonical signal, verify:

-   semantic meaning;
-   unit and scale;
-   sign convention;
-   coordinate/reference convention where relevant;
-   sampling frequency or timestamp semantics;
-   whether the field is measured, annotated or derived.

The current dictionary marks some signals as required and some as
derived. The meaning and scope of `is_required` must be clarified. A
signal being part of the canonical vocabulary must not make it mandatory
in every dataset/session. Likewise, a source type such as `CARLA`, `CAN`
or `GPS` must not be mistaken for a unique sensor identity.

## 10. Missing data and quality representation

Missingness must be explicit and must not be represented as a fabricated
zero.

Distinguish at least:

-   `not_present`: modality or field is not provided by this
    session/source;
-   `not_recorded`: expected source field was not recorded;
-   `missing_value`: record exists but value is missing;
-   `invalid`: value is present but fails a defined validation rule;
-   `unverified`: meaning/unit/reference is not established;
-   `unavailable_artifact`: referenced source artifact cannot be
    accessed;
-   `valid`: value passed the applicable checks.

These are proposed CDM statuses. They must be mapped carefully to the
existing database's `quality` enum before implementation.

A missing modality is generally a session/source availability fact, not
a repeated synthetic observation at every timestamp. Use a session
modality inventory or source availability record. Use observation-level
missing status only when a source record exists and the value itself is
missing or invalid.

Quality scores must be omitted unless a reproducible scoring method is
defined. Do not use confidence to disguise unknown metadata.

## 11. Provenance and reproducibility

Every normalized or derived record should be traceable to:

-   dataset and session;
-   original relative file path or stable file identifier;
-   original row/frame/array/packet index where available;
-   source sensor/stream;
-   source timestamp and unit;
-   adapter name and version;
-   transformation name and version;
-   configuration version;
-   creation/ingestion time;
-   checksum where practical for immutable artifacts.

For derived observations, record input observation IDs or a source-range
reference. For events, record the observations or annotation references
supporting the event. Keep the original source files unchanged.

## 12. Event and context policy for real data

The current `config/event_rules.yaml` defines six rule-based event
types: sharp braking, pedestrian detected, vehicle detected, collision
warning, lane departure warning and emergency braking.

These rules are not automatically applicable to IDD or TIAND. Before
enabling a rule for a dataset, verify that its required signal or
annotation exists and that its semantics match the rule.

Examples:

-   `SHARP_BRAKING` requires a valid longitudinal acceleration signal
    with a known unit and sign convention. Do not substitute a different
    signal without documenting the conversion.
-   `PEDESTRIAN_DETECTED` requires an authoritative annotation or a
    validated detector output. A camera frame alone is not a pedestrian
    label.
-   `COLLISION_WARNING`, `LANE_DEPARTURE_WARNING` and
    `EMERGENCY_BRAKING` require corresponding source signals/annotations
    or a separately validated detection method. Do not infer that these
    events exist merely because a pedestrian or vehicle is visible.
-   `VEHICLE_DETECTED` requires an annotation or validated detection
    output.

The existing sharp-braking severity configuration also needs review: its
`low` severity condition (`acceleration > -4.0 m/s²`) is outside the
event's detection threshold (`acceleration <= -4.0 m/s²`). Resolve this
before using severity metrics.

Temporal relationships such as `PRECEDES`, `OVERLAPS` and
`WITHIN_WINDOW` describe time relationships. They do not establish
causation. The system must not generate causal explanations unless a
separate causal method and evidence justify them.

## 13. Evaluation and data leakage controls

-   Split evaluation by independent session, sequence or other
    defensible recording unit, not by randomly distributing adjacent
    frames across train and test.
-   Keep ground-truth labels separate from model/rule predictions.
-   Do not expose held-out labels to retrieval, ranking or SLM
    prompting.
-   Report which sessions, modalities and labels are actually available
    for each metric.
-   Report abstention when required evidence is missing or insufficient.
-   Do not report precision, recall or F1 for an event class without
    defensible reference labels.
-   Evaluate temporal alignment only where a synchronization reference
    or defensible evaluation method exists.
-   Keep results from IDD and TIAND separate unless a justified
    cross-dataset evaluation protocol is defined.

For robustness experiments, perturb copies of real recordings only.
Record the perturbation type, magnitude, random seed if applicable, and
transformation version. Clearly distinguish these experiments from
untouched real-world observations.

## 14. Proposed directory organization

The following is a proposed logical organization; it does not require
moving the existing raw dataset.

``` text
data/
  raw/
    idd_multimodal/          # existing source files; read-only
    tiand/                   # source files; read-only
    physical/                # later, documented recordings
  manifests/
    datasets/
    sessions/
    sensors/
  interim/
    idd/
    tiand/
  processed/
    observations/
    events/
    contexts/
  artifacts/
    frames/
    pointclouds/
    clips/
  evaluation/
    annotations/
    splits/
    reports/
```

The adapter output location and file formats will be finalized during
Phase 3. Do not create empty directories merely to match this proposal.

## 15. Decisions required before database changes

  -----------------------------------------------------------------------
  Decision                Current status          Required
                                                  evidence/action
  ----------------------- ----------------------- -----------------------
  Dataset/session         Proposed                Define stable naming
  identifiers                                     rules

  Sensor identity         Proposed                Inspect source
  granularity                                     folder/stream structure

  Raw timestamp           Incomplete              Inspect dataset
  unit/reference per                              metadata and actual
  stream                                          records

  Normalized timestamp    Proposed milliseconds   Confirm conversion and
  convention              internally              clock semantics per
                                                  source

  Cross-sensor            Unverified              Find authoritative sync
  synchronization                                 metadata or define an
                                                  evaluation method

  IDD LiDAR column        Unverified              Obtain authoritative
  meanings                                        dataset documentation

  TIAND radar column      Unverified              Obtain authoritative
  meanings                                        dataset documentation

  Canonical signal        Incomplete              Validate field
  mapping                                         semantics and units

  Event labels per        Incomplete              Audit available
  dataset                                         annotations

  Sensor table and sync   Proposed                Confirm adapter
  table                                           requirements

  Quality status mapping  Proposed                Reconcile with current
                                                  SQLite enum
  -----------------------------------------------------------------------

## 16. Phase 2 acceptance criteria

The CDM design can be approved when:

1.  Dataset, session, sensor, observation, event, context and provenance
    entities are clearly defined.
2.  Original and normalized timestamps are distinct.
3.  Clock reference and synchronization uncertainty can be represented.
4.  Missing modalities do not require fabricated observations.
5.  Unknown sensor/field semantics can be retained without guessing.
6.  IDD and TIAND sessions remain isolated.
7.  Dataset annotations and detected events remain distinguishable.
8.  The mapping to the current SQLite schema and its gaps are
    documented.
9.  No database migration is performed before review.

## 17. Immediate next steps

1.  Review this document and confirm the conceptual entities and
    timestamp policy.
2.  Inspect actual IDD and TIAND metadata and representative records to
    complete field-level mappings.
3.  Decide which fields in the current SQLite schema can be reused and
    which need extension.
4.  Update the CDM document with evidence-backed mappings.
5.  Only then prepare a database migration plan and adapter
    implementation.

**Current status:** This document is a design draft based on the Phase 1
audit and the inspected repository configuration/schema.
Dataset-specific timestamp semantics, LiDAR/radar field meanings, exact
synchronization and annotation coverage remain to be verified.

---

# CDM Revision 2 — Full Perception and Motion Representation

**Revision status:** Proposed update for technical review  
**Approved scope decisions:** Full perception; trajectory prediction later  
**Database implementation status:** No SQL written; no migration applied

## 18. Revised scope

The CDM now explicitly supports the following core processing outputs:

1. Frame-level object detections.
2. Multi-object tracking outputs, with tracker-run-specific identities.
3. Time-indexed track states for observed and estimated motion.
4. Derived motion features over defined intervals.
5. Interactions between tracked road users.
6. Evidence links from estimated states and interactions to source observations.
7. Multimodal associations where the available data and calibration/synchronization evidence support them.

Trajectory prediction is **not part of the initial core implementation**. The CDM reserves a later extension for prediction runs and predicted future trajectory points. Do not create prediction records from observed trajectories or label estimates as predictions.

## 19. Revised conceptual entities

The original entities remain. Add these perception and motion entities:

| Entity | Meaning | Example |
|---|---|---|
| Detection | One model- or annotation-produced object instance in one source frame/observation | A pedestrian bounding box in a camera frame |
| Tracking run | One execution/configuration of a tracking method over a defined input sequence | ByteTrack run on a front-camera sequence |
| Track | A persistent object identity within one tracking run and session | Local track ID 42 |
| Track-detection association | Assignment of a detection to a track by a particular tracking run | Detection 812 assigned to track 42 |
| Track state | A time-indexed state estimate for a track | Image position or world position at a time |
| Motion feature | A derived movement descriptor over a point or interval | Estimated speed or heading change |
| Track interaction | A measured or inferred relationship between two tracks | Relative distance or time-to-collision estimate |
| Track-state evidence | Links a track state to the observations that support it | Camera detection and radar record |

A track ID is not globally meaningful. It is scoped to a session and a tracking run. Two tracking algorithms may assign different identities to the same detections. The schema must preserve those independent results.

## 20. Detection entity

Recommended logical fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `detection_id` | string | Yes | Stable internal identifier |
| `session_id` | string | Yes | Owning session |
| `observation_id` | string | Yes | Source frame/observation that produced the detection |
| `transformation_id` | string | Yes | Detector execution/version |
| `class_label` | string | Yes | Model or annotation class |
| `class_id` | integer/null | No | Source/model class index |
| `confidence` | number/null | No | Detector confidence, with documented meaning |
| `bbox_x_min` | number/null | Conditional | Bounding-box coordinate |
| `bbox_y_min` | number/null | Conditional | Bounding-box coordinate |
| `bbox_x_max` | number/null | Conditional | Bounding-box coordinate |
| `bbox_y_max` | number/null | Conditional | Bounding-box coordinate |
| `bbox_coordinate_space` | string | Yes when bbox exists | For example `image_pixel` |
| `image_width` | integer/null | No | Frame width used to interpret coordinates |
| `image_height` | integer/null | No | Frame height used to interpret coordinates |
| `mask_artifact_id` | string/null | No | Optional segmentation mask artifact |
| `source_annotation_reference` | string/null | No | Original dataset annotation reference |
| `is_ground_truth` | boolean | Yes | Annotation versus model output |
| `metadata_json` | object/null | No | Model-specific attributes |

Rules:

- A detection belongs to exactly one source observation/frame.
- Bounding-box coordinate space and image dimensions must be explicit.
- Do not put world coordinates into image-space bounding-box fields.
- Keep source annotations and model-generated detections distinguishable.
- Do not assume every dataset provides detection labels.
- A detector confidence is not a calibrated probability unless calibration has been evaluated.

## 21. Tracking run and track entities

A tracking run is represented by the existing `transformations` entity, provided its record identifies the tracking operation, model/algorithm, version, configuration, input scope and completion status. A separate `tracking_runs` table is not required initially if `transformations` can enforce these semantics.

Recommended `tracks` fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `track_id` | string | Yes | Stable internal track identifier |
| `session_id` | string | Yes | Owning session |
| `sensor_id` | string/null | No | Primary stream/sensor tracked |
| `transformation_id` | string | Yes | Tracking run that created this track |
| `local_track_id` | string | Yes | Tracker's own ID within the run |
| `class_label` | string/null | No | Track class, with source/method |
| `first_observed_timestamp_raw` | string/number/null | No | Original first observation time |
| `last_observed_timestamp_raw` | string/number/null | No | Original last observation time |
| `first_timestamp_normalized` | integer/null | No | Normalized first time |
| `last_timestamp_normalized` | integer/null | No | Normalized last time |
| `track_status` | string | Yes | For example active, lost, terminated, uncertain |
| `metadata_json` | object/null | No | Tracker-specific attributes |

Required uniqueness: `(transformation_id, local_track_id)`. The transformation itself must be scoped to the relevant session/input sequence. A track must not combine detections from unrelated sessions.

## 22. Track-detection association

Use a separate `track_detections` relationship rather than storing one permanent `track_id` on `detections`.

Recommended fields:

- `track_detection_id`
- `track_id`
- `detection_id`
- `association_timestamp_raw`
- `association_timestamp_normalized`
- `association_confidence` (nullable; only if produced by the tracker)
- `association_method`
- `association_role` or status, if needed
- `metadata_json`

Constraints:

- A track and its detection must belong to the same session.
- The track's tracking transformation must be the run that produced the association.
- A detection may be associated differently by different tracking runs.
- Within one tracking run, enforce the intended cardinality and prevent duplicate assignments unless the selected tracking method explicitly supports them.
- Do not treat a missing association as a zero or as proof that the object disappeared.

## 23. Track state entity

A track state is a time-indexed representation of an object's observed or estimated state. It is not automatically a ground-truth position.

Recommended fields:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `track_state_id` | string | Yes | Stable identifier |
| `track_id` | string | Yes | Track being described |
| `observation_id` | string/null | No | Direct source observation, when applicable |
| `transformation_id` | string | Yes | State-estimation execution |
| `source_timestamp_raw` | string/number/null | No | Original timestamp |
| `source_timestamp_unit` | string/null | No | Original unit |
| `timestamp_normalized` | integer/null | No | Normalized timestamp |
| `state_representation` | string | Yes | For example image-space, camera-space, vehicle-space, world-space |
| `coordinate_frame` | string/null | No | Exact frame convention, if known |
| `position_x`, `position_y`, `position_z` | number/null | No | Position components |
| `position_unit` | string/null | No | Unit for position |
| `velocity_x`, `velocity_y`, `velocity_z` | number/null | No | Velocity components |
| `speed` | number/null | No | Speed, with explicit unit |
| `acceleration_x`, `acceleration_y`, `acceleration_z` | number/null | No | Acceleration components |
| `heading` | number/null | No | Heading with documented reference and unit |
| `state_source` | string | Yes | Measured, estimated, filtered, fused, annotated |
| `confidence` | number/null | No | Only where method defines it |
| `uncertainty_json` | object/null | No | Covariance or other uncertainty representation |
| `metadata_json` | object/null | No | Additional state fields |

Rules:

- Position, velocity and acceleration require explicit units and coordinate frame.
- Image-space location, camera-space 3D location and world-space location are different representations.
- Do not calculate metric speed from image displacement without a valid scale/depth/geometry method.
- Keep raw observations separate from filtered or estimated states.
- Preserve uncertainty when the method provides it.
- A nullable normalized timestamp is valid when source-clock conversion is not defensible.

## 24. Motion features

`track_motion_features` stores derived descriptors over a point or interval. Recommended fields:

- `motion_feature_id`
- `track_id`
- `transformation_id`
- `start_track_state_id` / `end_track_state_id` (nullable as appropriate)
- `start_timestamp_normalized` / `end_timestamp_normalized`
- `feature_name`
- `feature_value`
- `feature_unit`
- `feature_method`
- `feature_version`
- `confidence` or uncertainty reference, if defined
- `metadata_json`

Examples include mean/maximum speed, longitudinal/lateral acceleration, heading change, direction stability and stop/move state. These are examples, not mandatory canonical features. Do not store a feature without documenting its calculation, units and applicable coordinate frame.

## 25. Track interactions

`track_interactions` represents relationships between two or more tracks over a point or interval.

Recommended fields:

- `track_interaction_id`
- `session_id`
- `transformation_id`
- `track_a_id`
- `track_b_id`
- `interaction_type`
- `start_timestamp_normalized`
- `end_timestamp_normalized`
- `relative_distance`
- `relative_speed`
- `time_to_collision_estimate`
- `coordinate_frame`
- `method_name`
- `method_version`
- `confidence`
- `uncertainty_json`
- `metadata_json`

The first implementation may restrict an interaction to a pair of tracks. If multi-agent interactions are later required, introduce a participant junction table rather than encoding arbitrary track IDs in JSON.

Interaction labels must distinguish directly measured quantities from model-derived interpretations. A proximity event is not automatically a collision risk, and a time-to-collision estimate is not a verified collision.

## 26. Track-state evidence and multimodal fusion

Add `track_state_evidence` to connect an estimated/fused track state to its supporting observations.

Recommended fields:

- `track_state_evidence_id`
- `track_state_id`
- `observation_id`
- `evidence_role` (for example primary, corroborating, calibration, rejected)
- `association_method`
- `association_confidence`
- `time_difference_ms` (only when normalized clocks permit calculation)
- `spatial_residual` and unit (only when the method calculates it)
- `metadata_json`

This relationship supports one-to-many evidence and avoids pretending that a fused state came from only one sensor. Store synchronization and calibration references through their own entities. A state may be camera-only, radar-only or fused; record which case applies.

For the first implementation, sensor fusion should be conservative:
- associate only sources with a documented or evaluated correspondence method;
- preserve unmatched observations;
- record the method and uncertainty;
- do not require LiDAR where local LiDAR measurements are absent;
- do not infer world coordinates from unverified calibration.

## 27. Revised entity relationships

- `sessions` 1:M `detections`, `tracks`, `track_states`, `track_motion_features` and `track_interactions`.
- `observations` 1:M `detections` because one frame may contain multiple objects.
- `transformations` 1:M `detections`; one detector run produces many detections.
- `transformations` 1:M `tracks`; one tracking run produces many tracks.
- `tracks` M:N `detections` through `track_detections`, with associations scoped to a tracking transformation.
- `tracks` 1:M `track_states`.
- `tracks` 1:M `track_motion_features`.
- `track_interactions` references two tracks in the same session.
- `track_states` M:N `observations` through `track_state_evidence`.
- Existing event/context evidence links remain. Events may additionally reference track interactions or track states through a future explicit evidence relationship if the use cases require it. Do not overload `event_observations` with track IDs.

## 28. Later trajectory-prediction extension

Do not implement prediction tables in the initial core migration. When prediction is approved, add:

### `trajectory_prediction_runs`
One record per prediction execution/model configuration, linked to a transformation and the input track/history window.

### `trajectory_prediction_points`
One row per predicted future point, linked to a prediction run and track, containing:
- prediction origin time;
- future horizon/time offset;
- predicted position and coordinate frame;
- units;
- uncertainty representation;
- model/version provenance.

This supports multiple horizons and uncertainty-aware evaluation. Do not store a whole future path only as an opaque JSON blob if point-level metrics and comparisons are required.

## 29. Revised initial logical table inventory

The core logical design is now 24 tables:

1. `datasets`
2. `sessions`
3. `sensors`
4. `session_modalities`
5. `signals`
6. `artifacts`
7. `observations`
8. `observation_artifacts`
9. `synchronization_records`
10. `synchronization_pairs`
11. `transformations`
12. `transformation_inputs`
13. `detections`
14. `tracks`
15. `track_detections`
16. `track_states`
17. `track_motion_features`
18. `track_interactions`
19. `events`
20. `contexts`
21. `event_observations`
22. `context_observations`
23. `event_relationships`
24. `track_state_evidence`

Later-only tables:
25. `trajectory_prediction_runs`
26. `trajectory_prediction_points`

The inventory is logical. During physical design, some relationships may require composite keys, junction tables or triggers to enforce same-session and same-transformation integrity.

## 30. Revised implementation order

1. Approve the revised CDM entities and field semantics.
2. Confirm which IDD/TIAND camera annotations and tracking labels actually exist.
3. Verify camera calibration and coordinate-frame metadata before defining metric state fields.
4. Define the first detector output contract and detection evaluation split.
5. Define tracking-run identity and association rules.
6. Define track-state coordinate representations and motion-feature calculations.
7. Review the physical schema and integrity constraints.
8. Only after approval, write a versioned SQLite migration.
9. Build adapters and model-output writers against the approved schema.

**Important:** this revision extends the existing CDM draft. It does not claim that IDD or TIAND already supplies every required annotation, calibration or ground-truth trajectory. Those capabilities must be verified from source documentation and files before model evaluation.
