# PromptBeast System Architecture

PromptBeast is a desktop application and cloud AI engine designed for content creators, documentary producers, educational animators, and video editors to transform long narrated stories and spoken word timestamps into validated visual storyboards and detailed image-generation prompts.

---

## High-Level Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│             LOCAL DESKTOP APPLICATION (PySide6)             │
│                                                             │
│  ┌───────────────────┐ ┌──────────────────┐ ┌────────────┐  │
│  │ Story & Timestamp │ │   Interactive    │ │   Scene    │  │
│  │    Loaders        │ │ Timeline Canvas  │ │ Inspector  │  │
│  └─────────┬─────────┘ └────────┬─────────┘ └─────┬──────┘  │
│            │                    │                 │         │
│            ▼                    ▼                 ▼         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │     Core Engine (Timeline, Validation, Exporters)     │  │
│  └──────────────────────────────┬────────────────────────┘  │
│                                 │ QThread Worker            │
│                                 ▼                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Cloud API Client (HTTP / Async)             │  │
│  └──────────────────────────────┬────────────────────────┘  │
└─────────────────────────────────┼───────────────────────────┘
                                  │ HTTPS (REST JSON)
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                 MODAL CLOUD AI BACKEND                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          FastAPI Endpoints (/api/v1/jobs)             │  │
│  └──────────────────────────────┬────────────────────────┘  │
│                                 │                           │
│  ┌──────────────────────────────▼────────────────────────┐  │
│  │                 4-Stage Pipeline                      │  │
│  │  1. Story Analysis & Conditional Continuity           │  │
│  │  2. Visual Scene Planning & Word Boundary Alignment  │  │
│  │  3. Batched Rich Prompt Generation (10 scenes/batch)  │  │
│  │  4. Timeline Validation & Targeted Prompt Repair      │  │
│  └──────────────────────────────┬────────────────────────┘  │
│                                 │                           │
│  ┌──────────────────────────────▼────────────────────────┐  │
│  │         vLLM High-Throughput Inference Engine         │  │
│  │    Model: Qwen3-30B-A3B-Instruct-2507 / Qwen2.5-32B    │  │
│  │         GPU: NVIDIA L4 24GB (Configurable)            │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Local Desktop Layer (`app/`)
- **`app/ui/`**: PySide6 dark QSS theme with 3-column workflow (Inputs -> Timeline & Scene List -> Inspector & Progress).
- **`app/ui/widgets/timeline_view.py`**: Custom `QPainter` canvas with multi-scale time ruler, interactive scene blocks, hover tooltips, and draggable playhead.
- **`app/core/timeline_engine.py`**: Precision scene operations (split, merge, delete, renumber, boundary gap/overlap healing).
- **`app/core/validation.py`**: Timeline integrity validator (coverage, gapless bounds, word-boundary preservation, prompt quality thresholds).
- **`app/core/export.py`**: Exporters for `image_prompts.txt`, `timeline.json`, `image_prompts.json`, and `timeline.csv`.
- **`app/core/project_manager.py`**: Atomic disk persistence with crash recovery detection.

### 2. Cloud AI Layer (`backend/`)
- **`backend/modal_app.py`**: Modal serverless deployment on NVIDIA L4 24GB or A10G.
- **`backend/pipeline/`**: Modular 4-stage pipeline orchestrator.
- **`backend/jobs/store.py`**: Thread-safe job store with progress streaming, batch caching, and user cancellation handling.
- **`backend/inference/engine.py`**: vLLM model runner with schema-repair fallback.
