# RaahiSense
### Evidence-Guided Road-User Activity Understanding in the Indian Environment

**RaahiSense** is an MTech Data Science research project focused on developing an on-device vehicle intelligence system that can understand vehicle behaviour and road-user activity using heterogeneous, time-dependent data.

The project explores how data from vehicle sensors, automotive systems, camera-based perception, ADAS events and diagnostic records can be aligned, structured, analysed and retrieved to generate evidence-grounded explanations in natural language.

RaahiSense is inspired by the VehicleGPT concept and extends it toward road-user activity understanding in Indian driving environments.

---

## 1. Project Overview

Modern vehicles generate data from multiple sources, including sensors, Electronic Control Units (ECUs), Advanced Driver Assistance Systems (ADAS), cameras and diagnostic systems. However, these data sources are often handled independently.

RaahiSense aims to connect these sources through a common temporal representation and an evidence-retrieval pipeline.

Instead of providing raw vehicle data directly to a language model, the system first processes and organizes the data into structured signals, events and contextual information. Relevant evidence is then retrieved before an on-device Small Language Model (SLM) generates an explanation.

**Core workflow:**

```text
Vehicle and Road-User Data
          |
          v
   Data Collection
          |
          v
 Protocol Adapters
          |
          v
Timestamp Alignment and Normalization
          |
          v
 Common Data Model
          |
          v
 Event and Context Understanding
          |
          v
    Local Storage
          |
          v
 Search and Analytics
          |
          v
 Evidence Retrieval and Ranking
          |
          v
     On-Device SLM
          |
          v
 Evidence-Guided Explanation
```

## 2. Research Objectives

The project focuses on the following objectives:

1. Develop a common temporal representation for heterogeneous vehicle and road-user data.
2. Investigate methods for timestamp alignment, data normalization and multimodal data fusion.
3. Represent road-user activity and driving conditions as structured events.
4. Identify temporal relationships between road-user activity and vehicle behaviour.
5. Develop historical event retrieval and evidence-ranking methods.
6. Generate natural-language explanations grounded in retrieved evidence.
7. Evaluate retrieval quality, explanation grounding, response latency and resource consumption on constrained edge hardware.

## 3. Research Questions

The research is guided by the following questions:

- **RQ1:** How can heterogeneous automotive and road-user data sources be temporally aligned into a common representation?
- **RQ2:** Can structured event and context abstraction improve historical vehicle-information retrieval compared with raw-signal search?
- **RQ3:** Can temporal evidence ranking identify relevant factors behind observed vehicle behaviour?
- **RQ4:** How accurately can a lightweight SLM generate explanations grounded in retrieved vehicle evidence?
- **RQ5:** Can the evidence-guided pipeline satisfy edge memory and response-latency constraints?

## 4. Dataset and Data Collection Strategy

The research follows a hybrid strategy involving publicly available datasets, simulation, data replay and selected physical hardware.

### Datasets under investigation

| Dataset | Research role |
|---|---|
| IDD Multimodal | Primary dataset for multimodal data inspection and validation |
| TIAND Multimodal Dataset | Additional dataset for sensor-structure and synchronization analysis |

The current Phase 1 work focuses on inspecting dataset structure, identifying available modalities, validating file contents, examining timestamp information and assessing synchronization-related metadata.

Dataset characteristics and sensor semantics will be documented based on inspection and available dataset documentation. The presence of a directory or file extension alone is not treated as proof of a sensor modality or data format.

### Additional data sources planned for the system

- CAN / CAN-FD vehicle signals
- SOME/IP service events
- Android Vehicle HAL (VHAL) properties
- QNX logs and service events
- ADAS warnings and interventions
- Camera-based road-user and scene metadata
- UDS / DoIP diagnostic information
- CARLA-generated driving scenarios
- Recorded and generated vehicle-data streams

The availability and implementation status of individual sources will be tracked separately.

## 5. Proposed System Architecture

RaahiSense is organized into the following logical layers.

