"""
VIRA — Small Language Model (SLM) Client
Interface for local Small Language Models via Ollama (e.g., Llama 3.2 3B, Qwen 2.5 3B).
Enforces evidence-constrained prompting, factual grounding, citation generation,
and explicit abstention on insufficient evidence.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
RECOMMENDED_MODELS = [
    ("llama3.2:3b", "Meta Llama 3.2 3B (Fast, laptop-friendly instruction tuned)"),
    ("qwen2.5:3b", "Qwen 2.5 3B (Excellent reasoning and citation fidelity)"),
    ("phi3:mini", "Microsoft Phi-3 Mini 3.8B (Strong analytical comprehension)"),
    ("mistral:7b", "Mistral 7B Instruct (Higher capability if GPU VRAM allows)"),
]

SYSTEM_PROMPT = """You are VIRA (VehicleGPT: Evidence-Guided Road-User Activity Understanding), an automotive intelligence assistant for analyzing road-scene evidence in the Indian driving environment.

GROUNDING RULES:
1. Base your answer STRICTLY and EXCLUSIVELY on the provided evidence records below.
2. Every factual claim MUST cite its supporting record ID in square brackets (e.g., [REC-SIM-010]) and mention the timestamp.
3. Clearly distinguish DIRECTLY OBSERVED facts (sensor detections, telemetry measurements) from INFERRED interpretations (hypothesized driver intent, causal reasoning).
4. Never assume temporal proximity proves causation. Do NOT invent or infer a driver's intention or emotional state from object detections alone.
5. If the provided evidence is missing, contradictory, or insufficient to answer the question reliably, explicitly state: "INSUFFICIENT EVIDENCE: The available evidence records do not contain enough information to determine..." and list what data is missing.
6. Do NOT fabricate sensor readings, timestamps, vehicle models, or road users not present in the evidence.
7. Keep your response concise, structured, and professional."""


def check_ollama_status(host: str = DEFAULT_OLLAMA_HOST, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Check if Ollama server daemon is active and list downloaded local models.
    """
    try:
        resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("name") for m in data.get("models", [])]
            return {
                "online": True,
                "host": host,
                "models": models,
                "error": None,
                "count": len(models),
            }
        return {
            "online": False,
            "host": host,
            "models": [],
            "error": f"Ollama HTTP error {resp.status_code}",
            "count": 0,
        }
    except requests.exceptions.ConnectionError:
        return {
            "online": False,
            "host": host,
            "models": [],
            "error": "Ollama service is not running on localhost:11434.",
            "count": 0,
        }
    except Exception as e:
        return {
            "online": False,
            "host": host,
            "models": [],
            "error": str(e),
            "count": 0,
        }


