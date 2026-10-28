"""
VIRA — Retrieval Engine
Provides transparent evidence retrieval comparing:
1. Keyword-Only Retrieval (FTS5 / Lexical Overlap)
2. Temporal & Context-Aware Retrieval (Time-window, Proximity Decay, Road-user Priors)
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from database import DEFAULT_DB_PATH, query_evidence, search_evidence_fts

ROAD_USER_KEYWORDS = {
    "auto_rickshaw": ["rickshaw", "auto", "three-wheeler", "3-wheeler", "bajaj", "tuk-tuk", "auto-rickshaw"],
    "two_wheeler": ["two-wheeler", "motorcycle", "bike", "scooter", "splendor", "activa", "cyclist"],
    "pedestrian": ["pedestrian", "person", "crossing", "walker", "foot", "pedestrians", "jaywalker"],
    "bus": ["bus", "dtc", "transit", "public transport"],
    "car": ["car", "suv", "sedan", "vehicle"],
    "ego_vehicle": ["ego", "ego-vehicle", "own vehicle", "speed", "accelerat", "brake", "braking", "telemetry"],
}

EVENT_KEYWORDS = {
    "CUT_IN": ["cut-in", "cut in", "cutting in", "swerved ahead"],
    "SUDDEN_BRAKING": ["brake", "braking", "sudden brake", "emergency deceleration", "slow down", "slowed down"],
    "PEDESTRIAN_INTERACTION": ["pedestrian", "crossing", "median", "hand raise", "gesture"],
    "NEAR_COLLISION": ["near collision", "near-miss", "swerve", "avoid collision", "rear-end"],
    "TRAFFIC_SIGNAL_CHANGE": ["traffic light", "signal", "amber", "red light", "stop line"],
}


def extract_timestamp_reference(query: str) -> Optional[float]:
    """
    Extract relative timestamp in seconds from queries.
    Examples:
      '00:12' -> 12.0
      '01:05' -> 65.0
      'at 12 seconds' -> 12.0
      'around 8.5s' -> 8.5
      'at 12.4' -> 12.4
    """
    # MM:SS or MM:SS.SS
    m_clock = re.search(r"\b(\d{1,2}):(\d{2})(?:\.(\d+))?\b", query)
    if m_clock:
        mins = int(m_clock.group(1))
        secs = int(m_clock.group(2))
        fraction = float(f"0.{m_clock.group(3)}") if m_clock.group(3) else 0.0
        return mins * 60 + secs + fraction

    # 'around 12.4s' or 'at 12s' or '12.4 seconds'
    m_sec = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)\b", query, re.IGNORECASE)
    if m_sec:
        return float(m_sec.group(1))

    # 'around 12' or 'at 12'
    m_num = re.search(r"(?:around|at|time|timestamp)\s+(\d+(?:\.\d+)?)", query, re.IGNORECASE)
    if m_num:
        return float(m_num.group(1))

    return None


def extract_target_categories(query: str) -> Tuple[List[str], List[str]]:
    """Detect mentioned road users and event types from query."""
    q_lower = query.lower()
    matched_users = []
    for cat, kws in ROAD_USER_KEYWORDS.items():
        if any(kw in q_lower for kw in kws):
            matched_users.append(cat)

    matched_events = []
    for ev_type, kws in EVENT_KEYWORDS.items():
        if any(kw in q_lower for kw in kws):
            matched_events.append(ev_type)

    return matched_users, matched_events


def compute_temporal_proximity_score(
    record_t: float, target_t: Optional[float], tau: float = 3.0
) -> float:
    """Exponential decay kernel for temporal proximity: exp(-|t - t_target| / tau)."""
    if target_t is None:
        return 0.5
    delta = abs(record_t - target_t)
    return math.exp(-delta / tau)


def compute_lexical_similarity(query_tokens: List[str], text: str) -> float:
    """Compute normalized token overlap score between query and record text."""
    if not query_tokens:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for tok in query_tokens if tok in text_lower)
    return hits / max(len(query_tokens), 1)


class RetrievalEngine:
    """Dual-mode evidence retrieval engine: Keyword-Only and Temporal/Context-Aware."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def retrieve_keyword_only(
        self,
        query: str,
        scene_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Baseline: Keyword / FTS lexical retrieval without temporal proximity scoring.
        """
        # Try FTS5 first
        fts_results = search_evidence_fts(query, scene_id=scene_id, limit=top_k * 2, db_path=self.db_path)
        if fts_results:
            results = fts_results[:top_k]
            for r in results:
                r["retrieval_mode"] = "keyword_only"
                r["temporal_score"] = 0.0
                r["composite_score"] = round(1.0 / (1.0 + abs(r.get("bm25_rank", 1.0))), 3)
            return results

        # Fallback to token matching across all records
        all_recs = query_evidence(scene_id=scene_id, limit=500, db_path=self.db_path)
        q_tokens = [tok for tok in re.findall(r"\w+", query.lower()) if len(tok) > 2]

        scored = []
        for rec in all_recs:
            combined_text = f"{rec['observation_description']} {rec['road_user_category']} {rec['event_type']} {rec['road_context']}"
            score = compute_lexical_similarity(q_tokens, combined_text)
            if score > 0.0:
                rec_copy = dict(rec)
                rec_copy["retrieval_mode"] = "keyword_only"
                rec_copy["composite_score"] = round(score, 3)
                rec_copy["temporal_score"] = 0.0
                scored.append(rec_copy)

        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        return scored[:top_k]

    def retrieve_temporal_context_aware(
        self,
        query: str,
        scene_id: Optional[str] = None,
        top_k: int = 5,
        time_window_padding_s: float = 4.0,
    ) -> List[Dict[str, Any]]:
        """
        Research Pipeline: Temporal & Context-Aware Retrieval.
        Combines:
        - Temporal window constraint (if timestamp mentioned)
        - Exponential temporal proximity decay
        - Road-user and event category semantic priors
        - BM25 / token overlap score
        """
        target_t = extract_timestamp_reference(query)
        target_users, target_events = extract_target_categories(query)
        q_tokens = [tok for tok in re.findall(r"\w+", query.lower()) if len(tok) > 2]

        # Time bounds
        t_min = (target_t - time_window_padding_s) if target_t is not None else None
        t_max = (target_t + time_window_padding_s) if target_t is not None else None

        # Fetch candidate records within broad window or scene
        candidates = query_evidence(
            scene_id=scene_id,
            time_min_s=t_min,
            time_max_s=t_max,
            limit=200,
            db_path=self.db_path,
        )

        # If strict time window returned too few results, expand candidates
        if len(candidates) < top_k and target_t is not None:
            candidates = query_evidence(scene_id=scene_id, limit=200, db_path=self.db_path)

        scored: List[Dict[str, Any]] = []
        for rec in candidates:
            # 1. Lexical score
            combined_text = f"{rec['observation_description']} {rec['road_user_category']} {rec['event_type']} {rec['road_context']}"
            lexical_score = compute_lexical_similarity(q_tokens, combined_text)

            # 2. Temporal proximity score
            rec_t = float(rec["timestamp_relative_s"])
            temporal_score = compute_temporal_proximity_score(rec_t, target_t, tau=3.5)

            # 3. Context category bonuses
            category_bonus = 0.0
            if target_users and rec["road_user_category"] in target_users:
                category_bonus += 0.25
            if target_events and rec["event_type"] in target_events:
                category_bonus += 0.25

            # 4. Composite ranking score
            # If target timestamp exists, weight temporal proximity heavily (0.45)
            if target_t is not None:
                composite = (0.35 * lexical_score) + (0.45 * temporal_score) + (0.20 * category_bonus)
            else:
                composite = (0.65 * lexical_score) + (0.35 * category_bonus)

            rec_copy = dict(rec)
            rec_copy["retrieval_mode"] = "temporal_context_aware"
            rec_copy["lexical_score"] = round(lexical_score, 3)
            rec_copy["temporal_score"] = round(temporal_score, 3)
            rec_copy["category_bonus"] = round(category_bonus, 3)
            rec_copy["composite_score"] = round(composite, 3)
            rec_copy["time_delta_s"] = round(abs(rec_t - target_t), 2) if target_t is not None else None
            scored.append(rec_copy)

        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        return scored[:top_k]

    def compare_retrieval(
        self,
        query: str,
        scene_id: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Run both retrieval modes and return side-by-side comparison."""
        target_t = extract_timestamp_reference(query)
        kw_results = self.retrieve_keyword_only(query, scene_id=scene_id, top_k=top_k)
        tc_results = self.retrieve_temporal_context_aware(query, scene_id=scene_id, top_k=top_k)

        kw_ids = [r["record_id"] for r in kw_results]
        tc_ids = [r["record_id"] for r in tc_results]

        # Overlap and rank variance
        common_ids = set(kw_ids).intersection(set(tc_ids))
        jaccard_overlap = len(common_ids) / max(len(set(kw_ids + tc_ids)), 1)

        return {
            "query": query,
            "scene_id": scene_id,
            "target_timestamp_s": target_t,
            "keyword_only": kw_results,
            "temporal_context": tc_results,
            "overlap_ratio": round(jaccard_overlap, 3),
            "common_records_count": len(common_ids),
        }