| Layer | Responsibility |
|---|---|
| Data Sources | Collect vehicle signals, sensor data, road-user observations and diagnostic information |
| Protocol Adapters | Read and interpret source-specific data |
| Data Fusion | Timestamp alignment, decoding, validation and normalization |
| Understanding | Event detection, road-user activity representation and driving-context analysis |
| Storage | Maintain recent vehicle state and indexed historical records |
| Retrieval | Process queries and retrieve relevant historical evidence |
| Evidence Ranking | Rank signals, events and contextual records by relevance |
| VehicleGPT | Generate explanations using a local or quantized SLM |
| Interface | Provide query-based access to vehicle information |

### Common vehicle-road-user representation

The proposed common data model will include fields such as:

- Timestamp
- Source and sensor identifier
- Trip or session identifier
- Signal or event name
- Observed value and unit
- Event severity
- Road context
- Driving context
- Source-file or observation reference

This representation will support temporal correlation across different data sources while retaining the provenance of each observation.

## 6. Example Research Scenario

Consider a vehicle experiencing repeated braking and increased energy consumption in dense traffic.

RaahiSense aims to retrieve and correlate relevant evidence:

1. Road-user or traffic activity is identified.
2. Vehicle signals indicate repeated braking.
3. Driving context identifies stop-and-go conditions.
4. Energy-consumption records show a change during the same period.
5. Relevant observations are retrieved and ranked.
6. The SLM generates an explanation based on the retrieved evidence.

The system should distinguish observed evidence from inferred relationships. Temporal association alone does not establish causation.

## 7. On-Device Intelligence

The language model is not expected to process or remember weeks of raw sensor streams.

Instead, RaahiSense follows a retrieval-before-generation approach:

1. Interpret the user's natural-language query.
2. Convert the query into a structured search request.
3. Retrieve relevant signals, events, diagnostics and contextual records.
4. Rank evidence according to temporal and contextual relevance.
5. Prepare a compact evidence context.
6. Generate a concise explanation using an on-device SLM.
7. Preserve references to the supporting records.

This approach is intended to reduce the model's workload and support local processing without requiring continuous cloud connectivity.

## 8. Hardware Architecture

The prototype follows a hybrid development and deployment strategy rather than requiring a complete physical vehicle.

| Component | Purpose | Priority |
|---|---|---|
| Development workstation | Simulation, dataset processing, model preparation and replay | Essential |
| Raspberry Pi 4 (2 GB) or equivalent ARM board | Constrained edge deployment | Essential |
| CAN / CAN-FD interface | Physical automotive-bus communication and replay | Essential |
| Ethernet connection | Workstation-to-edge communication | Essential |
| 64/128 GB SSD | Local historical data and application storage | Recommended |
| USB / CSI camera | Camera and perception demonstration | Recommended |
| OBD-II interface | Optional vehicle diagnostics and signal experiments | Optional |
| GNSS receiver | Location and route context | Optional |
| IMU | Motion and orientation context | Optional |

CARLA or equivalent simulation and recorded-data replay can provide scenarios for development and evaluation. Selected physical interfaces will be used to validate the pipeline where available.

## 9. Current Development Status

The repository contains the initial dataset-inspection and Phase 1 validation work.

### Phase 1: Dataset audit and validation

Current work includes:

- IDD primary, secondary and supplement inventory generation.
- TIAND dataset inventory generation.
- Dataset file-structure inspection.
- File-content and data-format validation.
- IDD LiDAR data profiling.
- Camera and LiDAR frame-index inspection.
- OBD timestamp and signal inspection.
- TIAND radar file-structure analysis.
- Calibration-file inventory.
- Camera-LiDAR and camera-radar synchronization analysis.
- Dataset audit visualizations and summary reports.

The scripts and generated inventory manifests are maintained separately from the raw datasets.

**Important:** Initial inspection and validation do not imply that every sensor's physical semantics, calibration parameters or clock synchronization have been fully verified. These require further documentation review and validation.

### Planned research phases

| Phase | Focus |
|---|---|
| Phase 1 | Dataset audit, structure inspection and validation |
| Phase 2 | Data preprocessing, timestamp alignment and common data representation |
| Phase 3 | Event and road-user activity understanding |
| Phase 4 | Temporal correlation, analytics and anomaly detection |
| Phase 5 | Evidence retrieval and ranking |
| Phase 6 | On-device SLM integration and explanation generation |
| Phase 7 | Edge deployment, testing and research evaluation |

The implementation status of each phase will be updated as the research progresses.

