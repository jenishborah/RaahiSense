"""
Unit tests for VIRA Grounding & Verification Engine.
"""

import unittest
from grounding import (
    detect_insufficient_evidence_abstention,
    detect_observed_vs_inferred_separation,
    evaluate_grounding,
    extract_cited_record_ids,
)


class TestVIRAGrounding(unittest.TestCase):
    def test_extract_citations(self):
        text = "Based on [REC-SIM-010] and [REC-SIM-011], emergency braking occurred in REC-SIM-012."
        ids = extract_cited_record_ids(text)
        self.assertEqual(ids, ["REC-SIM-010", "REC-SIM-011", "REC-SIM-012"])

    def test_detect_abstention(self):
        self.assertTrue(detect_insufficient_evidence_abstention("INSUFFICIENT EVIDENCE: The data does not contain..."))
        self.assertTrue(detect_insufficient_evidence_abstention("The driver's intent cannot be determined from telemetry alone."))
        self.assertFalse(detect_insufficient_evidence_abstention("The auto-rickshaw cut in at 12 seconds."))

    def test_detect_separation(self):
        text = "Observed fact: sudden brake pulse. Inferred interpretation: driver reacted to cut-in."
        self.assertTrue(detect_observed_vs_inferred_separation(text))

    def test_evaluate_grounding_valid(self):
        retrieved = [{"record_id": "REC-SIM-010"}, {"record_id": "REC-SIM-011"}]
        answer = "The auto-rickshaw swerved [REC-SIM-010] and cut in [REC-SIM-011]."
        res = evaluate_grounding(answer, retrieved)
        self.assertEqual(res["verdict"], "FULLY_GROUNDED")
        self.assertEqual(res["citation_precision"], 1.0)
        self.assertEqual(len(res["valid_citations"]), 2)

    def test_evaluate_grounding_hallucination(self):
        retrieved = [{"record_id": "REC-SIM-010"}]
        answer = "The vehicle braked according to [REC-FAKE-999]."
        res = evaluate_grounding(answer, retrieved)
        self.assertEqual(res["verdict"], "PARTIAL_HALLUCINATION")
        self.assertIn("REC-FAKE-999", res["hallucinated_citations"])

    def test_evaluate_grounding_abstention(self):
        retrieved = []
        answer = "INSUFFICIENT EVIDENCE: There is not enough information to determine the driver's intent."
        res = evaluate_grounding(answer, retrieved, is_expected_abstention_query=True)
        self.assertEqual(res["verdict"], "VALID_ABSTENTION")
        self.assertTrue(res["is_grounded"])


if __name__ == "__main__":
    unittest.main()
