# RaahiSense Physical Database Specification
## Revision 2 — Full Perception and Motion Analysis

**Status:** Proposed physical design for review  
**Database:** SQLite  
**Scope:** Full perception; trajectory prediction reserved for later  
**Implementation:** No SQL included; no database changed  
**Baseline:** Existing six-table SQLite schema and approved 24-table logical CDM

---

## 1. Physical design conventions

| Concern | Convention |
|---|---|
| Primary keys | Application-generated `TEXT` identifiers |
| Foreign keys | Explicit SQLite foreign keys; composite keys where needed to enforce session/run scope |
| Normalized time | Nullable `INTEGER`, Unix epoch milliseconds only after defensible conversion |
| Raw time | Preserve exact source representation as `TEXT` or a lossless typed representation, plus original unit |
| Ingestion time | Separate nullable/required `INTEGER` in normalized epoch milliseconds when available |
| JSON | `TEXT`, validated by application and optionally SQLite JSON functions |
| Boolean | `INTEGER` constrained to 0 or 1 |
| Unknown metadata | `NULL` or explicit status; never guessed |
| Files | Stored outside SQLite; database stores relative path, checksum and metadata |
| Provenance | Every derived output links to a transformation/run and its inputs |
| Raw source | Immutable; processed outputs written to separate locations |

Do not use one timestamp field to mean source time, normalized event time and ingestion time.

## 2. Table inventory

### Core tables

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

### Later-only tables

25. `trajectory_prediction_runs`
26. `trajectory_prediction_points`

The later-only tables are deliberately excluded from the initial migration.

---

## 3. Dataset and session tables

### 3.1 `datasets`

Purpose: identify a published or locally managed dataset collection.

Fields:
- `dataset_id` TEXT PK
- `dataset_name` TEXT NOT NULL
- `dataset_version` TEXT NULL
- `source_uri` TEXT NULL
- `license_or_terms` TEXT NULL
- `description` TEXT NULL
- `metadata_json` TEXT NULL
- `created_at_ms` INTEGER NOT NULL

Constraints:
- `dataset_name` must not be blank.
- Do not store credentials or access tokens.
- Dataset identity should be stable across sessions from the same dataset version/source.

### 3.2 `sessions`

Purpose: isolate a recording sequence or physical collection run.

Retain compatible existing columns and add/clarify:
- `session_id` TEXT PK
- `dataset_id` TEXT NULL FK → `datasets`
- `source_session_id` TEXT NULL
- `session_name` TEXT NULL
- `start_source_timestamp_raw` TEXT NULL
- `end_source_timestamp_raw` TEXT NULL
- `source_timestamp_unit` TEXT NULL
- `source_clock_reference` TEXT NULL
- `start_time_ms` INTEGER NULL
- `end_time_ms` INTEGER NULL
- `duration_ms` INTEGER NULL
- `data_origin` TEXT NOT NULL
- `metadata_json` TEXT NULL
- retain legacy vehicle/scenario/context fields where needed for compatibility

Constraints:
- New dataset-backed sessions require `dataset_id`.
- Legacy rows may retain NULL `dataset_id` during migration.
- `end_time_ms >= start_time_ms` when both are non-NULL.
- Do not derive normalized times from filename ordering alone.
- Use a documented origin vocabulary, including at minimum `real_dataset`, `physical`, `derived`, and legacy values needed during transition.

---

## 4. Sensor and modality tables

### 4.1 `sensors`

Fields:
- `sensor_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `modality` TEXT NOT NULL
- `sensor_name` TEXT NULL
- `sensor_type` TEXT NULL
- `source_stream_name` TEXT NULL
- `position_json` TEXT NULL
- `orientation_json` TEXT NULL
- `coordinate_frame` TEXT NULL
- `calibration_artifact_id` TEXT NULL FK → `artifacts` (or a deferred reference if table creation order requires)
- `configuration_artifact_id` TEXT NULL FK → `artifacts`
- `metadata_status` TEXT NOT NULL
- `metadata_json` TEXT NULL

Constraints:
- Multiple cameras/radars in one session must have distinct sensor records.
- `metadata_status` limited to `documented`, `partially_documented`, `unknown`.
- Sensor identity is not equivalent to modality.

### 4.2 `session_modalities`

Fields:
- `session_modality_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `modality` TEXT NOT NULL
- `availability_status` TEXT NOT NULL
- `metadata_available` INTEGER NOT NULL DEFAULT 0
- `measurements_available` INTEGER NOT NULL DEFAULT 0
- `metadata_json` TEXT NULL

