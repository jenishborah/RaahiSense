"""
Unit tests for VIRA Retrieval Engine (timestamp parsing, proximity decay, dual retrieval).
"""

import os
import tempfile
import unittest

from database import init_database, insert_evidence_record, upsert_scene
from retrieval import (
    RetrievalEngine,
    compute_temporal_proximity_score,
    extract_target_categories,
    extract_timestamp_reference,
)


class TestVIRARetrieval(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_retrieval.db")
        init_database(self.db_path)

        upsert_scene(
            {
                "scene_id": "RET_SCENE_01",
                "name": "Retrieval Test Scene",
                "location": "Delhi",
                "duration_s": 30.0,
                "description": "Scene for retrieval tests",
                "data_origin": "synthetic_demo_data",
                "primary_road_context": "Urban Test",
            },
            db_path=self.db_path,
        )

        # Insert records at different timestamps
        records = [
            ("REC-R-01", 2.0, "EGO_TELEMETRY", "ego_vehicle", "Vehicle cruising at 40 km/h in lane"),
            ("REC-R-02", 11.5, "CUT_IN", "auto_rickshaw", "Auto-rickshaw abruptly cuts across lane"),
            ("REC-R-03", 12.2, "SUDDEN_BRAKING", "ego_vehicle", "Emergency braking deceleration -3.5 m/s2"),
            ("REC-R-04", 13.0, "NEAR_COLLISION", "two_wheeler", "Motorcycle swerved to avoid rear ending"),
            ("REC-R-05", 25.0, "TRAFFIC_SIGNAL_CHANGE", "none", "Signal changed to green"),
        ]
        for rid, t, ev, ru, desc in records:
            insert_evidence_record(
                {
                    "record_id": rid,
                    "scene_id": "RET_SCENE_01",
                    "timestamp_iso": "2024-03-15T12:00:00Z",
                    "timestamp_relative_s": t,
                    "event_type": ev,
                    "road_user_category": ru,
                    "observation_description": desc,
                    "source_sensor": "TEST",
                    "confidence": 0.95,
                    "road_context": "Urban Test",
                    "data_origin": "synthetic_demo_data",
                    "status": "observed",
                },
                db_path=self.db_path,
            )

        self.engine = RetrievalEngine(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_timestamp(self):
        self.assertEqual(extract_timestamp_reference("What happened around 00:12?"), 12.0)
        self.assertEqual(extract_timestamp_reference("At 12.5 seconds"), 12.5)
        self.assertEqual(extract_timestamp_reference("At 01:05 in the scene"), 65.0)
        self.assertIsNone(extract_timestamp_reference("Tell me about auto-rickshaws"))

    def test_extract_target_categories(self):
        users, events = extract_target_categories("Did the auto-rickshaw cut in and cause braking?")
        self.assertIn("auto_rickshaw", users)
        self.assertIn("CUT_IN", events)
        self.assertIn("SUDDEN_BRAKING", events)

    def test_temporal_proximity_score(self):
        s_exact = compute_temporal_proximity_score(12.0, 12.0)
        s_close = compute_temporal_proximity_score(13.0, 12.0)
        s_far = compute_temporal_proximity_score(25.0, 12.0)
        self.assertEqual(s_exact, 1.0)
        self.assertGreater(s_close, s_far)

    def test_temporal_retrieval_ranking(self):
        query = "What happened around 00:12 with the auto-rickshaw?"
        recs = self.engine.retrieve_temporal_context_aware(query, scene_id="RET_SCENE_01", top_k=3)
        retrieved_ids = [r["record_id"] for r in recs]
        # REC-R-02 (cut-in at 11.5s) and REC-R-03 (braking at 12.2s) must rank higher than REC-R-05 (at 25s)
        self.assertIn("REC-R-02", retrieved_ids)
        self.assertNotIn("REC-R-05", retrieved_ids)


if __name__ == "__main__":
    unittest.main()
