"""
Unit tests for VIRA Benchmark Evaluation Suite.
"""

import unittest
from evaluation import BenchmarkEvaluator, compute_retrieval_metrics


class TestVIRAEvaluation(unittest.TestCase):
    def test_compute_retrieval_metrics(self):
        retrieved = ["REC-01", "REC-02", "REC-03", "REC-04", "REC-05"]
        expected = ["REC-01", "REC-02", "REC-06"]

        m = compute_retrieval_metrics(retrieved, expected, k=5)
        self.assertEqual(m["precision_at_k"], 0.4)  # 2 / 5
        self.assertAlmostEqual(m["recall_at_k"], 2 / 3, places=2)
        self.assertEqual(m["hit_at_k"], 1.0)

    def test_evaluator_benchmark_run(self):
        evaluator = BenchmarkEvaluator()
        ret_results = evaluator.run_retrieval_evaluation(k=5)
        self.assertGreater(ret_results["cases_evaluated"], 0)
        self.assertIn("mean_tc_precision_at_5", ret_results)
        self.assertIn("mean_kw_precision_at_5", ret_results)

        full_results = evaluator.run_full_pipeline_evaluation(allow_offline_mock=True)
        self.assertGreater(full_results["total_test_cases"], 0)
        self.assertGreater(full_results["overall_grounding_rate_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
