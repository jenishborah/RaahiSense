# VIRA — VehicleGPT: Evidence-Guided Road-User Activity Understanding

**A Working Demo Prototype for M.Tech Data Science & Ideathon Presentation**  
*Focused on the Unstructured, High-Density Indian Driving Environment*

---

## 1. Project Overview

**VIRA (VehicleGPT)** is an evidence-guided road-scene understanding platform developed as part of an M.Tech Data Science project. While contemporary autonomous driving platforms focus on real-time vehicle control, VIRA addresses **historical automotive intelligence**: extracting, structuring, indexing, and explaining timestamped multi-sensor observations through a resource-constrained local Small Language Model (SLM).

In heterogeneous Indian traffic environments (featuring high densities of two-wheelers, auto-rickshaws, informal lane merges, and mid-block pedestrian crossings), standard keyword searches fail to capture temporal causality. VIRA introduces a **temporally indexed SQLite evidence store** coupled with a **temporal-proximity retrieval engine** and an **epistemic grounding framework** that separates direct observations from inferred intent.

---

## 2. System Architecture

```text
       Multimodal Input Sources
  ┌─────────────────┬─────────────────┐
  │ Genuine TIAND   │ Synthetic Demo  │
  │ GNSS & Cameras  │ Indian Traffic  │
  └────────┬────────┴────────┬────────┘
           │                 │
           ▼                 ▼
   Modular Ingestion & Provenance Engine
           │ (TIAND vs synthetic_demo_data)
           ▼
    SQLite Structured Evidence Store
           │ (FTS5 + B-Tree Temporal Indexes)
           ▼
  Dual-Mode Evidence Retrieval Engine
  ┌───────────────────────────────────┐
  │ 1. Keyword FTS Baseline           │
  │ 2. Temporal & Context-Aware RAG   │
  └─────────────────┬─────────────────┘
                    ▼
     Constrained Prompt Synthesis
                    ▼
   Local Small Language Model (Ollama)
           (Llama 3.2 3B / Qwen 2.5 3B)
                    ▼
   Grounding & Verification Inspector
  (Citation Check, Abstention, Observed vs Inferred)
                    ▼
    Automotive Intelligence Dashboard
```

---

## 3. Data Integrity & Provenance Policy

VIRA enforces strict epistemic and provenance transparency throughout the pipeline:

| Provenance Tag | Source Description | Handling Rule |
| :--- | :--- | :--- |
| **`TIAND`** | Genuine telemetry from the Indian TIAND dataset (`NovAtel OEM7 INSPVA` GNSS & Front Camera frames). | Ingested directly. Missing sensor signals or annotations are **never fabricated** or disguised as real. |
| **`synthetic_demo_data`** | Simulated high-density scenarios (Auto-rickshaw sudden cut-in, mid-block pedestrian crossing). | Explicitly tagged across all database tables, query results, exports, and UI badges. |
| **`uploaded_data`** | User-imported custom CSV telemetry records. | Tagged as custom external data. |

### Observed Facts vs. Inferred Interpretations
- **`observed`**: Direct physical measurements (e.g., IMU deceleration spike of $-3.8\text{ m/s}^2$, camera bounding box detection of auto-rickshaw at $2.4\text{m}$ headway).
- **`inferred`**: Causal hypotheses (e.g., "Ego braking provoked by auto-rickshaw cut-in"). Driver psychological thoughts are explicitly marked as unobserved.

---

## 4. Quick Start: Windows Setup & Run

### Prerequisites
- Python 3.10+ (tested on Python 3.12 64-bit on Windows)
- Modern web browser (Chrome, Edge, Firefox)

### Step 1: Install Dependencies
From the repository root or inside `VIRA_Demo_Prototype/`:
```powershell
pip install -r VIRA_Demo_Prototype/requirements.txt
```

### Step 2: Initialize Database & Load Bundled Data
```powershell
python VIRA_Demo_Prototype/scripts/initialize_database.py --reset
```
*This populates the SQLite evidence store with 31 genuine TIAND observations and 16 synthetic Indian traffic demonstration records.*

### Step 3: Launch the Prototype Dashboard
```powershell
streamlit run VIRA_Demo_Prototype/app.py
```
The dashboard will open automatically in your browser at `http://localhost:8501`.

---

## 5. Setting Up the Real Local SLM (Ollama)

VIRA connects to a local Small Language Model using **Ollama** so inference runs completely locally without external API costs or cloud dependencies.

