# 🛡️ Project Specification: SlopStopper

**Version:** 3.0 (Implemented)
**Date:** December 19, 2025
**Target User:** Technical Parent (macOS environment)
**Objective:** Create a local, privacy-focused automated system to audit a child’s YouTube history. The system uses LLMs to detect "brainrot," radicalization, dark patterns, and low-quality content ("slop"), providing a high-fidelity dashboard for parental review and trend analysis.

---

## 1. System Architecture

### 1.1 Technology Stack

*   **Language:** Python 3.12+
*   **Environment Management:** `uv` (Astral)
*   **Database:** SQLite (local file)
*   **LLM Provider:** Google Gemini API (via `google-genai` SDK)
*   **Frontend:** Streamlit (local web dashboard)
*   **Ingestion/Enrichment:**
    *   `yt-dlp` (Transcript & Metadata extraction - *Currently disabled/optional*)
    *   Standard JSON libraries (Takeout parsing)

### 1.2 Directory Structure

```text
slopstopper/
├── .env                  # API Keys (GEMINI_API_KEY)
├── .python-version       # Python version definition
├── pyproject.toml        # Dependencies managed by uv
├── README.md
├── APP_SPEC.md           # This file
├── data/
│   ├── history.json      # Raw Google Takeout file
│   └── slopstopper.db    # SQLite Database
└── src/
    ├── ingest.py         # Parses Takeout -> SQLite
    ├── analyze.py        # SQLite -> Gemini -> SQLite
    ├── report.py         # Streamlit Dashboard (Entry point)
    ├── schema.py         # JSON Schema definitions (Pydantic)
    └── prompts.py        # System Instructions (Persona)
```

---

## 2. Database Schema (SQLite)

**File:** `data/slopstopper.db`
**Table:** `videos`

The `videos` table is the single source of truth.

```sql
CREATE TABLE IF NOT EXISTS videos (
    -- Core Identity
    video_id TEXT PRIMARY KEY,
    title TEXT,
    video_url TEXT,
    channel_name TEXT,
    channel_url TEXT,
    watch_timestamp DATETIME,
    
    -- Content Data
    transcript_text TEXT,           -- (Optional) Full subtitles
    transcript_status TEXT,         -- 'MISSING', 'FETCHED', 'UNAVAILABLE'
    
    -- Analysis State
    status TEXT DEFAULT 'PENDING',  -- 'PENDING', 'ANALYZED', 'ERROR', 'SKIPPED'
    error_log TEXT,

    -- LLM Analysis Metadata
    model_used TEXT,                -- e.g., 'gemini-1.5-flash'
    prompt_version TEXT,            -- e.g., 'v1.0'
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost REAL,

    -- High-Level Indices (Extracted from JSON for querying)
    safety_score INTEGER,           -- 0-100
    primary_genre TEXT,
    is_slop BOOLEAN,
    is_brainrot BOOLEAN,
    
    -- Full Payload
    analysis_json TEXT              -- The complete raw JSON response
);
```

---

## 3. LLM Configuration

### 3.1 System Instruction (The Persona)

**File:** `src/prompts.py`
The agent acts as **SlopStopper**, a cynical, protective parent analyzing content for "Brainrot", "Slop", and "Radicalization Pipeline" risks. It prioritizes *intent* over keywords.

### 3.2 JSON Schema (5 Dimensions)

**File:** `src/schema.py`
The analysis output is structured into 5 core dimensions:

1.  **Visual Grounding:**
    *   `setting`: Description of the visual environment.
    *   `detected_entities`: List of key visual elements (e.g., "Minecraft Steve", "AK-47").
2.  **Content Taxonomy:**
    *   `primary_genre`: Broad category (e.g., `Gaming_Gameplay`, `Mascot_Horror`).
    *   `specific_topic`: Narrow subject (e.g., "Skibidi Toilet").
    *   `target_demographic`: Age group.
