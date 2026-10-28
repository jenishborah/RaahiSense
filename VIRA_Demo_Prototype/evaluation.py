"""
VIRA — Evaluation & Research Benchmark Suite
Runs repeatable evaluation of:
1. Evidence Retrieval (Precision@K, Recall@K, Keyword vs Temporal-Context Comparison)
2. SLM Answer Grounding (Citation accuracy, hallucination detection, abstention compliance)
3. Latency & Resource Benchmarking
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from database import DEFAULT_DB_PATH
from grounding import evaluate_grounding
from retrieval import RetrievalEngine
from slm_client import SLMClient

logger = logging.getLogger(__name__)

BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), "data", "evaluation_benchmark.json")


def load_benchmark_cases(benchmark_file: str = BENCHMARK_PATH) -> List[Dict[str, Any]]:
    """Load benchmark test cases from JSON file."""
    if not os.path.isfile(benchmark_file):
        raise FileNotFoundError(f"Benchmark file not found at: {benchmark_file}")
    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_cases", [])


def compute_retrieval_metrics(
    retrieved_ids: List[str], expected_ids: List[str], k: int = 5
) -> Dict[str, float]:
    """Compute Precision@K, Recall@K, and Hit@K."""
    if not expected_ids:
        # For negative / abstention cases
        return {"precision_at_k": 1.0 if not retrieved_ids else 0.0, "recall_at_k": 1.0, "hit_at_k": 1.0}

    top_k = retrieved_ids[:k]
    hits = [rid for rid in top_k if rid in expected_ids]
    precision = len(hits) / max(len(top_k), 1)
    recall = len(hits) / max(len(expected_ids), 1)
    hit = 1.0 if len(hits) > 0 else 0.0

    return {
        "precision_at_k": round(precision, 3),
        "recall_at_k": round(recall, 3),
        "hit_at_k": hit,
    }


class BenchmarkEvaluator:
    """Evaluates retrieval and SLM grounding performance across curated test cases."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        benchmark_file: str = BENCHMARK_PATH,
        slm_client: Optional[SLMClient] = None,
    ):
        self.db_path = db_path
        self.benchmark_file = benchmark_file
        self.retrieval_engine = RetrievalEngine(db_path=db_path)
        self.slm_client = slm_client or SLMClient()

    def run_retrieval_evaluation(self, k: int = 5) -> Dict[str, Any]:
        """
        Compare Keyword-Only vs Temporal/Context-Aware retrieval across all benchmark cases.
        """
        cases = load_benchmark_cases(self.benchmark_file)

        results = []
        kw_p_total = 0.0
        kw_r_total = 0.0
        tc_p_total = 0.0
        tc_r_total = 0.0
        evaluated_cases = 0

        for case in cases:
            # Skip pure abstention test cases from precision calculation if expected_ids is empty
            exp_ids = case["expected_evidence_ids"]
            query = case["query"]
            scene_id = case["scene_id"]

            t0 = time.time()
            kw_recs = self.retrieval_engine.retrieve_keyword_only(query, scene_id=scene_id, top_k=k)
            t_kw = round((time.time() - t0) * 1000, 2)

            t1 = time.time()
            tc_recs = self.retrieval_engine.retrieve_temporal_context_aware(query, scene_id=scene_id, top_k=k)
            t_tc = round((time.time() - t1) * 1000, 2)

            kw_ids = [r["record_id"] for r in kw_recs]
            tc_ids = [r["record_id"] for r in tc_recs]

            kw_metrics = compute_retrieval_metrics(kw_ids, exp_ids, k=k)
            tc_metrics = compute_retrieval_metrics(tc_ids, exp_ids, k=k)

            if exp_ids:
                kw_p_total += kw_metrics["precision_at_k"]
                kw_r_total += kw_metrics["recall_at_k"]
                tc_p_total += tc_metrics["precision_at_k"]
                tc_r_total += tc_metrics["recall_at_k"]
                evaluated_cases += 1

            results.append(
                {
                    "test_id": case["test_id"],
                    "query": query,
                    "scene_id": scene_id,
                    "category": case["category"],
                    "expected_ids": exp_ids,
                    "kw_retrieved_ids": kw_ids,
                    "tc_retrieved_ids": tc_ids,
                    "kw_precision": kw_metrics["precision_at_k"],
                    "kw_recall": kw_metrics["recall_at_k"],
                    "tc_precision": tc_metrics["precision_at_k"],
                    "tc_recall": tc_metrics["recall_at_k"],
                    "kw_latency_ms": t_kw,
                    "tc_latency_ms": t_tc,
                }
            )

        denom = max(evaluated_cases, 1)
        mean_kw_precision = round(kw_p_total / denom, 3)
        mean_kw_recall = round(kw_r_total / denom, 3)
        mean_tc_precision = round(tc_p_total / denom, 3)
        mean_tc_recall = round(tc_r_total / denom, 3)

        improvement_pct = round(
            ((mean_tc_precision - mean_kw_precision) / max(mean_kw_precision, 0.01)) * 100, 1
        )

        return {
            "cases_evaluated": len(cases),
            "factual_cases": evaluated_cases,
            "mean_kw_precision_at_5": mean_kw_precision,
            "mean_kw_recall_at_5": mean_kw_recall,
            "mean_tc_precision_at_5": mean_tc_precision,
            "mean_tc_recall_at_5": mean_tc_recall,
            "precision_improvement_pct": improvement_pct,
            "case_details": results,
        }

    def run_full_pipeline_evaluation(
        self, allow_offline_mock: bool = True
    ) -> Dict[str, Any]:
        """
        Run end-to-end evaluation including retrieval, SLM generation, and grounding validation.
        """
        cases = load_benchmark_cases(self.benchmark_file)
        eval_records = []

        total_grounded = 0
        total_abstained_correctly = 0
        total_latencies = []

        for case in cases:
            query = case["query"]
            scene_id = case["scene_id"]
            is_abstention = case["expected_abstention"]

            # Retrieve temporal context aware
            retrieved = self.retrieval_engine.retrieve_temporal_context_aware(
                query, scene_id=scene_id, top_k=5
            )

            # Generate SLM answer
            slm_res = self.slm_client.generate_grounded_answer(
                query=query,
                evidence_records=retrieved,
                allow_offline_mock=allow_offline_mock,
            )

            answer = slm_res["answer"]
            latency = slm_res.get("latency_ms", 0.0)
            total_latencies.append(latency)

            # Evaluate grounding
            grounding_res = evaluate_grounding(
                generated_answer=answer,
                retrieved_evidence=retrieved,
                is_expected_abstention_query=is_abstention,
            )

            if grounding_res["is_grounded"]:
                total_grounded += 1

            if is_abstention and grounding_res["has_abstained"]:
                total_abstained_correctly += 1

            eval_records.append(
                {
                    "test_id": case["test_id"],
                    "query": query,
                    "scene_id": scene_id,
                    "category": case["category"],
                    "expected_abstention": is_abstention,
                    "retrieved_count": len(retrieved),
                    "model_used": slm_res.get("model_used"),
                    "is_real_slm": slm_res.get("is_real_slm"),
                    "slm_status": slm_res.get("status"),
                    "grounding_verdict": grounding_res["verdict"],
                    "valid_citations": grounding_res["valid_citations"],
                    "hallucinated_citations": grounding_res["hallucinated_citations"],
                    "citation_precision": grounding_res["citation_precision"],
                    "has_abstained": grounding_res["has_abstained"],
                    "latency_ms": latency,
                    "answer_preview": (answer[:120] + "...") if len(answer) > 120 else answer,
                }
            )

        n = len(cases)
        overall_grounding_rate = round((total_grounded / max(n, 1)) * 100, 1)
        mean_latency = round(sum(total_latencies) / max(len(total_latencies), 1), 1)

        return {
            "total_test_cases": n,
            "overall_grounding_rate_pct": overall_grounding_rate,
            "mean_response_latency_ms": mean_latency,
            "eval_records": eval_records,
            "methodology_disclaimer": (
                "Prototype Evaluation Notice: Automated citation matching and pattern-based abstention "
                "detection serve as research indicators of factual grounding. They evaluate lexical and citation "
                "alignment, but do not replace comprehensive human semantic verification in safety-critical domains."
            ),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    evaluator = BenchmarkEvaluator()
    print("=== RETRIEVAL EVALUATION ===")
    ret_res = evaluator.run_retrieval_evaluation()
    print(f"Keyword Precision@5: {ret_res['mean_kw_precision_at_5']}")
    print(f"Temporal/Context Precision@5: {ret_res['mean_tc_precision_at_5']}")
    print(f"Relative Improvement: +{ret_res['precision_improvement_pct']}%")

    print("\n=== FULL PIPELINE EVALUATION ===")
    full_res = evaluator.run_full_pipeline_evaluation(allow_offline_mock=True)
    print(f"Overall Grounding Rate: {full_res['overall_grounding_rate_pct']}%")
    print(f"Mean Latency: {full_res['mean_response_latency_ms']} ms")