## 10. Repository Structure

The repository is organized around dataset inspection, data processing, research experiments and prototype development.

```text
RaahiSense/
│
├── data/
│   ├── raw/
│   │   └── README.md
│   ├── manifests/
│   │   ├── tiand/
│   │   └── phase1/
│   └── generated/
│
├── scripts/
│   ├── inspect_tiand_structure.py
│   ├── phase1_dataset_audit.py
│   ├── phase1_content_validation.py
│   ├── phase1_sensor_structure.py
│   ├── phase1_remaining_validation.py
│   └── phase1_dataset_visualisations.py
│
├── R/
│   └── tiand/
│
├── database/
│
├── temporal/
│
├── detector/
│
├── generator/
│
├── tests/
│
├── VIRA_Demo_Prototype/
│
├── configs/
│
├── requirements.txt
└── README.md
```

The structure may evolve as additional research components are implemented.

## 11. Getting Started

### Prerequisites

- Python 3.10 or a compatible Python version
- Git
- NumPy
- Pandas
- Matplotlib
- Required packages listed in `requirements.txt`

### Clone the repository

```bash
git clone https://github.com/jenishborah/RaahiSense.git
cd RaahiSense
```

### Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

If you only need the basic Phase 1 Python audit dependencies:

```bash
pip install numpy pandas matplotlib
```

### Run the dataset audit

```bash
python scripts/phase1_dataset_audit.py
```

### Run additional validation

```bash
python scripts/phase1_content_validation.py
python scripts/phase1_sensor_structure.py
python scripts/phase1_remaining_validation.py
```

### Generate dataset visualizations

```bash
python scripts/phase1_dataset_visualisations.py
```

**Note:** These scripts use local dataset paths and directory structures. Before running them, download the relevant datasets separately and configure their paths to match your local environment. Check each script's configuration before execution.

## 12. Data and Storage Policy

The raw datasets are not included in this GitHub repository.

Users must obtain datasets from their respective official sources and place them in the configured local directories.

The repository may contain:

- Dataset inventory manifests
- Dataset inspection scripts
- Validation summaries
- Research code
- Selected reproducible visualizations
- Application and prototype source code

Large raw sensor files, private credentials, database files and temporary outputs should not be committed.

## 13. Research Evaluation

The proposed evaluation will consider the following dimensions:

| Evaluation area | Measurement focus |
|---|---|
| Data quality | Missing values, invalid records and timestamp consistency |
| Temporal alignment | Alignment error and synchronization quality |
| Event understanding | Event classification and detection performance |
| Temporal correlation | Accuracy of identified event relationships |
| Retrieval | Precision, recall, ranking quality and relevance |
| Explanation grounding | Whether generated explanations are supported by retrieved evidence |
| Edge performance | Memory usage, response latency and computational requirements |

Evaluation metrics and experimental protocols will be finalized as the corresponding methods are implemented.

## 14. Expected Research Contribution

The research aims to develop and evaluate an evidence-guided temporal intelligence pipeline for heterogeneous vehicle and road-user data under edge-computing constraints.

The expected contributions include:

- A common representation for heterogeneous vehicle and road-user observations.
- Temporal alignment and event-context abstraction methods.
- Methods for correlating road-user activity with vehicle behaviour.
- Evidence retrieval and ranking for historical vehicle queries.
- Grounded natural-language explanations using a resource-constrained SLM.
- An evaluation of the pipeline under edge hardware limitations.

These are research objectives, not claims of completed experimental results.

## 15. Project Information

**Project:** RaahiSense  
**Research Title:** Evidence-Guided Road-User Activity Understanding in the Indian Environment  
**Programme:** MTech Data Science  
**Department:** Department of Computer Science  
**Institution:** Tezpur University, Assam, India  
**Product Concept:** RaahiSense / VehicleGPT  

**Researcher:** Jenish Ali Borah

## 16. License and Dataset Attribution

This repository is intended for academic research and prototype development.

Dataset ownership, licensing, usage restrictions and citation requirements remain with the respective dataset providers. Users should consult the original dataset documentation before using or redistributing any dataset.

A repository-level license should be added only after the project's code and third-party dependencies have been reviewed for licensing compatibility.

---

**RaahiSense — Evidence before explanation.**