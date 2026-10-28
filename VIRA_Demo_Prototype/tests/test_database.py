"""
Unit tests for VIRA database operations, schema initialization, and FTS indexing.
"""

import os
import tempfile
import unittest

from database import (
    get_all_scenes,
    get_provenance_stats,
    get_record_by_id,
    init_database,
    insert_evidence_record,
    query_evidence,
    search_evidence_fts,
    upsert_scene,
)


class TestVIRADatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_vira.db")
        init_database(self.db_path)

        # Insert test scene
        upsert_scene(
            {
                "scene_id": "TEST_SCENE_01",
                "name": "Test Urban Scene",
                "location": "Bengaluru",
                "duration_s": 20.0,
                "description": "A test scene for unit tests",
                "data_origin": "synthetic_demo_data",
                "primary_road_context": "Urban Test Corridor",
            },
            db_path=self.db_path,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_insert_and_get_record(self):
        rec = {
            "record_id": "REC-TEST-001",
            "scene_id": "TEST_SCENE_01",
            "timestamp_iso": "2024-03-15T10:00:00Z",
            "timestamp_relative_s": 12.0,
            "event_type": "CUT_IN",
            "road_user_category": "auto_rickshaw",
            "observation_description": "Auto-rickshaw abruptly cut in ahead of ego vehicle.",
            "source_sensor": "TEST_CAMERA",
            "confidence": 0.95,
            "road_context": "Urban Junction",
            "evidence_reference": "CAM_FRAME:001",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
        }
        res = insert_evidence_record(rec, db_path=self.db_path)
        self.assertTrue(res)

        fetched = get_record_by_id("REC-TEST-001", db_path=self.db_path)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["road_user_category"], "auto_rickshaw")
        self.assertEqual(fetched["timestamp_relative_s"], 12.0)

    def test_duplicate_record_handling(self):
        rec = {
            "record_id": "REC-DUP-001",
            "scene_id": "TEST_SCENE_01",
            "timestamp_iso": "2024-03-15T10:00:00Z",
            "timestamp_relative_s": 5.0,
            "event_type": "EGO_TELEMETRY",
            "road_user_category": "ego_vehicle",
            "observation_description": "First insertion",
            "source_sensor": "TEST_SENSOR",
            "confidence": 1.0,
            "road_context": "Road",
            "data_origin": "synthetic_demo_data",
            "status": "observed",
        }
        self.assertTrue(insert_evidence_record(rec, db_path=self.db_path))
        # Inserting duplicate primary key should return False, not crash
        self.assertFalse(insert_evidence_record(rec, db_path=self.db_path))

    def test_fts5_search(self):
        insert_evidence_record(
            {
                "record_id": "REC-FTS-001",
                "scene_id": "TEST_SCENE_01",
                "timestamp_iso": "2024-03-15T10:00:00Z",
                "timestamp_relative_s": 8.0,
                "event_type": "PEDESTRIAN_INTERACTION",
                "road_user_category": "pedestrian",
                "observation_description": "Pedestrian crossed near zebra crossing with hand raised.",
                "source_sensor": "TEST_DETECTOR",
                "confidence": 0.92,
                "road_context": "Zebra Crossing",
                "data_origin": "synthetic_demo_data",
                "status": "observed",
            },
            db_path=self.db_path,
        )

        results = search_evidence_fts("zebra crossing pedestrian", db_path=self.db_path)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["record_id"], "REC-FTS-001")

    def test_provenance_stats(self):
        stats = get_provenance_stats(self.db_path)
        self.assertIn("total_records", stats)
        self.assertIn("tiand_pct", stats)
        self.assertIn("synthetic_pct", stats)


if __name__ == "__main__":
    unittest.main()