3.  **Narrative Quality:**
    *   `structural_integrity`: `Coherent_Narrative` vs `Incoherent_Chaos`.
    *   `creative_intent`: `Artistic/Creative` vs `Algorithmic/Slop`.
    *   `weirdness_verdict`: `Creative_Surrealism` vs `Lazy_Randomness` (distinguishes art from brainrot).
4.  **Cognitive Nutrition:**
    *   `intellectual_density`: `High` to `Void`.
    *   `emotional_volatility`: `Calm` to `Aggressive_Screaming`.
    *   `is_slop` & `is_brainrot`: Boolean flags.
5.  **Risk Assessment:**
    *   `safety_score`: 0-100.
    *   `flags`: Booleans for specific risks (Radicalization, Body Image, Pseudoscience, etc.).

---

## 4. Dashboard (Streamlit)

**File:** `src/report.py`

### 4.1 Global UX Rules
*   **Tab Persistence:** Uses a custom `st.radio` navigation bar (not `st.tabs`) to prevent state resets during interaction.
*   **Header Placement:** The Streamlit header (deploy/hamburger) is fixed to the **BOTTOM** (`bottom: 0`) to maximize top-screen real estate.
*   **Information Density:** No "useless space". Content starts immediately (`1rem` padding). Margins are minimized.

### 4.2 Views (Tabs)

#### 🧠 The Diet (Overview)
*   **KPIs:** Count of Slop/Brainrot videos, Avg Quality Score.
*   **Taxonomy Treemap:** Hierarchical view of Genres and Topics colored by Safety Score.
*   **Risk Radar:** Spider chart showing aggregate risk flags.
*   **Quality vs Safety:** Scatter plot (Quadrants: Safe & Good, Unsafe but Art, Safe Slop, Danger Zone).
*   **Cognitive Nutrition:** Donut chart of Emotional Volatility.

#### 🚨 The Audit (Action)
*   **The Kill List:** Channels ranked by Average Safety Score (lowest first). High-density table.
*   **Red Flag Gallery:** Specific recent videos flagged for high-risk categories (Radicalization, etc.) with Verdict reasons.

#### 🔍 Deep Dive (Inspector)
*   **Purpose:** Detailed analysis of a single video.
*   **Navigation:** Searchable Dropdown (Title | Channel | ID). unified session state (`deep_dive_video_idx`).
*   **Layout:**
    *   **Left Column:**
        *   **Header:** `##### [Channel] | Title`
        *   **Summary:** "Cynical Summary" block.
        *   **Verdict:** Colorful Alert Box (Green/Yellow/Red) with Reason.
        *   **Player:** YouTube Video Embed.
    *   **Right Column:**
        *   **Header:** `##### 🧬 Content Fingerprint`
        *   **Fingerprint Scales:** Visual scale bars for Structure, Intent, Weirdness, Density, and Volatility.
            *   Layout: Flexbox, horizontal bars.
            *   Highlight: Selected value is colored (Green/Orange/Red) and bordered.
        *   **Visual Setting & Flags:** Text description.
    *   **Bottom:** Raw JSON viewer (collapsed/expanded).

---

## 5. CLI Tools

### 5.1 `ingest.py`
Parses `watch-history.json` into SQLite. Idempotent.

### 5.2 `analyze.py`
Connects to Gemini to analyze pending videos.
*   `--limit [N]`: Batch size (default 10).
*   `--ids [ID]`: Analytic specific ID.
*   `--all`: Analyze all pending.
*   **Output:** Rich formatted table showing Title, Verdict, Slop/Brainrot status, and Cost.

---

## 6. Development Workflow

1.  **Dependency Management:** `uv sync`, `uv run`.
2.  **Testing:** `uv run pytest` (Mocked Gemini responses).
3.  **Linting/Formatting:** Standard Python practices.
4.  **Local Data:** `data/` folder is gitignored (except placeholder).