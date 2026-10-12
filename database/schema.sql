PRAGMA foreign_keys = ON;

-- ============================================================
-- RaahiSense - Frozen v1 Database Schema
-- SQLite
--
-- Primary IDs  : UUIDv7 stored as TEXT
-- Timestamps   : Unix epoch milliseconds stored as INTEGER
-- JSON         : JSON stored as TEXT
--
-- Frozen v1 tables:
--   1. sessions
--   2. signals
--   3. observations
--   4. events
--   5. contexts
--   6. event_relationships
-- ============================================================


-- ============================================================
-- 1. SESSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    session_id              TEXT PRIMARY KEY NOT NULL,
    vehicle_id              TEXT NOT NULL,
    scenario_id             TEXT,
    session_name            TEXT,

    start_time_ms            INTEGER NOT NULL,
    end_time_ms              INTEGER NOT NULL,

    duration_ms              INTEGER
        GENERATED ALWAYS AS (end_time_ms - start_time_ms) STORED,

    data_origin              TEXT NOT NULL
        CHECK (data_origin IN (
            'synthetic',
            'simulation',
            'replay',
            'physical'
        )),

    generator_version       TEXT,
    schema_version          TEXT NOT NULL,

    road_type               TEXT,
    traffic_level           TEXT,
    weather                 TEXT,
    lighting                TEXT,
    region                  TEXT,

    latitude_start          REAL,
    longitude_start         REAL,
    latitude_end            REAL,
    longitude_end           REAL,

    distance_km             REAL,

    initial_soc             REAL
        CHECK (initial_soc IS NULL OR
               (initial_soc >= 0 AND initial_soc <= 100)),

    final_soc               REAL
        CHECK (final_soc IS NULL OR
               (final_soc >= 0 AND final_soc <= 100)),

    initial_battery_temp_c  REAL,
    final_battery_temp_c    REAL,

    created_at_ms           INTEGER NOT NULL,

    metadata_json           TEXT
);


-- ============================================================
-- 2. SIGNALS
-- ============================================================

CREATE TABLE IF NOT EXISTS signals (
    signal_id               TEXT PRIMARY KEY NOT NULL,

    canonical_name          TEXT UNIQUE NOT NULL,
    display_name            TEXT NOT NULL,

    category                TEXT NOT NULL,
    subcategory             TEXT,

    data_type               TEXT NOT NULL,

    default_unit            TEXT,
    description             TEXT,

    min_value               REAL,
    max_value               REAL,

    expected_frequency_hz   REAL,

    source_type             TEXT,

    is_derived              INTEGER NOT NULL
        CHECK (is_derived IN (0, 1)),

    is_required             INTEGER NOT NULL
        CHECK (is_required IN (0, 1)),

    aggregation_method      TEXT,

    quality_rule            TEXT,

    schema_version          TEXT NOT NULL,

    metadata_json           TEXT
);


