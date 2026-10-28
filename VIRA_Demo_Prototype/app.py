"""
VIRA — VehicleGPT: Evidence-Guided Road-User Activity Understanding
Professional Automotive Intelligence & Research Prototype Dashboard
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

# Configure page
st.set_page_config(
    page_title="VIRA — VehicleGPT Automotive Intelligence",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Internal module imports
from database import (
    DEFAULT_DB_PATH,
    get_all_scenes,
    get_provenance_stats,
    get_record_by_id,
    init_database,
    query_evidence,
    reset_database,
    search_evidence_fts,
)
from evaluation import BenchmarkEvaluator, compute_retrieval_metrics
from grounding import evaluate_grounding
from ingestion import (
    REPO_ROOT,
    TIAND_CAM_FRONT_REL_PATH,
    build_and_export_demonstration_dataset,
    ingest_user_csv,
)
from retrieval import RetrievalEngine, extract_target_categories, extract_timestamp_reference
from slm_client import RECOMMENDED_MODELS, SLMClient, check_ollama_status

# Ensure DB initialized
if not os.path.isfile(DEFAULT_DB_PATH):
    init_database(DEFAULT_DB_PATH)
    build_and_export_demonstration_dataset(DEFAULT_DB_PATH)

# ==========================================
# CUSTOM PROFESSIONAL CSS STYLING
# ==========================================
CUSTOM_CSS = """
<style>
/* Base Dark Automotive Theme */
.stApp {
    background-color: #0b1120;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    color: #f8fafc !important;
    font-weight: 600;
    letter-spacing: -0.02em;
}

/* Metric Cards */
.vira-metric-card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.vira-metric-value {
    font-size: 28px;
    font-weight: 700;
    color: #38bdf8;
    line-height: 1.2;
}
.vira-metric-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
    margin-bottom: 4px;
}
.vira-metric-subtext {
    font-size: 12px;
    color: #64748b;
    margin-top: 4px;
}

/* Badges */
.badge-observed {
    background-color: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    display: inline-block;
}
.badge-inferred {
    background-color: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.3);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    display: inline-block;
}
.badge-tiand {
    background-color: rgba(6, 182, 212, 0.15);
    color: #22d3ee;
    border: 1px solid rgba(6, 182, 212, 0.3);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    display: inline-block;
}
.badge-synthetic {
    background-color: rgba(148, 163, 184, 0.15);
    color: #94a3b8;
    border: 1px solid rgba(148, 163, 184, 0.3);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    display: inline-block;
}

/* Evidence Card */
.evidence-card {
    background-color: #131d31;
    border: 1px solid #22324e;
    border-left: 4px solid #0284c7;
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 12px;
}
.evidence-card:hover {
    border-color: #38bdf8;
}
.evidence-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.evidence-id {
    font-family: monospace;
    font-size: 13px;
    font-weight: 700;
    color: #38bdf8;
}
.evidence-time {
    font-family: monospace;
    font-size: 12px;
    color: #94a3b8;
}