Constraints:
- Unique `(session_id, modality)` unless the implementation intentionally models per-stream entries; per-sensor availability belongs in `sensors` or a later sensor-status table.
- Status vocabulary: `available`, `partially_available`, `not_present`, `metadata_only`, `unverified`.
- Boolean fields constrained to 0/1.
- Do not create fake observations for a missing modality.

---

## 5. Signals, artifacts and observations

### 5.1 `signals`

Retain the canonical signal dictionary table. Preserve the distinction between a signal definition and a sensor instance. Review the meaning of `is_required` before migration; it must not mean required in every dataset.

### 5.2 `artifacts`

Fields:
- `artifact_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `sensor_id` TEXT NULL FK → `sensors`
- `artifact_type` TEXT NOT NULL
- `artifact_role` TEXT NOT NULL
- `relative_path` TEXT NOT NULL
- `file_name` TEXT NULL
- `media_type` TEXT NULL
- `file_size_bytes` INTEGER NULL
- `checksum_algorithm` TEXT NULL
- `checksum_value` TEXT NULL
- `source_timestamp_raw` TEXT NULL
- `source_timestamp_unit` TEXT NULL
- `sequence_index` TEXT NULL
- `created_at_ms` INTEGER NULL
- `metadata_json` TEXT NULL

Constraints:
- `relative_path` must be relative to the managed data root.
- Prevent path traversal in application code.
- Do not delete source files when metadata rows are deleted.
- Raw source artifacts should be marked immutable.
- Checksums are recommended for raw files and important processed outputs.

### 5.3 `observations`

Retain the current table concept, but make its timestamp and payload semantics explicit.

Fields:
- `observation_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `sensor_id` TEXT NULL FK → `sensors`
- `signal_id` TEXT NULL FK → `signals`
- `modality` TEXT NOT NULL
- `observation_type` TEXT NOT NULL
- `source_timestamp_raw` TEXT NULL
- `source_timestamp_unit` TEXT NULL
- `source_clock_reference` TEXT NULL
- `timestamp_ms` INTEGER NULL — normalized event/measurement time only
- `normalization_method` TEXT NULL
- `sequence_index` TEXT NULL
- `source_record_reference` TEXT NULL
- typed payload columns retained from the existing schema
- `unit` TEXT NULL
- `quality` TEXT NOT NULL
- `quality_score` REAL NULL
- `confidence` REAL NULL
- `data_origin` TEXT NOT NULL
- `source_reference` TEXT NULL
- `transformation_id` TEXT NULL FK → `transformations`
- `ingested_at_ms` INTEGER NULL
- `metadata_json` TEXT NULL

Rules:
- Keep exactly one typed payload representation active for a scalar value, unless the observation type explicitly permits structured payloads.
- Validate payload type against `value_type`/signal definition.
- A frame or point-cloud observation may primarily reference an artifact.
- `source_timestamp_raw` must not be assumed to be milliseconds.
- `ingested_at_ms` must represent actual ingestion/processing time, not a jittered source timestamp.
- Preserve existing `source_timestamp_ms` only as a compatibility field during migration; do not use it as the new raw timestamp contract.

### 5.4 `observation_artifacts`

Fields:
- `observation_artifact_id` TEXT PK
- `observation_id` TEXT NOT NULL FK → `observations`
- `artifact_id` TEXT NOT NULL FK → `artifacts`
- `relationship_role` TEXT NOT NULL
- `metadata_json` TEXT NULL

Constraints:
- Unique `(observation_id, artifact_id, relationship_role)`.
- Supports one observation referencing multiple artifacts and one artifact containing multiple records.

---

## 6. Synchronization tables

### 6.1 `synchronization_records`

