
# Agricultural Synthetic Reasoning Data Generation System


---

## Table of Contents

1. Project Vision
2. System Architecture
3. Installation & Setup

   * Prerequisites
   * Installation
   * Environment Variables
4. Core Workflow & Key Components

   * Phase 1: Taxonomy Definition & Seeding
   * Phase 2: Dataset-Grounded Scenario Bundling
   * Phase 3: Reasoning & Advisory Generation
   * Phase 4: Validation, Resume & Scaling
5. Command-Line Interface (CLI) & Usage
6. Directory Structure

---

## Project Vision

The goal of this project is to build a **reliable synthetic data factory for agricultural reasoning**, focused on:

* Crop–weather compatibility analysis
* Feasible vs infeasible (negative) agronomic scenarios
* Detailed step-by-step reasoning (“thinking tokens”)
* Actionable farmer advisories
* Hindi-first output for Indian agricultural contexts

### Core Principles

* **Grounded Generation**
  All inputs come from **real datasets** (crop suitability, weather observations).
  The LLM does *reasoning*, not hallucination.

* **Combinatorial Coverage**
  All cross-combinations of crops × weather scenarios are generated, including implausible cases.

* **Explainability**
  Every record includes detailed reasoning explaining *why* a scenario is valid or invalid.

* **Scalability & Resume Safety**
  Generation supports batching, checkpointing, and crash-safe resumption.

---

## System Architecture

The system is divided into clearly separated layers:

### 1. Data Access Layer

Responsible for structured access to taxonomies and datasets.

* `taxonomy_manager.py`
  Loads YAML taxonomies into MongoDB and exposes active groups and entries.

* `adapters/`
  Dataset-specific adapters (crop, weather, soil) that normalize raw CSV data into canonical schema.

---

### 2. Knowledge & Scenario Layer

* `bundle_builder.py`
  Creates **scenario bundles** by combining:

  * crop taxonomy entry
  * weather taxonomy entry
  * dataset-grounded numeric attributes

Each bundle is deterministic and uniquely identified, e.g.:

```
crop_maize__weather_hot_dry.json
```

These bundles are the **only inputs** passed to the LLM.

---

### 3. Generation Layer

* `prompt_builder.py`
  Converts structured bundle JSON into a controlled English prompt instructing:

  * Hindi output
  * explicit reasoning
  * feasibility analysis

* `generator.py` (GenerationEngine)
  Orchestrates:

  * batching of bundles
  * LLM calls
  * JSON sanitization
  * output persistence
  * checkpointing

---

### 4. Model Provider Layer

Thin wrappers over LLM APIs:

* `gemini_provider.py`
* `perplexity_sonar_provider.py`

Each provider:

* handles authentication
* abstracts request format
* allows provider swapping without pipeline changes

---

## Installation & Setup

### Prerequisites

* Python 3.9+
* MongoDB (local or remote)
* Valid API key for at least one LLM provider (Gemini / Perplexity)

---

### Installation

```bash
git clone <your-repo-url>
cd retrieve_agri

python3 -m venv agri_env
source agri_env/bin/activate

pip install -e .
```

---

### Environment Variables

Create a `.env` file in the project root:

```env
# LLM Providers
GOOGLE_API_KEY="your_gemini_key"
PERPLEXITY_API_KEY="your_perplexity_key"

# MongoDB
MONGO_URI="mongodb://localhost:27017/"
MONGO_DB_NAME="agri_taxonomies"

# Data Paths
DATA_DIR="data"
```

---

## Command-Line Interface (CLI)

### Run entire pipeline
```bash
python -m agri_data_gen.cli.main pipeline-run
```

### Load Taxonomies

```bash
python -m agri_data_gen.cli.main load-taxonomies
```

---

### Build Scenario Bundles

```bash
python -m agri_data_gen.cli.main build-bundles
```

---

### Generate Synthetic Reasoning Data

```bash
python -m agri_data_gen.cli.main generate-data
```


---

## Core Workflow & Key Components

### Phase 1: Taxonomy Definition & Seeding

Taxonomies define **what dimensions to vary**, not data values.

Examples:

* crop
* weather
* soil (future)
* pests (future)

Each taxonomy:

* has a group name
* defines attributes
* lists valid scenario IDs

Seed taxonomies into MongoDB:

```bash
python -m agri_data_gen.cli.main load-taxonomies
```

---

### Phase 2: Dataset-Grounded Scenario Bundling

Adapters read raw datasets:

* `Crop_recommendation.csv`
* `weather.csv`

Adapters compute numeric ranges:

* rainfall tolerance
* temperature tolerance
* pH range

Bundles are created as **pure structured JSON**:

```json
{
  "bundle_id": "crop_maize__weather_cool_dry",
  "crop": {...},
  "weather": {...}
}
```

---

### Phase 3: Reasoning & Advisory Generation

Each batch of bundles is passed to the LLM with instructions to:

* analyze feasibility
* explain reasoning step-by-step
* generate Hindi farmer advisory

Outputs contain:

* full input context
* detailed reasoning
* final advisory
* category (in Hindi)

---

### Phase 4: Validation, Resume & Scaling

---

## Directory Structure

```
.
├── data/
│   ├── raw/
│   │   ├── Crop_recommendation.csv
│   │   └── weather.csv
│   ├── bundles/
│   └── generated/
│       └── data.jsonl
├── sample_data/
│   └── taxonomies/
├── src/
│   └── agri_data_gen/
│       ├── core/
│       │   ├── data_access/
│       │   │   ├── taxonomy_manager.py
│       │   │   └── adapters/
│       │   ├── knowledge/
│       │   │   └── bundle_builder.py
│       │   ├── generators/
│       │   │   └── generator.py
│       │   ├── prompt/
│       │   │   └── prompt_builder.py
│       │   └── providers/
│       │       ├── gemini_provider.py
│       │       └── perplexity_sonar_provider.py
│       └── cli/
│           └── main.py
```

---

## Final Notes

This system is **not a prompt generator**.
It is a **controlled synthetic reasoning engine** designed for:

* fine-tuning LLMs
* benchmarking agronomic reasoning
* studying failure modes
* generating negative knowledge explicitly

The design scales cleanly to:

* soil
* pests
* fertilizer
* irrigation
* farmer query modeling