/* Grounding banner */
.grounding-box-valid {
    background-color: rgba(16, 185, 129, 0.1);
    border: 1px solid #10b981;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
}
.grounding-box-warning {
    background-color: rgba(245, 158, 11, 0.1);
    border: 1px solid #f59e0b;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==========================================
# SIDEBAR NAVIGATION & SYSTEM STATUS
# ==========================================
def render_sidebar():
    st.sidebar.markdown(
        """
        <div style="padding: 4px 0 16px 0;">
            <div style="font-size: 18px; font-weight: 800; color: #38bdf8; letter-spacing: -0.03em;">
                VIRA // VehicleGPT
            </div>
            <div style="font-size: 12px; color: #94a3b8; line-height: 1.3;">
                Evidence-Guided Road-User Activity Understanding (Indian Environment)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Navigation menu
    sections = [
        "Overview Dashboard",
        "Scene Explorer",
        "Event Timeline",
        "Evidence Store",
        "VehicleGPT Assistant",
        "Evaluation & Research",
    ]
    selected_page = st.sidebar.radio("SYSTEM NAVIGATION", sections, index=0)

    st.sidebar.markdown("---")

    # Local SLM Status Box
    st.sidebar.markdown("#### LOCAL SLM STATUS")
    ollama_status = check_ollama_status()
    if ollama_status["online"]:
        st.sidebar.success(f"Ollama: Online ({len(ollama_status['models'])} models)")
        default_idx = 0
        model_choice = st.sidebar.selectbox(
            "Active Model",
            options=ollama_status["models"],
            index=default_idx,
            help="Select an installed local instruction-tuned model.",
        )
    else:
        st.sidebar.error("Ollama: Offline (Not Running)")
        st.sidebar.caption("Ollama daemon not detected on `localhost:11434`.")
        model_choice = "llama3.2:3b (offline)"

    # Dataset Provenance summary in sidebar
    stats = get_provenance_stats()
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### PROVENANCE MONITOR")
    st.sidebar.markdown(
        f"""
        <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
            <div>• Genuine TIAND: <strong style="color: #22d3ee;">{stats['tiand_count']}</strong> ({stats['tiand_pct']}%)</div>
            <div>• Synthetic Demo: <strong style="color: #94a3b8;">{stats['synthetic_count']}</strong> ({stats['synthetic_pct']}%)</div>
            <div>• User Uploaded: <strong>{stats['uploaded_count']}</strong> ({stats['uploaded_pct']}%)</div>
            <div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid #334155;">
                • Total Records: <strong>{stats['total_records']}</strong> across <strong>{stats['total_scenes']}</strong> scenes
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Safe Database reload
    with st.sidebar.expander("Database Maintenance", expanded=False):
        if st.button("Reload Default Dataset", use_container_width=True):
            reset_database()
            build_and_export_demonstration_dataset()
            st.success("Reloaded demo database!")
            st.rerun()

    return selected_page, ollama_status, model_choice


# ==========================================
# SECTION 1: OVERVIEW DASHBOARD
# ==========================================
def render_overview(ollama_status: Dict[str, Any], active_model: str):
    st.markdown("## Overview Dashboard")
    st.markdown(
        "Real-time operational summary of loaded road scenes, multimodal evidence store, "
        "road-user observations, and local Small Language Model (SLM) status."
    )

    stats = get_provenance_stats()

    # Metric Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Total Scenes</div>
                <div class="vira-metric-value">{stats['total_scenes']}</div>
                <div class="vira-metric-subtext">TIAND + Synthetic Demonstrations</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Total Evidence Records</div>
                <div class="vira-metric-value">{stats['total_records']}</div>
                <div class="vira-metric-subtext">Timestamped & Indexed in SQLite</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Observed vs Inferred</div>
                <div class="vira-metric-value">{stats['observed_count']} <span style="font-size: 16px; color: #94a3b8;">/ {stats['inferred_count']}</span></div>
                <div class="vira-metric-subtext">Strict Epistemic Separation</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        status_color = "#34d399" if ollama_status["online"] else "#f87171"
        status_text = "ONLINE" if ollama_status["online"] else "OFFLINE"
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Local SLM Engine</div>
                <div class="vira-metric-value" style="color: {status_color}; font-size: 20px;">{status_text}</div>
                <div class="vira-metric-subtext">{active_model}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Provenance and Road User Breakdown
    col_prov, col_users = st.columns([1, 1])

    with col_prov:
        st.markdown("### Data Provenance Breakdown")
        df_prov = pd.DataFrame(
            [
                {"Provenance": "Genuine TIAND Multimodal", "Records": stats["tiand_count"], "Share": f"{stats['tiand_pct']}%"},
                {"Provenance": "Synthetic Demonstration Data", "Records": stats["synthetic_count"], "Share": f"{stats['synthetic_pct']}%"},
                {"Provenance": "User Uploaded", "Records": stats["uploaded_count"], "Share": f"{stats['uploaded_pct']}%"},
            ]
        )
        st.dataframe(df_prov, use_container_width=True, hide_index=True)

        st.info(
            "**Data Integrity Principle:** Genuine TIAND sensor measurements (NovAtel OEM7 INSPVA GNSS and front camera frames) "
            "are preserved without fabricating unobserved fields. Simulated Indian traffic scenarios (auto-rickshaw cut-ins, "
            "pedestrian interactions) are strictly labeled as `synthetic_demo_data`."
        )

    with col_users:
        st.markdown("### Road-User Category Distribution")
        if stats["road_user_counts"]:
            df_users = pd.DataFrame(
                list(stats["road_user_counts"].items()), columns=["Road User Category", "Observations"]
            )
            st.dataframe(df_users, use_container_width=True, hide_index=True)
        else:
            st.write("No road-user observations found.")

        st.markdown("### Top Detected Event Types")
        if stats["event_counts"]:
            df_ev = pd.DataFrame(
                list(stats["event_counts"].items())[:5], columns=["Event Type", "Count"]
            )
            st.dataframe(df_ev, use_container_width=True, hide_index=True)

    # Loaded Scenes Summary Table
    st.markdown("### Active Road Scenes")
    scenes = get_all_scenes()
    if scenes:
        df_scenes = pd.DataFrame(scenes)[
            ["scene_id", "name", "location", "duration_s", "data_origin", "record_count", "observed_count", "inferred_count"]
        ]
        df_scenes.columns = [
            "Scene ID",
            "Scene Name",
            "Location",
            "Duration (s)",
            "Data Origin",
            "Total Records",
            "Observed",
            "Inferred",
        ]
        st.dataframe(df_scenes, use_container_width=True, hide_index=True)


# ==========================================
# SECTION 2: SCENE EXPLORER
# ==========================================
def render_scene_explorer():
    st.markdown("## Scene Explorer")
    st.markdown("Inspect spatial-temporal road scenes, camera frame sequences, and synchronized vehicle telemetry.")

    scenes = get_all_scenes()
    if not scenes:
        st.warning("No scenes available in database.")
        return

    scene_map = {s["scene_id"]: s for s in scenes}
    selected_scene_id = st.selectbox(
        "Select Road Scene",
        options=list(scene_map.keys()),
        format_func=lambda sid: f"{sid} — {scene_map[sid]['name']} [{scene_map[sid]['data_origin']}]",
    )

    scene = scene_map[selected_scene_id]

    # Scene header card
    col_info, col_badge = st.columns([4, 1])
    with col_info:
        st.markdown(f"### {scene['name']}")
        st.markdown(f"**Location:** {scene['location']} | **Context:** {scene['primary_road_context']}")
        st.caption(scene["description"])
    with col_badge:
        if scene["data_origin"] == "TIAND":
            st.markdown('<div class="badge-tiand" style="margin-top: 10px;">GENUINE TIAND DATA</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="badge-synthetic" style="margin-top: 10px;">SYNTHETIC DEMO DATA</div>', unsafe_allow_html=True)

    # Time interval slider
    max_duration = float(scene["duration_s"] or 30.0)
    time_window = st.slider(
        "Select Time Interval (Seconds from Scene Start)",
        min_value=0.0,
        max_value=max_duration,
        value=(0.0, min(15.0, max_duration)),
        step=0.5,
    )

    # Query records in window
    records = query_evidence(
        scene_id=selected_scene_id,
        time_min_s=time_window[0],
        time_max_s=time_window[1],
        limit=100,
    )

    st.markdown(f"**Found {len(records)} evidence observations in window [{time_window[0]:.1f}s — {time_window[1]:.1f}s]**")

    # Visual Inspection Panel
    cam_folder = os.path.join(REPO_ROOT, TIAND_CAM_FRONT_REL_PATH)
    if selected_scene_id == "TIAND_SCENE_03_HYD" and os.path.isdir(cam_folder):
        st.markdown("#### Genuine TIAND Camera Visual Inspection")
        cam_files = sorted([f for f in os.listdir(cam_folder) if f.lower().endswith((".jpg", ".png"))])
        if cam_files:
            frame_idx = st.slider("Scrub Front Camera Frames", 0, len(cam_files) - 1, 0)
            target_file = os.path.join(cam_folder, cam_files[frame_idx])
            col_img, col_frame_info = st.columns([2, 1])
            with col_img:
                st.image(target_file, caption=f"TIAND Front Camera: {cam_files[frame_idx]}", use_container_width=True)
            with col_frame_info:
                st.markdown("**Synchronized Metadata**")
                st.markdown(f"- **Filename:** `{cam_files[frame_idx]}`")
                st.markdown("- **Camera:** Front Center (1280x720 RGB)")
                st.markdown("- **Dataset:** TIAND Multimodal Driving Dataset")
                st.markdown("- **Provenance:** Genuine In-Vehicle Recording")
    else:
        # Telemetry / Scenario Dynamics Plot
        st.markdown("#### Synchronized Scenario Telemetry Dynamics")
        if records:
            chart_data = []
            for r in records:
                meta = {}
                try:
                    meta = json.loads(r.get("metadata_json") or "{}")
                except Exception:
                    pass
                chart_data.append({
                    "Time (s)": r["timestamp_relative_s"],
                    "Speed (km/h)": meta.get("speed_kmh", 35.0),
                    "Event": r["event_type"],
                    "Confidence": r["confidence"],
                })
            df_chart = pd.DataFrame(chart_data)
            st.line_chart(df_chart.set_index("Time (s)")[["Speed (km/h)"]])

    # Observations in current window
    st.markdown("#### Observations in Window")
    for r in records:
        status_badge = (
            '<span class="badge-observed">OBSERVED</span>'
            if r["status"] == "observed"
            else '<span class="badge-inferred">INFERRED</span>'
        )
        origin_badge = (
            '<span class="badge-tiand">TIAND</span>'
            if r["data_origin"] == "TIAND"
            else '<span class="badge-synthetic">SIMULATED</span>'
        )

        st.markdown(
            f"""
            <div class="evidence-card">
                <div class="evidence-header">
                    <div>
                        <span class="evidence-id">{r['record_id']}</span> &nbsp;
                        {status_badge} &nbsp; {origin_badge}
                    </div>
                    <div class="evidence-time">t = {r['timestamp_relative_s']:.1f}s | {r['event_type']}</div>
                </div>
                <div style="font-size: 14px; color: #f1f5f9; margin-bottom: 6px;">
                    {r['observation_description']}
                </div>
                <div style="font-size: 12px; color: #94a3b8;">
                    <strong>Road User:</strong> {r['road_user_category']} | <strong>Sensor:</strong> {r['source_sensor']} | <strong>Ref:</strong> {r.get('evidence_reference', 'N/A')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==========================================
# SECTION 3: EVENT TIMELINE
# ==========================================
def render_event_timeline():
    st.markdown("## Event Timeline")
    st.markdown("Chronological progression of detected road-user interactions, state transitions, and vehicle events.")

    scenes = get_all_scenes()
    scene_ids = [s["scene_id"] for s in scenes]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        scene_filter = st.selectbox("Scene Filter", options=["All Scenes"] + scene_ids)
    with c2:
        event_filter = st.selectbox(
            "Event Type Filter",
            options=["All Events", "CUT_IN", "SUDDEN_BRAKING", "PEDESTRIAN_INTERACTION", "ROAD_USER_DETECTION", "NEAR_COLLISION", "EGO_TELEMETRY"],
        )
    with c3:
        status_filter = st.selectbox("Status Filter", options=["All Statuses", "observed", "inferred"])
    with c4:
        user_filter = st.selectbox(
            "Road User Filter",
            options=["All Road Users", "auto_rickshaw", "pedestrian", "two_wheeler", "bus", "ego_vehicle"],
        )

    # Fetch filtered
    target_scene = None if scene_filter == "All Scenes" else scene_filter
    target_ev = None if event_filter == "All Events" else event_filter
    target_st = None if status_filter == "All Statuses" else status_filter
    target_ru = None if user_filter == "All Road Users" else user_filter

    records = query_evidence(
        scene_id=target_scene,
        event_type=target_ev,
        status=target_st,
        road_user_category=target_ru,
        limit=200,
    )

    st.markdown(f"Showing **{len(records)}** events matching criteria.")

    for r in records:
        mins = int(r["timestamp_relative_s"] // 60)
        secs = r["timestamp_relative_s"] % 60
        clock_str = f"{mins:02d}:{secs:04.1f}"

        status_badge = (
            '<span class="badge-observed">OBSERVED FACT</span>'
            if r["status"] == "observed"
            else '<span class="badge-inferred">INFERRED INTERPRETATION</span>'
        )
        origin_badge = (
            '<span class="badge-tiand">TIAND</span>'
            if r["data_origin"] == "TIAND"
            else '<span class="badge-synthetic">SIMULATED</span>'
        )

        st.markdown(
            f"""
            <div class="evidence-card" style="border-left-color: {'#10b981' if r['status'] == 'observed' else '#f59e0b'};">
                <div class="evidence-header">
                    <div>
                        <span class="evidence-id">{r['record_id']}</span> &nbsp;
                        {status_badge} &nbsp; {origin_badge}
                    </div>
                    <div class="evidence-time" style="font-weight: 600; color: #38bdf8;">
                        ⏱ {clock_str} ({r['timestamp_relative_s']:.1f}s)
                    </div>
                </div>
                <div style="font-size: 14px; color: #f8fafc; font-weight: 500; margin-bottom: 6px;">
                    {r['observation_description']}
                </div>
                <div style="font-size: 12px; color: #94a3b8; display: flex; gap: 16px;">
                    <span><strong>Event:</strong> {r['event_type']}</span>
                    <span><strong>Road User:</strong> {r['road_user_category']}</span>
                    <span><strong>Sensor:</strong> {r['source_sensor']}</span>
                    <span><strong>Confidence:</strong> {r['confidence']:.2f}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==========================================
# SECTION 4: EVIDENCE STORE
# ==========================================
def render_evidence_store():
    st.markdown("## Evidence Store")
    st.markdown("Searchable, filterable local SQLite evidence catalog with full-text search and detailed metadata inspection.")

    c_search, c_origin, c_status = st.columns([3, 1, 1])
    with c_search:
        search_query = st.text_input("Full-Text Search", placeholder="e.g., auto-rickshaw, deceleration, bus blind spot, GNSS...")
    with c_origin:
        origin_filter = st.selectbox("Provenance", ["All Origins", "TIAND", "synthetic_demo_data", "uploaded_data"])
    with c_status:
        status_filter = st.selectbox("Status", ["All", "observed", "inferred"])

    target_origin = None if origin_filter == "All Origins" else origin_filter
    target_status = None if status_filter == "All" else status_filter

    if search_query.strip():
        records = search_evidence_fts(search_query, limit=100)
    else:
        records = query_evidence(
            data_origin=target_origin,
            status=target_status,
            limit=200,
        )

    if records:
        df = pd.DataFrame(records)[
            [
                "record_id",
                "scene_id",
                "timestamp_relative_s",
                "event_type",
                "road_user_category",
                "observation_description",
                "data_origin",
                "status",
                "confidence",
                "source_sensor",
            ]
        ]
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Download CSV
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Filtered Evidence (CSV)",
            data=csv_data,
            file_name=f"vira_evidence_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

        # Record Inspector Drawer
        st.markdown("### Record Detail Inspector")
        record_ids = [r["record_id"] for r in records]
        inspect_id = st.selectbox("Select Record ID to Inspect", options=record_ids)
        if inspect_id:
            rec = get_record_by_id(inspect_id)
            if rec:
                col_meta1, col_meta2 = st.columns(2)
                with col_meta1:
                    st.markdown(f"**Record ID:** `{rec['record_id']}`")
                    st.markdown(f"**Scene ID:** `{rec['scene_id']}`")
                    st.markdown(f"**Relative Time:** `{rec['timestamp_relative_s']} s`")
                    st.markdown(f"**Event Type:** `{rec['event_type']}`")
                    st.markdown(f"**Road User:** `{rec['road_user_category']}`")
                    st.markdown(f"**Status:** `{rec['status']}`")
                with col_meta2:
                    st.markdown(f"**Data Origin:** `{rec['data_origin']}`")
                    st.markdown(f"**Confidence:** `{rec['confidence']}`")
                    st.markdown(f"**Source Sensor:** `{rec['source_sensor']}`")
                    st.markdown(f"**Evidence Reference:** `{rec.get('evidence_reference')}`")
                    st.markdown(f"**Road Context:** `{rec['road_context']}`")

                st.markdown("**Observation Description:**")
                st.info(rec["observation_description"])

                st.markdown("**Structured Metadata JSON:**")
                try:
                    meta_dict = json.loads(rec.get("metadata_json") or "{}")
                    st.json(meta_dict)
                except Exception:
                    st.text(rec.get("metadata_json"))
    else:
        st.warning("No records matched the selected query.")

    # CSV Upload Feature
    st.markdown("---")
    st.markdown("### Import User CSV Data")
    uploaded_file = st.file_uploader("Upload custom road-user observation CSV", type=["csv"])
    if uploaded_file is not None:
        if st.button("Process and Ingest CSV"):
            count, msg = ingest_user_csv(uploaded_file)
            st.success(msg)
            st.rerun()


# ==========================================
# SECTION 5: VEHICLEGPT ASSISTANT
# ==========================================
def render_assistant(ollama_status: Dict[str, Any], active_model: str):
    st.markdown("## VehicleGPT Assistant")
    st.markdown(
        "Evidence-guided conversational QA powered by local SLM inference. "
        "Every claim cites supporting record IDs and separates direct observations from inferred intent."
    )

    # Retrieval and Client setup
    engine = RetrievalEngine()
    slm_client = SLMClient(model_name=active_model)

    # Predefined sample prompts for presentation demo
    demo_queries = [
        "What road-user activity occurred around 00:12, and what evidence supports your interpretation?",
        "What events occurred immediately before and after the sudden braking event?",
        "What evidence supports the pedestrian interaction around 00:08?",
        "Can we determine the exact psychological intent or thinking of the driver when the vehicle braked?",
        "Did an emergency ambulance pass the vehicle at 00:45?",
        "What was the ego-vehicle speed and heading in the genuine TIAND Hyderabad corridor at 00:05?",
    ]

    selected_demo_q = st.selectbox("Presentation Demonstration Queries", ["-- Select a Predefined Scenario Query --"] + demo_queries)

    user_query = st.text_input(
        "Or enter a custom question:",
        value=selected_demo_q if selected_demo_q != "-- Select a Predefined Scenario Query --" else "",
        placeholder="e.g., What happened around 00:12?",
    )

    col_btn, col_scene, col_mock = st.columns([1, 2, 2])
    with col_btn:
        ask_button = st.button("Generate Grounded Answer", type="primary")
    with col_scene:
        scenes = get_all_scenes()
        scene_choices = ["All Scenes"] + [s["scene_id"] for s in scenes]
        target_scene_filter = st.selectbox("Scope to Scene", scene_choices, index=0)
    with col_mock:
        allow_mock = st.checkbox(
            "Enable Deterministic Fallback Mock (if Ollama offline)",
            value=True,
            help="Allows dry-run QA testing with labeled deterministic mock responses when local Ollama daemon is offline.",
        )

    if ask_button and user_query.strip():
        scene_id_param = None if target_scene_filter == "All Scenes" else target_scene_filter

        with st.spinner("Retrieving evidence and running Small Language Model inference..."):
            # 1. Retrieval
            retrieved = engine.retrieve_temporal_context_aware(
                user_query, scene_id=scene_id_param, top_k=5
            )

            # 2. SLM Inference
            slm_result = slm_client.generate_grounded_answer(
                query=user_query,
                evidence_records=retrieved,
                allow_offline_mock=allow_mock,
            )

            # 3. Grounding evaluation
            is_abstention_q = any(
                kw in user_query.lower() for kw in ["intent", "driver thinking", "ambulance", "cattle", "00:45"]
            )
            grounding_res = evaluate_grounding(
                generated_answer=slm_result["answer"],
                retrieved_evidence=retrieved,
                is_expected_abstention_query=is_abstention_q,
            )

        # Display SLM Status & Metadata
        st.markdown("### VehicleGPT Response")

        if slm_result["status"] == "OLLAMA_OFFLINE":
            st.error(slm_result["error"])
            return

        # Grounding Badge Banner
        verdict = grounding_res["verdict"]
        if verdict in ("FULLY_GROUNDED", "VALID_ABSTENTION"):
            st.markdown(
                f"""
                <div class="grounding-box-valid">
                    <strong>✓ GROUNDING VERDICT: {verdict}</strong><br/>
                    {grounding_res['explanation']} (Citation Precision: {grounding_res['citation_precision'] * 100:.0f}%, Latency: {slm_result['latency_ms']} ms)
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="grounding-box-warning">
                    <strong>⚠ GROUNDING NOTICE: {verdict}</strong><br/>
                    {grounding_res['explanation']} (Citation Precision: {grounding_res['citation_precision'] * 100:.0f}%)
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Answer Box
        st.markdown(slm_result["answer"])

        st.caption(
            f"**Model:** `{slm_result.get('model_used')}` | "
            f"**Engine Type:** `{'Real Local SLM' if slm_result.get('is_real_slm') else 'Fallback Dry-Run Mock'}` | "
            f"**Latency:** `{slm_result['latency_ms']} ms` | "
            f"**Retrieved Evidence Records:** `{len(retrieved)}`"
        )

        # Retrieved Evidence Cards
        st.markdown("#### Retrieved Supporting Evidence Package")
        if retrieved:
            for r in retrieved:
                status_badge = (
                    '<span class="badge-observed">OBSERVED</span>'
                    if r["status"] == "observed"
                    else '<span class="badge-inferred">INFERRED</span>'
                )
                origin_badge = (
                    '<span class="badge-tiand">TIAND</span>'
                    if r["data_origin"] == "TIAND"
                    else '<span class="badge-synthetic">SIMULATED</span>'
                )

                st.markdown(
                    f"""
                    <div class="evidence-card">
                        <div class="evidence-header">
                            <div>
                                <span class="evidence-id">[{r['record_id']}]</span> &nbsp;
                                {status_badge} &nbsp; {origin_badge}
                            </div>
                            <div class="evidence-time">
                                t = {r['timestamp_relative_s']:.1f}s | Score: {r.get('composite_score', 0.0):.2f} (Temporal: {r.get('temporal_score', 0.0):.2f})
                            </div>
                        </div>
                        <div style="font-size: 14px; color: #f8fafc; margin-bottom: 6px;">
                            {r['observation_description']}
                        </div>
                        <div style="font-size: 12px; color: #94a3b8;">
                            <strong>Event:</strong> {r['event_type']} | <strong>Sensor:</strong> {r['source_sensor']} | <strong>Ref:</strong> {r.get('evidence_reference', 'N/A')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No supporting evidence retrieved.")

        # Prompt Inspector Drawer
        with st.expander("Inspect Raw Prompt Sent to SLM (Research Reproducibility)", expanded=False):
            st.code(slm_result["prompt_sent"], language="markdown")


# ==========================================
# SECTION 6: EVALUATION & RESEARCH METRICS
# ==========================================
def render_evaluation():
    st.markdown("## Evaluation & Research Metrics")
    st.markdown(
        "Quantitative evaluation suite evaluating evidence retrieval Precision@K, "
        "temporal ranking superiority over keyword baseline, and SLM grounding accuracy."
    )

    evaluator = BenchmarkEvaluator()

    col_btn, _ = st.columns([2, 3])
    with col_btn:
        run_eval = st.button("Run Full Benchmark Evaluation", type="primary")

    if run_eval or "eval_results" not in st.session_state:
        with st.spinner("Running retrieval and pipeline benchmark suite..."):
            ret_metrics = evaluator.run_retrieval_evaluation(k=5)
            full_metrics = evaluator.run_full_pipeline_evaluation(allow_offline_mock=True)
            st.session_state["eval_results"] = {
                "ret": ret_metrics,
                "full": full_metrics,
            }

    data = st.session_state["eval_results"]
    ret_res = data["ret"]
    full_res = data["full"]

    # Metric Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Temporal Precision@5</div>
                <div class="vira-metric-value">{ret_res['mean_tc_precision_at_5']:.3f}</div>
                <div class="vira-metric-subtext">Context-Aware Pipeline</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Keyword Precision@5</div>
                <div class="vira-metric-value" style="color: #94a3b8;">{ret_res['mean_kw_precision_at_5']:.3f}</div>
                <div class="vira-metric-subtext">FTS Baseline</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Relative Improvement</div>
                <div class="vira-metric-value" style="color: #34d399;">+{ret_res['precision_improvement_pct']}%</div>
                <div class="vira-metric-subtext">Temporal Proximity Gain</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"""
            <div class="vira-metric-card">
                <div class="vira-metric-label">Grounding Compliance</div>
                <div class="vira-metric-value">{full_res['overall_grounding_rate_pct']}%</div>
                <div class="vira-metric-subtext">Citation & Abstention</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Retrieval Comparison Table
    st.markdown("### Retrieval Comparison: Keyword Baseline vs Temporal/Context Aware")
    st.caption("Side-by-side evaluation across standard benchmark test cases:")

    df_cases = pd.DataFrame(ret_res["case_details"])[
        ["test_id", "query", "category", "kw_precision", "tc_precision", "kw_latency_ms", "tc_latency_ms"]
    ]
    df_cases.columns = [
        "Test ID",
        "Benchmark Query",
        "Category",
        "Keyword Prec@5",
        "Temporal Prec@5",
        "Keyword Latency (ms)",
        "Temporal Latency (ms)",
    ]
    st.dataframe(df_cases, use_container_width=True, hide_index=True)

    # Grounding & Abstention Table
    st.markdown("### Grounding & Abstention Verification")
    df_ground = pd.DataFrame(full_res["eval_records"])[
        [
            "test_id",
            "category",
            "grounding_verdict",
            "citation_precision",
            "valid_citations",
            "has_abstained",
            "expected_abstention",
            "latency_ms",
        ]
    ]
    st.dataframe(df_ground, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.info(full_res["methodology_disclaimer"])


# ==========================================
# MAIN APPLICATION CONTROLLER
# ==========================================
def main():
    selected_page, ollama_status, active_model = render_sidebar()

    if selected_page == "Overview Dashboard":
        render_overview(ollama_status, active_model)
    elif selected_page == "Scene Explorer":
        render_scene_explorer()
    elif selected_page == "Event Timeline":
        render_event_timeline()
    elif selected_page == "Evidence Store":
        render_evidence_store()
    elif selected_page == "VehicleGPT Assistant":
        render_assistant(ollama_status, active_model)
    elif selected_page == "Evaluation & Research":
        render_evaluation()


if __name__ == "__main__":
    main()