Fields:
- `sync_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `source_a_id` TEXT NOT NULL FK → `sensors`
- `source_b_id` TEXT NOT NULL FK → `sensors`
- `clock_reference_a` TEXT NULL
- `clock_reference_b` TEXT NULL
- `method` TEXT NOT NULL
- `estimated_offset` REAL NULL
- `estimated_drift` REAL NULL
- `uncertainty` REAL NULL
- `time_unit` TEXT NULL
- `valid_from_ms` INTEGER NULL
- `valid_to_ms` INTEGER NULL
- `evidence_artifact_id` TEXT NULL FK → `artifacts`
- `status` TEXT NOT NULL
- `method_version` TEXT NULL
- `metadata_json` TEXT NULL

Constraints:
- Both sensors must belong to the same session as the synchronization record.
- `source_a_id != source_b_id`.
- Status: `unverified`, `estimated`, `validated`, `rejected`.
- Do not mark a correspondence validated solely because filenames resolve.

### 6.2 `synchronization_pairs`

Fields:
- `sync_pair_id` TEXT PK
- `sync_id` TEXT NOT NULL FK → `synchronization_records`
- `observation_a_id` TEXT NOT NULL FK → `observations`
- `observation_b_id` TEXT NOT NULL FK → `observations`
- `raw_time_delta` REAL NULL
- `raw_time_unit` TEXT NULL
- `normalized_time_delta_ms` INTEGER NULL
- `pairing_method` TEXT NOT NULL
- `pairing_confidence` REAL NULL
- `metadata_json` TEXT NULL

Constraints:
- Observations must belong to the session and sensors specified by the parent synchronization record.
- Do not require one-to-one correspondence. Many camera frames may refer to the same radar record.
- Preserve the source correspondence file as an artifact.

---

## 7. Transformations and provenance

### 7.1 `transformations`

Fields:
- `transformation_id` TEXT PK
- `session_id` TEXT NULL FK → `sessions`
- `operation_type` TEXT NOT NULL
- `operation_name` TEXT NOT NULL
- `implementation_name` TEXT NULL
- `implementation_version` TEXT NULL
- `model_name` TEXT NULL
- `model_version` TEXT NULL
- `configuration_json` TEXT NULL
- `started_at_ms` INTEGER NULL
- `completed_at_ms` INTEGER NULL
- `status` TEXT NOT NULL
- `input_count` INTEGER NULL
- `output_count` INTEGER NULL
- `error_summary` TEXT NULL
- `metadata_json` TEXT NULL

Operation types should include the actual pipeline operations as used: ingestion, decoding, timestamp normalization, calibration, detection, tracking, state estimation, motion-feature extraction, interaction analysis, fusion, event detection and evaluation.

Constraints:
- A run's model/config/version must be recorded sufficiently to reproduce or interpret the output.
- Do not use one transformation row for unrelated sessions unless the transformation explicitly represents a multi-session batch and its inputs identify every session.
- Completed transformations should be immutable; reruns create new records.

### 7.2 `transformation_inputs`

Fields:
- `transformation_input_id` TEXT PK
- `transformation_id` TEXT NOT NULL FK → `transformations`
- `artifact_id` TEXT NULL FK → `artifacts`
- `observation_id` TEXT NULL FK → `observations`
- `input_role` TEXT NOT NULL
- `metadata_json` TEXT NULL

Constraint:
- Exactly one of `artifact_id` or `observation_id` must be non-NULL.
- Inputs must be traceable to the transformation's session scope.
- For very large frame sets, a manifest artifact or explicit source-range reference may be used rather than millions of input junction rows, provided individual output provenance remains recoverable.

---

## 8. Perception and tracking tables

### 8.1 `detections`

Fields:
- `detection_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `observation_id` TEXT NOT NULL FK → `observations`
- `transformation_id` TEXT NOT NULL FK → `transformations`
- `class_label` TEXT NOT NULL
- `class_id` INTEGER NULL
- `confidence` REAL NULL
- `bbox_x_min` REAL NULL
- `bbox_y_min` REAL NULL
- `bbox_x_max` REAL NULL
- `bbox_y_max` REAL NULL
- `bbox_coordinate_space` TEXT NULL
- `image_width` INTEGER NULL
- `image_height` INTEGER NULL
- `mask_artifact_id` TEXT NULL FK → `artifacts`
- `source_annotation_reference` TEXT NULL
- `is_ground_truth` INTEGER NOT NULL DEFAULT 0
- `metadata_json` TEXT NULL

Constraints:
- Observation must be a compatible frame/image observation in the same session.
- Transformation must be a detector or annotation-import run for that session.
- If any bounding-box coordinate is supplied, all four coordinates and coordinate space must be supplied.
- `bbox_x_max >= bbox_x_min`; `bbox_y_max >= bbox_y_min`.
- Confidence, when present, must be in [0,1] only if the model contract defines it that way.
- Ground-truth flag constrained to 0/1.
- Detector output and source annotation must remain distinguishable.

### 8.2 `tracks`

