# SlopStopper 🛡️

**SlopStopper** is a local, privacy-focused automated system designed to audit a child’s YouTube history. It acts as an intelligent "guardian" that uses LLMs (Google Gemini) to detect "brainrot," radicalization pipelines, dark patterns, and low-quality content ("slop").

Unlike generic brand safety tools, SlopStopper adopts the persona of a cynical, protective parent who analyzes content intent rather than just keywords.

## Features

-   **Local & Private**: All data is stored locally in a SQLite database (`data/slopstopper.db`).
-   **5-Dimension Analysis**: Uses Gemini 2.5 Flash-Lite to evaluate content across Visual Grounding, Taxonomy, Narrative Quality, Cognitive Nutrition, and Risk.
-   **"Cynical" Persona**: Detects "sigma male" rhetoric, "mascot horror," and dopamine-loop editing styles.
-   **Deep Dive Inspector**: A "Content Fingerprint" view for individual video analysis, showing structural integrity, weirdness, and emotional volatility scales.
-   **Nutritional Scoring**: A comprehensive 0-10 "Quality Score" for every video, evolving over time.
-   **Actionable Audit**: Interactive "Kill List" and "Risk Spotlight" (Brainrot/Aggression/Slop) to isolate and block toxic channels.
-   **High-Fidelity Dashboard**: A persistent, state-preserving Streamlit interface with "Diet" (Overview), "Audit" (Action), and "Deep Dive" (Inspection) tabs.

## Prerequisites

-   Python 3.12+
-   `uv` (for dependency management)
-   Google Gemini API Key

## Setup

1.  **Clone & Install**
    ```bash
    git clone <repo>
    cd slopstopper
    uv sync
    ```

2.  **Environment Variables**
    Create a `.env` file in the root directory:
    ```bash
    GEMINI_API_KEY=your_actual_api_key_here
    ```

3.  **Data**
    Place your YouTube `watch-history.json` (from Google Takeout) in the root directory of the project.

## Runbook

### 1. Ingest Data
Parse your raw `watch-history.json` into the local database. This step is idempotent and can be run multiple times as you add new history files.

```bash
uv run src/ingest.py
```

### 2. Run Analysis
Analyze pending videos using the Gemini API.

**Analyze specific videos (good for testing):**
```bash
uv run src/analyze.py --ids VIDEO_ID_1 VIDEO_ID_2
```

**Analyze a batch of videos (e.g., first 50):**
```bash
uv run src/analyze.py --limit 50
```

**Analyze ALL pending videos:**
```bash
uv run src/analyze.py --all
```

**Compare Models (A/B Test with Judge):**
```bash
uv run src/compare_models.py VIDEO_ID
```

### 3. View Dashboard
Launch the local web interface to explore the results.

```bash
uv run streamlit run src/report.py
```

### 4. Run Tests
Execute the test suite (includes mocked LLM interactions).

```bash
uv run pytest
```

## Directory Structure

-   `src/ingest.py`: Parses JSON to SQLite.
-   `src/analyze.py`: Main logic for transcript fetching and LLM analysis.
-   `src/report.py`: Streamlit dashboard.
-   `src/schema.py`: Pydantic models collecting the analysis schema.
-   `src/prompts.py`: System prompts defining the "SlopStopper" persona.
-   `data/`: Stores the SQLite database.