### Step 1: Install Ollama
Download and run the Windows installer from [ollama.com](https://ollama.com/download), or install via winget:
```powershell
winget install Ollama.Ollama
```

### Step 2: Pull a Laptop-Friendly 3B Model
Open PowerShell and download a recommended 3B instruction-tuned model:
```powershell
ollama pull llama3.2:3b
# Or alternatively:
ollama pull qwen2.5:3b
```

### Step 3: Verify Ollama Daemon
Ensure Ollama is running. In PowerShell:
```powershell
curl http://localhost:11434/api/tags
```
Once active, the VIRA dashboard sidebar will immediately display:  
`Ollama: Online (1 models)` and allow you to select `llama3.2:3b`.

> **Offline Dry-Run Fallback:** If Ollama is not yet installed or the laptop is running on battery without GPU support, VIRA includes an explicitly labeled **Deterministic Fallback Mock** toggle in the assistant. This allows full end-to-end presentation dry-runs while clearly indicating `[MOCK / OFFLINE FALLBACK - NOT A REAL SLM]`.

---

## 6. Predefined 2-Minute Presentation Scenario

Follow this exact walkthrough during your presentation:

1. **Open Overview Dashboard:**
   - Highlight the metric cards: Total Scenes (3), Total Evidence Records (47), Provenance distribution (66% genuine TIAND, 34% synthetic demo).
2. **Open Scene Explorer:**
   - Select `DEMO_INDIAN_JUNCTION_01` ("Bengaluru Outer Ring Road Mixed Junction").
   - Move time slider to `[10.0s — 15.0s]`.
   - Show the emergency deceleration telemetry graph dropping from $40.5\text{ km/h}$ to $18.2\text{ km/h}$.
   - Switch to `TIAND_SCENE_03_HYD` and scrub through the real front camera images recorded in Hyderabad.
3. **Open VehicleGPT Assistant:**
   - Select predefined query:  
     *“What road-user activity occurred around 00:12, and what evidence supports your interpretation?”*
   - Click **Generate Grounded Answer**.
   - Show the generated answer citing `[REC-SIM-010]`, `[REC-SIM-011]`, and `[REC-SIM-012]`.
   - Point out the green badge: `GROUNDING VERDICT: FULLY_GROUNDED (Citation Precision: 100%)`.
   - Point out the separation between **Directly Observed Facts** and **Inferred Interpretations**.
4. **Demonstrate Appropriate Abstention:**
   - Select query:  
     *“Can we determine the exact psychological intent or thinking of the driver when the vehicle braked?”*
   - Click **Generate Grounded Answer**.
   - Model correctly abstains: `INSUFFICIENT EVIDENCE: Physical sensors record kinematic states, not internal cognitive intentions.`
5. **Open Evaluation & Research Metrics:**
   - Show empirical results:  
     - **Keyword Precision@5:** `0.412`
     - **Temporal/Context Precision@5:** `0.700`
     - **Gain:** **+69.9% relative precision improvement** over keyword search!

---

## 7. Directory Structure

```text
VIRA_Demo_Prototype/
├── app.py                      # Professional Streamlit dark-theme dashboard
├── database.py                 # SQLite evidence store with FTS5 and indexes
├── ingestion.py                # Data ingestion for TIAND, synthetic scenes, and CSVs
├── retrieval.py                # Dual retrieval engine (Keyword FTS vs Temporal Context)
├── slm_client.py               # Local SLM client interfacing with Ollama
├── grounding.py                # Citation parser & epistemic grounding verifier
├── evaluation.py               # Quantitative research benchmark suite
├── requirements.txt            # Lightweight Python dependencies
├── .gitignore                  # Git ignore rules for database and cache files
├── README.md                   # Complete documentation and setup manual
├── data/
│   ├── vira_evidence.db        # Initialized local SQLite evidence store
│   ├── sample_observations.csv # Unified CSV dataset export
│   ├── sample_scenarios.json   # Exported scenes and metadata JSON
│   └── evaluation_benchmark.json # Ground-truth benchmark test cases
├── scripts/
│   ├── initialize_database.py  # Script to initialize database schema & demo data
│   ├── generate_synthetic_data.py # Standalone synthetic scenario generator
│   └── import_dataset.py       # CLI tool for custom CSV or TIAND import
└── tests/
    ├── test_database.py        # Database CRUD, FTS5, and duplicate handling tests
    ├── test_retrieval.py       # Timestamp extraction and temporal ranking tests
    ├── test_grounding.py       # Citation extraction and hallucination tests
    └── test_evaluation.py      # Benchmark evaluation metrics tests
```

---

## 8. Running Automated Unit Tests

Run the full test suite with pytest:
```powershell
python -m pytest VIRA_Demo_Prototype/tests/ -v
```
All 16 unit tests verify schema integrity, FTS indexing, proximity scoring, citation verification, and benchmark metrics.