Fields:
- `track_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `sensor_id` TEXT NULL FK → `sensors`
- `transformation_id` TEXT NOT NULL FK → `transformations`
- `local_track_id` TEXT NOT NULL
- `class_label` TEXT NULL
- `first_source_timestamp_raw` TEXT NULL
- `last_source_timestamp_raw` TEXT NULL
- `first_timestamp_ms` INTEGER NULL
- `last_timestamp_ms` INTEGER NULL
- `track_status` TEXT NOT NULL
- `metadata_json` TEXT NULL

Constraints:
- Unique `(transformation_id, local_track_id)`.
- Transformation must be a tracking run and must be scoped to the same session.
- Sensor, when present, must belong to the same session.
- `last_timestamp_ms >= first_timestamp_ms` when both are non-NULL.
- A local tracker ID is not globally unique.

### 8.3 `track_detections`

Fields:
- `track_detection_id` TEXT PK
- `track_id` TEXT NOT NULL FK → `tracks`
- `detection_id` TEXT NOT NULL FK → `detections`
- `association_timestamp_raw` TEXT NULL
- `association_timestamp_ms` INTEGER NULL
- `association_confidence` REAL NULL
- `association_method` TEXT NOT NULL
- `association_status` TEXT NULL
- `metadata_json` TEXT NULL

Constraints:
- Track and detection must belong to the same session.
- Detection and track must be compatible with the same tracking run. Since the detector run and tracking run are separate transformations, the tracking transformation must consume the detection output.
- Prevent duplicate `(track_id, detection_id)` pairs within a run.
- Do not add a single permanent `track_id` column to `detections`; this preserves comparison across tracker runs.
- Enforce same-session/run constraints using composite unique keys and composite foreign keys where practical, otherwise triggers plus application validation.

### 8.4 `track_states`

Fields:
- `track_state_id` TEXT PK
- `track_id` TEXT NOT NULL FK → `tracks`
- `observation_id` TEXT NULL FK → `observations`
- `transformation_id` TEXT NOT NULL FK → `transformations`
- `source_timestamp_raw` TEXT NULL
- `source_timestamp_unit` TEXT NULL
- `timestamp_ms` INTEGER NULL
- `state_representation` TEXT NOT NULL
- `coordinate_frame` TEXT NULL
- `position_x` REAL NULL
- `position_y` REAL NULL
- `position_z` REAL NULL
- `position_unit` TEXT NULL
- `velocity_x` REAL NULL
- `velocity_y` REAL NULL
- `velocity_z` REAL NULL
- `speed` REAL NULL
- `speed_unit` TEXT NULL
- `acceleration_x` REAL NULL
- `acceleration_y` REAL NULL
- `acceleration_z` REAL NULL
- `acceleration_unit` TEXT NULL
- `heading` REAL NULL
- `heading_unit` TEXT NULL
- `heading_reference` TEXT NULL
- `state_source` TEXT NOT NULL
- `confidence` REAL NULL
- `uncertainty_json` TEXT NULL
- `metadata_json` TEXT NULL

Constraints:
- State transformation must be a state-estimation/filtering/fusion operation scoped to the same session as the track.
- `state_representation` vocabulary should include at least `image_space`, `camera_space`, `vehicle_space`, `world_space`, and `unknown`.
- `state_source` should distinguish `measured`, `estimated`, `filtered`, `fused`, and `annotated`.
- Coordinate frame and units must be explicit before interpreting metric values.
- Do not derive metric velocity from pixel movement without a defensible geometry/scale method.
- A track state can have no direct observation if it is interpolated/filtered, but its transformation inputs/evidence must remain traceable.

### 8.5 `track_motion_features`

Fields:
- `motion_feature_id` TEXT PK
- `track_id` TEXT NOT NULL FK → `tracks`
- `transformation_id` TEXT NOT NULL FK → `transformations`
- `start_track_state_id` TEXT NULL FK → `track_states`
- `end_track_state_id` TEXT NULL FK → `track_states`
- `start_timestamp_ms` INTEGER NULL
- `end_timestamp_ms` INTEGER NULL
- `feature_name` TEXT NOT NULL
- `feature_value` REAL NULL
- `feature_unit` TEXT NULL
- `feature_method` TEXT NOT NULL
- `feature_version` TEXT NULL
- `confidence` REAL NULL
- `uncertainty_json` TEXT NULL
- `metadata_json` TEXT NULL

Constraints:
- State references and transformation must be compatible with the same track/session.
- End time must not precede start time.
- Do not use a generic feature value without feature name, unit and method.

### 8.6 `track_interactions`

Fields:
- `track_interaction_id` TEXT PK
- `session_id` TEXT NOT NULL FK → `sessions`
- `transformation_id` TEXT NOT NULL FK → `transformations`
- `track_a_id` TEXT NOT NULL FK → `tracks`
- `track_b_id` TEXT NOT NULL FK → `tracks`
- `interaction_type` TEXT NOT NULL
- `start_timestamp_ms` INTEGER NULL
- `end_timestamp_ms` INTEGER NULL
- `relative_distance` REAL NULL
- `distance_unit` TEXT NULL
- `relative_speed` REAL NULL
- `speed_unit` TEXT NULL
- `time_to_collision_estimate` REAL NULL
- `ttc_unit` TEXT NULL
- `coordinate_frame` TEXT NULL
- `method_name` TEXT NOT NULL
- `method_version` TEXT NULL
- `confidence` REAL NULL
- `uncertainty_json` TEXT NULL
- `metadata_json` TEXT NULL

Constraints:
- `track_a_id != track_b_id`.
- Both tracks and the transformation must belong to the same session.
- End time must not precede start time.
- TTC is an estimate, not a verified collision outcome.
- Distance and relative speed require documented coordinate frame and units.
- The first version models pairwise interactions. Multi-track interactions require a participant junction table in a later revision.

### 8.7 `track_state_evidence`

Fields:
- `track_state_evidence_id` TEXT PK
- `track_state_id` TEXT NOT NULL FK → `track_states`
- `observation_id` TEXT NOT NULL FK → `observations`
- `evidence_role` TEXT NOT NULL
- `association_method` TEXT NOT NULL
- `association_confidence` REAL NULL
- `time_difference_ms` INTEGER NULL
- `spatial_residual` REAL NULL
- `spatial_residual_unit` TEXT NULL
- `metadata_json` TEXT NULL

Constraints:
- Track state and observation must belong to the same session.
- Evidence role should distinguish primary, corroborating, calibration and rejected evidence where applicable.
- Do not calculate time difference unless both timestamps have defensible normalized values.
- Preserve the association method and synchronization record reference in metadata or a dedicated FK added if the implementation requires it.

---

## 9. Event, context and relationship tables

Retain `events`, `contexts` and `event_relationships`, with the previously identified extensions:

- Distinguish dataset annotations, manual annotations, rule detections and model detections.
- Preserve nullable normalized event/context times.
- Link multiple supporting observations through `event_observations` and `context_observations`.
- Keep ground truth separate from predictions.
- Add explicit track-state/interaction evidence links only when the event-analysis use case is finalized; do not store track IDs in free-text descriptions as a substitute for relationships.
- Enforce same-session relationship integrity for `event_relationships`.
- Keep temporal association separate from causal claims.

### 9.1 `event_observations`

Fields:
- `event_observation_id` TEXT PK
- `event_id` TEXT NOT NULL FK → `events`
- `observation_id` TEXT NOT NULL FK → `observations`
- `evidence_role` TEXT NOT NULL
- `metadata_json` TEXT NULL

Unique `(event_id, observation_id, evidence_role)`. Event and observation must share a session.

### 9.2 `context_observations`

Fields:
- `context_observation_id` TEXT PK
- `context_id` TEXT NOT NULL FK → `contexts`
- `observation_id` TEXT NOT NULL FK → `observations`
- `evidence_role` TEXT NOT NULL
- `metadata_json` TEXT NULL

Unique `(context_id, observation_id, evidence_role)`. Context and observation must share a session.

---

## 10. Future trajectory-prediction tables — not in initial migration

### 10.1 `trajectory_prediction_runs`

Reserved fields:
- `prediction_run_id`
- `session_id`
- `transformation_id`
- `model_name`
- `model_version`
- `input_history_window`
- `prediction_horizon`
- `coordinate_frame`
- `configuration_json`
- `created_at_ms`
- `metadata_json`

### 10.2 `trajectory_prediction_points`

Reserved fields:
- `prediction_point_id`
- `prediction_run_id`
- `track_id`
- `prediction_origin_timestamp_ms`
- `future_timestamp_ms` or `horizon_ms`
- predicted position components
- coordinate frame and units
- uncertainty representation
- metadata

These tables must support multiple predicted points per track and per prediction run. Prediction outputs must never be mixed with observed `track_states`.

---

## 11. Cross-table integrity requirements

Before writing SQL, decide how each will be enforced using composite foreign keys, unique indexes, triggers or application-level validation:

1. Every child record belongs to the same session as its parent entities.
2. A track's transformation is a tracking run for that session.
3. A detection's transformation is a detector/annotation-import run for that session.
4. A `track_detections` row connects a detection to a track whose tracking run consumed that detection.
5. A track state references a track and a compatible state-estimation transformation.
6. A track interaction references two distinct tracks from the same session.
7. A synchronization pair references observations from the two sensors in its synchronization record.
8. Event and context evidence links cannot cross sessions.
9. `transformation_inputs` has exactly one of artifact or observation populated.
10. Typed observation payload columns match the declared payload/value type.
11. All boolean columns are restricted to 0/1.
12. All interval end times are greater than or equal to start times when both are known.
13. Deleting metadata must not delete immutable source files.
14. Completed transformation outputs should not be silently overwritten.

---

## 12. Recommended indexes

Add indexes after query patterns are confirmed. Candidate indexes:

- `sessions(dataset_id, source_session_id)`
- `sensors(session_id, modality)`
- `session_modalities(session_id, modality)`
- `artifacts(session_id, sensor_id, artifact_type)`
- `observations(session_id, timestamp_ms)`
- `observations(session_id, sensor_id, timestamp_ms)`
- `observations(session_id, modality, timestamp_ms)`
- `synchronization_records(session_id, source_a_id, source_b_id)`
- `synchronization_pairs(sync_id)`
- `transformations(session_id, operation_type, status)`
- `detections(session_id, observation_id)`
- `detections(transformation_id, class_label)`
- `tracks(session_id, transformation_id)`
- `tracks(transformation_id, local_track_id)` UNIQUE
- `track_detections(track_id, detection_id)` UNIQUE
- `track_detections(detection_id)`
- `track_states(track_id, timestamp_ms)`
- `track_states(session_id, timestamp_ms)`
- `track_motion_features(track_id, feature_name, start_timestamp_ms)`
- `track_interactions(session_id, start_timestamp_ms, interaction_type)`
- `events(session_id, event_type, start_time_ms)`
- `contexts(session_id, context_type, start_time_ms)`
- evidence junction indexes on both foreign-key directions.

Avoid indexing every JSON field or adding indexes without an actual query/evaluation need.

---

## 13. Migration compatibility and implementation boundaries

- Extend the existing six-table schema; do not replace it wholesale.
- Preserve existing IDs and records.
- Add new tables and nullable columns first; backfill only values that can be derived safely.
- Do not fabricate dataset IDs, sensor IDs, timestamps, units, labels or coordinate frames.
- Keep legacy synthetic/scenario fields nullable and compatible while the real-data path is introduced.
- Do not delete generator/config files as part of this database revision.
- Store files outside SQLite and keep only managed relative paths and metadata in the database.
- Create a versioned migration with a backup and rollback plan only after this specification is approved.
- No SQL is included in this document by design.

---

## 14. Decisions still requiring confirmation

| Decision | Proposed default | Why it needs review |
|---|---|---|
| Detection coordinate space | Store original image-pixel boxes; optional normalized boxes in metadata or explicit columns | Preserve detector output without losing frame dimensions |
| Track coordinate space | Support multiple explicit representations; do not force world coordinates | Some datasets may lack valid calibration |
| Fusion representation | A fused track state can cite multiple observations through `track_state_evidence` | Supports camera/radar evidence without inventing one-to-one sensor pairing |
| Track identity | Scoped to tracking transformation and session | Enables fair tracker comparison |
| Motion feature storage | Named rows with units/method/version | Allows feature comparisons without schema changes for every new feature |
| Interaction scope | Pairwise tracks initially | Avoid premature multi-agent schema complexity |
| Prediction | Exclude from initial migration | User selected trajectory prediction for a later phase |
| Annotation availability | Verify per dataset before import | Do not assume labels or track IDs exist |

---

## 15. Acceptance checklist before SQL

- [ ] Revised CDM reviewed and approved.
- [ ] IDD/TIAND annotation and track-label availability audited.
- [ ] Camera calibration and coordinate frames verified where metric trajectories are planned.
- [ ] Detector output contract approved.
- [ ] Tracking-run and association semantics approved.
- [ ] Track-state representations and units approved.
- [ ] Motion-feature calculation/provenance rules approved.
- [ ] Multimodal evidence and synchronization rules approved.
- [ ] Same-session/run integrity strategy approved.
- [ ] Existing SQLite compatibility and migration/rollback plan approved.

**Current state:** This is a proposed physical specification. It is not executable SQL and has not changed the database.
