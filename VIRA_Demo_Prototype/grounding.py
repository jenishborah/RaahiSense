"""
VIRA — Grounding & Verification Engine
Validates citation fidelity, factual alignment, abstention appropriateness,
and observed vs inferred separation in SLM-generated answers.
"""

import re
from typing import Any, Dict, List, Set, Tuple


def extract_cited_record_ids(text: str) -> List[str]:
    """
    Extract record identifiers cited in the text.
    Matches formats like [REC-SIM-010], [REC-TIAND-0001], or bare REC-SIM-010.
    """
    matches = re.findall(r"\[?(REC-[A-Za-z0-9_-]+)\]?", text)
    # Deduplicate while preserving order
    seen: Set[str] = set()
    cited: List[str] = []
    for m in matches:
        m_clean = m.strip("[]")
        if m_clean not in seen:
            seen.add(m_clean)
            cited.append(m_clean)
    return cited


def detect_insufficient_evidence_abstention(text: str) -> bool:
    """Check if the response explicitly acknowledged insufficient evidence or abstained."""
    cues = [
        "insufficient evidence",
        "cannot be determined",
        "not enough information",
        "no evidence to determine",
        "lacking sufficient",
        "do not contain enough information",
        "not observed in the sensor data",
        "unable to confirm",
        "cannot prove causation",
        "cannot be verified",
    ]
    text_lower = text.lower()
    return any(cue in text_lower for cue in cues)


def detect_observed_vs_inferred_separation(text: str) -> bool:
    """Check if the answer distinguishes directly observed facts from inferred interpretations."""
    text_lower = text.lower()
    has_observed = any(w in text_lower for w in ["observed", "direct observation", "telemetry record", "sensor detection"])
    has_inferred = any(w in text_lower for w in ["inferred", "interpretation", "hypothesis", "causal explanation"])
    return has_observed and has_inferred


def evaluate_grounding(
    generated_answer: str,
    retrieved_evidence: List[Dict[str, Any]],
    is_expected_abstention_query: bool = False,
) -> Dict[str, Any]:
    """
    Perform multi-dimensional grounding verification on an SLM response.
    Returns quantitative metrics and categorical grounding verdict.
    """
    retrieved_ids = {r["record_id"] for r in retrieved_evidence}
    cited_ids = extract_cited_record_ids(generated_answer)

    valid_citations = [cid for cid in cited_ids if cid in retrieved_ids]
    hallucinated_citations = [cid for cid in cited_ids if cid not in retrieved_ids]

    has_abstained = detect_insufficient_evidence_abstention(generated_answer)
    has_separation = detect_observed_vs_inferred_separation(generated_answer)

    # Citation precision & recall
    total_cited = len(cited_ids)
    citation_precision = (len(valid_citations) / total_cited) if total_cited > 0 else 0.0
    citation_recall = (len(valid_citations) / len(retrieved_ids)) if retrieved_ids else 0.0

    # Determine grounding status
    if is_expected_abstention_query:
        if has_abstained:
            verdict = "VALID_ABSTENTION"
            explanation = "Model correctly acknowledged insufficient evidence for an unanswerable or subjective query."
        else:
            verdict = "UNJUSTIFIED_SPECULATION"
            explanation = "Model attempted to answer a query that lacked sufficient factual evidence."
    elif total_cited == 0:
        if has_abstained:
            verdict = "VALID_ABSTENTION"
            explanation = "Model indicated insufficient evidence."
        else:
            verdict = "UNGROUNDED_NO_CITATIONS"
            explanation = "Answer generated without citing any supporting record IDs from retrieved evidence."
    elif hallucinated_citations:
        verdict = "PARTIAL_HALLUCINATION"
        explanation = f"Answer cited {len(hallucinated_citations)} records not present in the retrieved evidence: {hallucinated_citations}."
    elif citation_precision >= 1.0 and len(valid_citations) > 0:
        verdict = "FULLY_GROUNDED"
        explanation = f"All {len(valid_citations)} citations are verified and grounded in retrieved evidence."
    else:
        verdict = "PARTIALLY_GROUNDED"
        explanation = f"Answer partially cites retrieved evidence ({len(valid_citations)} valid)."

    return {
        "verdict": verdict,
        "is_grounded": verdict in ("FULLY_GROUNDED", "VALID_ABSTENTION"),
        "total_citations": total_cited,
        "valid_citations": valid_citations,
        "hallucinated_citations": hallucinated_citations,
        "citation_precision": round(citation_precision, 3),
        "citation_recall": round(citation_recall, 3),
        "has_abstained": has_abstained,
        "observed_inferred_separation": has_separation,
        "explanation": explanation,
    }