def format_evidence_context(evidence_records: List[Dict[str, Any]]) -> str:
    """Format retrieved evidence records into a structured prompt context block."""
    if not evidence_records:
        return "No matching evidence records retrieved from database."

    lines = ["=== RETRIEVED ROAD-SCENE EVIDENCE RECORDS ==="]
    for idx, r in enumerate(evidence_records, 1):
        rel_s = r.get("timestamp_relative_s", 0.0)
        mins = int(rel_s // 60)
        secs = rel_s % 60
        time_str = f"{mins:02d}:{secs:04.1f} ({rel_s:.1f}s)"

        lines.append(
            f"Record [{r['record_id']}] | Time: {time_str} | Scene: {r['scene_id']}\n"
            f"  - Event: {r['event_type']} | Road User: {r['road_user_category']} | Status: {r['status'].upper()}\n"
            f"  - Sensor: {r['source_sensor']} (Confidence: {float(r.get('confidence', 1.0)):.2f}) | Origin: {r['data_origin']}\n"
            f"  - Context: {r['road_context']}\n"
            f"  - Observation: {r['observation_description']}\n"
            f"  - Reference: {r.get('evidence_reference', 'N/A')}"
        )
    lines.append("=== END OF EVIDENCE ===")
    return "\n\n".join(lines)


class SLMClient:
    """Modular Small Language Model inference client."""

    def __init__(self, host: str = DEFAULT_OLLAMA_HOST, model_name: Optional[str] = None):
        self.host = host.rstrip("/")
        self.model_name = model_name or "llama3.2:3b"

    def generate_grounded_answer(
        self,
        query: str,
        evidence_records: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 512,
        allow_offline_mock: bool = False,
    ) -> Dict[str, Any]:
        """
        Send evidence-constrained prompt to real local SLM via Ollama.
        If Ollama is offline and allow_offline_mock=True, generates an explicitly
        labeled mock response for dry-run testing.
        """
        evidence_context = format_evidence_context(evidence_records)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{evidence_context}\n\n"
            f"USER QUESTION: {query}\n\n"
            f"GROUNDED ANSWER (Cite record IDs like [REC-...], separate observed vs inferred facts, state uncertainty if evidence is lacking):"
        )

        start_time = time.time()

        # Check real Ollama
        status = check_ollama_status(self.host)
        if not status["online"]:
            if not allow_offline_mock:
                return {
                    "answer": "",
                    "model_used": None,
                    "is_real_slm": False,
                    "status": "OLLAMA_OFFLINE",
                    "latency_ms": 0,
                    "error": (
                        "Local SLM is currently offline. Ollama daemon was not detected on localhost:11434.\n\n"
                        "To run real local inference:\n"
                        "1. Download and install Ollama from https://ollama.com\n"
                        "2. In PowerShell run: `ollama pull llama3.2:3b`\n"
                        "3. Start Ollama and refresh this assistant."
                    ),
                    "prompt_sent": prompt,
                    "evidence_count": len(evidence_records),
                }
            else:
                # Explicitly labeled deterministic fallback
                mock_answer = self._generate_deterministic_fallback(query, evidence_records)
                latency = round((time.time() - start_time) * 1000, 1)
                return {
                    "answer": mock_answer,
                    "model_used": "Deterministic Fallback Mock (Ollama Offline)",
                    "is_real_slm": False,
                    "status": "OFFLINE_FALLBACK_SIMULATION",
                    "latency_ms": latency,
                    "error": None,
                    "prompt_sent": prompt,
                    "evidence_count": len(evidence_records),
                }

        # Check if selected model is available
        available_models = status["models"]
        active_model = self.model_name
        if active_model not in available_models and available_models:
            active_model = available_models[0]

        try:
            payload = {
                "model": active_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }
            resp = requests.post(f"{self.host}/api/generate", json=payload, timeout=60.0)
            latency = round((time.time() - start_time) * 1000, 1)

            if resp.status_code == 200:
                result_json = resp.json()
                raw_answer = result_json.get("response", "").strip()
                return {
                    "answer": raw_answer,
                    "model_used": active_model,
                    "is_real_slm": True,
                    "status": "SUCCESS",
                    "latency_ms": latency,
                    "error": None,
                    "prompt_sent": prompt,
                    "evidence_count": len(evidence_records),
                }
            else:
                return {
                    "answer": "",
                    "model_used": active_model,
                    "is_real_slm": False,
                    "status": "API_ERROR",
                    "latency_ms": latency,
                    "error": f"Ollama error {resp.status_code}: {resp.text}",
                    "prompt_sent": prompt,
                    "evidence_count": len(evidence_records),
                }

        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 1)
            return {
                "answer": "",
                "model_used": active_model,
                "is_real_slm": False,
                "status": "REQUEST_FAILED",
                "latency_ms": latency,
                "error": str(e),
                "prompt_sent": prompt,
                "evidence_count": len(evidence_records),
            }

    def _generate_deterministic_fallback(
        self, query: str, evidence_records: List[Dict[str, Any]]
    ) -> str:
        """
        Deterministic fallback purely for UI evaluation testing when Ollama is offline.
        Strictly labeled so it cannot be mistaken for a real model.
        """
        q_lower = query.lower()

        # Check for unanswerable / insufficient evidence scenarios
        unanswerable_kws = ["intent", "driver thinking", "why did driver choose", "ambulance", "cattle", "dog", "police", "00:45", "00:50"]
        if any(kw in q_lower for kw in unanswerable_kws):
            return (
                "[MOCK / OFFLINE FALLBACK - NOT A REAL SLM]\n\n"
                "INSUFFICIENT EVIDENCE: The available database records do not contain evidence to determine "
                "the subjective driver intent or the specified event. Object detectors and CAN telemetry record "
                "physical kinematic changes, not internal driver cognitive states. Sensor records for external out-of-domain "
                "entities (e.g. emergency vehicles) are not present in this scenario."
            )

        if not evidence_records:
            return (
                "[MOCK / OFFLINE FALLBACK - NOT A REAL SLM]\n\n"
                "INSUFFICIENT EVIDENCE: No relevant evidence records were retrieved for this query from the evidence store."
            )

        # Build grounded response based on top retrieved records
        observed_facts = []
        inferred_facts = []
        cited_ids = []

        for r in evidence_records[:3]:
            rec_id = r["record_id"]
            cited_ids.append(f"[{rec_id}]")
            t_str = f"at {r['timestamp_relative_s']:.1f}s"
            if r["status"] == "inferred":
                inferred_facts.append(f"- Inferred interpretation {t_str} {cited_ids[-1]}: {r['observation_description']}")
            else:
                observed_facts.append(f"- Observed fact {t_str} {cited_ids[-1]}: {r['observation_description']}")

        body = (
            "[MOCK / OFFLINE FALLBACK - NOT A REAL SLM]\n\n"
            f"Based on the retrieved evidence {' '.join(cited_ids)}:\n\n"
            "**Directly Observed Facts:**\n" +
            ("\n".join(observed_facts) if observed_facts else "None.") + "\n\n"
            "**Inferred Interpretations:**\n" +
            ("\n".join(inferred_facts) if inferred_facts else "No causal inferences provided in evidence.") + "\n\n"
            "**Causality & Grounding Notice:** Temporal proximity between these observations correlates with an evasive interaction, "
            "but driver cognitive intention cannot be directly verified by sensor telemetry alone."
        )
        return body