-- ============================================================
-- 3. OBSERVATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS observations (
    observation_id          TEXT PRIMARY KEY NOT NULL,

    session_id              TEXT NOT NULL,
    signal_id               TEXT NOT NULL,

    timestamp_ms            INTEGER NOT NULL,
    sequence_no             INTEGER,

    source                  TEXT NOT NULL,

    value_num               REAL,
    value_text              TEXT,

    value_bool              INTEGER
        CHECK (value_bool IS NULL OR value_bool IN (0, 1)),

    value_int               INTEGER,
    value_json              TEXT,

    unit                    TEXT,

    quality                 TEXT NOT NULL
        CHECK (quality IN (
            'valid',
            'missing',
            'estimated',
            'interpolated',
            'invalid',
            'out_of_range',
            'delayed'
        )),

    quality_score           REAL
        CHECK (quality_score IS NULL OR
               (quality_score >= 0 AND quality_score <= 1)),

    confidence              REAL
        CHECK (confidence IS NULL OR
               (confidence >= 0 AND confidence <= 1)),

    is_missing              INTEGER DEFAULT 0
        CHECK (is_missing IN (0, 1)),

    is_interpolated         INTEGER DEFAULT 0
        CHECK (is_interpolated IN (0, 1)),

    is_outlier              INTEGER DEFAULT 0
        CHECK (is_outlier IN (0, 1)),

    road_context            TEXT,
    driving_context         TEXT,

    latitude                REAL,
    longitude               REAL,
    altitude_m              REAL,

    data_origin             TEXT NOT NULL
        CHECK (data_origin IN (
            'synthetic',
            'simulation',
            'replay',
            'physical'
        )),

    source_reference        TEXT,
    source_timestamp_ms     INTEGER,
    ingested_at_ms          INTEGER,

    metadata_json           TEXT,

    FOREIGN KEY (session_id)
        REFERENCES sessions(session_id)
        ON DELETE CASCADE,

    FOREIGN KEY (signal_id)
        REFERENCES signals(signal_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- 4. EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS events (
    event_id                    TEXT PRIMARY KEY NOT NULL,

    session_id                  TEXT NOT NULL,

    event_type                  TEXT NOT NULL,
    event_category              TEXT NOT NULL,

    start_time_ms               INTEGER NOT NULL,
    end_time_ms                 INTEGER NOT NULL,

    duration_ms                 INTEGER
        GENERATED ALWAYS AS (end_time_ms - start_time_ms) STORED,

    severity                    TEXT,

    confidence                  REAL
        CHECK (confidence IS NULL OR
               (confidence >= 0 AND confidence <= 1)),

    source                      TEXT,

    detection_method            TEXT,

    detection_version           TEXT,

    trigger_observation_id      TEXT,

    description                 TEXT,

    road_context                TEXT,
    driving_context             TEXT,

    latitude                    REAL,
    longitude                   REAL,

    data_origin                 TEXT NOT NULL
        CHECK (data_origin IN (
            'synthetic',
            'simulation',
            'replay',
            'physical'
        )),

    is_ground_truth             INTEGER DEFAULT 0
        CHECK (is_ground_truth IN (0, 1)),

    metadata_json               TEXT,

    FOREIGN KEY (session_id)
        REFERENCES sessions(session_id)
        ON DELETE CASCADE,

    FOREIGN KEY (trigger_observation_id)
        REFERENCES observations(observation_id)
        ON DELETE SET NULL
);


-- ============================================================
-- 5. CONTEXTS
-- ============================================================

CREATE TABLE IF NOT EXISTS contexts (
    context_id              TEXT PRIMARY KEY NOT NULL,

    session_id              TEXT NOT NULL,

    context_type             TEXT NOT NULL,
    context_category         TEXT,

    start_time_ms            INTEGER NOT NULL,
    end_time_ms              INTEGER NOT NULL,

    label                    TEXT,

    value_num                REAL,
    value_text               TEXT,

    unit                     TEXT,

    confidence               REAL
        CHECK (confidence IS NULL OR
               (confidence >= 0 AND confidence <= 1)),

    source                   TEXT,
    detection_method         TEXT,

    latitude_start           REAL,
    longitude_start          REAL,
    latitude_end             REAL,
    longitude_end            REAL,

    data_origin              TEXT NOT NULL
        CHECK (data_origin IN (
            'synthetic',
            'simulation',
            'replay',
            'physical'
        )),

    metadata_json            TEXT,

    FOREIGN KEY (session_id)
        REFERENCES sessions(session_id)
        ON DELETE CASCADE
);


-- ============================================================
-- 6. EVENT_RELATIONSHIPS
-- ============================================================

CREATE TABLE IF NOT EXISTS event_relationships (
    relationship_id          TEXT PRIMARY KEY NOT NULL,

    session_id               TEXT NOT NULL,

    source_event_id          TEXT NOT NULL,
    target_event_id          TEXT NOT NULL,

    relationship_type        TEXT NOT NULL
        CHECK (relationship_type IN (
            'PRECEDES',
            'FOLLOWS',
            'OVERLAPS',
            'CO_OCCURS',
            'WITHIN_WINDOW',
            'ASSOCIATED_WITH'
        )),

    time_delta_ms            INTEGER,
    overlap_ms               INTEGER,
    distance_m               REAL,

    confidence               REAL
        CHECK (confidence IS NULL OR
               (confidence >= 0 AND confidence <= 1)),

    method                   TEXT,

    window_ms                INTEGER,

    is_ground_truth          INTEGER DEFAULT 0
        CHECK (is_ground_truth IN (0, 1)),

    causal_claim_allowed     INTEGER DEFAULT 0
        CHECK (causal_claim_allowed IN (0, 1)),

    description              TEXT,

    metadata_json            TEXT,

    FOREIGN KEY (session_id)
        REFERENCES sessions(session_id)
        ON DELETE CASCADE,

    FOREIGN KEY (source_event_id)
        REFERENCES events(event_id)
        ON DELETE CASCADE,

    FOREIGN KEY (target_event_id)
        REFERENCES events(event_id)
        ON DELETE CASCADE
);


-- ============================================================
-- INDEXES
-- ============================================================

-- ----------------------------
-- sessions
-- ----------------------------

CREATE INDEX IF NOT EXISTS idx_sessions_vehicle_time
    ON sessions (vehicle_id, start_time_ms);

CREATE INDEX IF NOT EXISTS idx_sessions_scenario
    ON sessions (scenario_id);

CREATE INDEX IF NOT EXISTS idx_sessions_time
    ON sessions (start_time_ms, end_time_ms);


-- ----------------------------
-- observations
-- ----------------------------

CREATE INDEX IF NOT EXISTS idx_obs_session_time
    ON observations (session_id, timestamp_ms);

CREATE INDEX IF NOT EXISTS idx_obs_signal_time
    ON observations (signal_id, timestamp_ms);

CREATE INDEX IF NOT EXISTS idx_obs_session_signal_time
    ON observations (session_id, signal_id, timestamp_ms);

CREATE INDEX IF NOT EXISTS idx_obs_source_time
    ON observations (source, timestamp_ms);


-- ----------------------------
-- events
-- ----------------------------

CREATE INDEX IF NOT EXISTS idx_events_session_type_time
    ON events (session_id, event_type, start_time_ms);

CREATE INDEX IF NOT EXISTS idx_events_session_time
    ON events (session_id, start_time_ms, end_time_ms);


-- ----------------------------
-- contexts
-- ----------------------------

CREATE INDEX IF NOT EXISTS idx_contexts_session_type_time
    ON contexts (session_id, context_type, start_time_ms);


-- ----------------------------
-- event relationships
-- ----------------------------

CREATE INDEX IF NOT EXISTS idx_rel_session_type
    ON event_relationships (session_id, relationship_type);

CREATE INDEX IF NOT EXISTS idx_rel_source
    ON event_relationships (source_event_id);

CREATE INDEX IF NOT EXISTS idx_rel_target
    ON event_relationships (target_event_id);