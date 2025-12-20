
# Agricultural Synthetic Reasoning Data Generation System


---

## Table of Contents

1. Project Vision
2. System Architecture
3. Installation & Setup
   * Prerequisites
   * Installation
   * Environment Variables
4. Command-Line Interface (CLI) & Usage
5. Core Workflow & Key Components
   * Phase 1: Taxonomy Definition & Seeding
   * Phase 2: Dataset-Grounded Scenario Bundling
   * Phase 3: Reasoning & Advisory Generation
   * Phase 4: Validation, Resume & Scaling
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

The system is designed as a modular pipeline with three distinct layers:

### 1. Data Access Layer
* **`taxonomy_manager.py`**: Manages the schemas (Crops, Weather, Soil).
* **`adapters/`**: specialized readers that pull real numbers from `Crop_recommendation.csv` and `weather.csv` to "hydrate" abstract scenarios.


### 2. Knowledge Layer (The "Bundle Builder")
* **`bundle_builder.py`**: 
    * Generates the **Cartesian Product** of all active taxonomies (Crop × Weather × Soil).
    * Instead of creating thousands of small files, it streams these scenarios into a single, memory-efficient **JSONL file** (`bundles.jsonl`).
    * Each line is a self-contained "Ground Truth" bundle.


### 3. Generation Layer (The "Engine")
* **`prompt_builder.py`**: Wraps the bundle in a strict system prompt that enforces Hindi output and feasibility checking.
* **`generator.py` (Local Engine)**:
    * Runs generation locally using multi-threading (`ThreadPoolExecutor`).
    * Features **Smart Rate Limiting** (prevents 429 errors) and **Crash Recovery** (resumes from last saved line).
* **`create_job.py` (Batch Engine)**:
    * Offloads processing to **Google Gemini Batch API**.
    * 50% cheaper and higher limits than standard API.
    * Handles asynchronous submission, polling, and result parsing.


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

### Run entire pipeline (create batch and generation (non-batch))

```bash
python -m agri_data_gen.cli.main pipeline-run
```

### Batch API processing
This submits your bundles to Google's background servers. It is the fastest and most robust method for large datasets (>1,000 records).
```bash
python -m agri_data_gen.cli.main batch-run
```

### Load YAML Taxonomies to MongoDB

```bash
python -m agri_data_gen.cli.main load-taxonomies
```

### Delete taxonomies from MongoDB:

```bash
python -m agri_data_gen.cli.main reset-taxonomies
```


---
## Core Workflow

### Phase 1: Bundle Construction
The system iterates through every defined crop and weather condition to create grounded scenarios.
* **Input:** Taxonomy Definitions (e.g., "Rice", "High Temp").
* **Process:** Hydrates abstract definitions with real values from CSV datasets (e.g., "Rice" + "35°C", "90% Humidity").
* **Output:** `data/bundles/bundles.jsonl`

### Phase 2: Generation
The engine reads the JSONL file line-by-line to process requests.
* **Input:** A single bundle line (one specific scenario).
* **Prompting:** Instructs the model to act as an advisor, specifically asking: *"Can 'Rice' grow in '35°C'? Explain why."*
* **Model:** `gemini-2.0-flash-thinking-exp` (specifically selected to capture internal Chain-of-Thought).

### Phase 3: Result Parsing
The raw API response is parsed to separate the structured output:
* **Thinking Tokens:** The model's hidden internal reasoning and feasibility checks.
* **Advisory:** The final, actionable Hindi output for the farmer.

---

## Directory Structure

```
.
├── data/
│   ├── raw/                    # Source CSVs
│   │   ├── Crop_recommendation.csv
│   │   └── weather.csv
│   ├── bundles/
│   │   └── bundles.jsonl
│   └── generated/
│       └── data.jsonl          <-- LLM Outputs (Input + Thought + Answer)
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
│       ├── cli/
│       |   └── main.py                 # Entry Point
│       └── gemini_batch_processing/
│           └── create_job.py           # Batch API Handler
```
