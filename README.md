# MyHealth Assistant

A RAG (Retrieval-Augmented Generation) system that answers questions about health insurance benefit booklets. Users enter their Plan ID and ask a question; the system retrieves the most relevant passages from that plan's booklet and streams an answer via Claude.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                             │
│                     frontend_service/                           │
│              index.html  (plain HTML + JS)                      │
│         Plan ID input │ Question input │ Answer (streamed)      │
└───────────────────────┬─────────────────────────────────────────┘
                        │  POST /ask  (SSE stream)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   rag_backend_service/                          │
│                    index.js  (Express)                          │
│                                                                 │
│   Spawns Python pipeline, pipes stdout SSE tokens to browser    │
│                          │                                      │
│           ┌──────────────▼──────────────┐                       │
│           │       generation.py         │  ← pipeline entry     │
│           │  (orchestrates steps below) │                       │
│           └──┬───────────┬─────────┬───┘                       │
│              │           │         │                            │
│   generate_query_embed.py │  retrieval.py   prepare_prompt.py  │
│   Embed user question     │  Query ChromaDB  Format context +   │
│   (all-MiniLM-L6-v2)     │  for plan's      question for LLM   │
│                           │  collection                        │
└───────────────────────────┼────────────────────────────────────┘
                            │  top-k parent chunks
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              rag_data_ingestion_service/                        │
│                   data/vectordb/  (ChromaDB)                    │
│                                                                 │
│    UC280509 collection  │  AC000213  │  N5082015  │  M0025185   │
│    (one per Plan ID — fully isolated)                           │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                  built once by ingest.py
┌─────────────────────────────────────────────────────────────────┐
│              rag_data_ingestion_service/                        │
│                                                                 │
│  text_extraction.py  →  preprocessing.py  →  chunking.py       │
│  pdfplumber             fix hyphenation       Hierarchical:     │
│  raw text per page      drop noise lines      parent ~1200 ch   │
│                         normalize space       child  ~300 ch    │
│                                               child stored in   │
│                                               VectorDB;         │
│                                               parent returned   │
│                                               to LLM            │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                    Claude API (streaming)
                    claude-sonnet-4-6
```

### Key design decisions

| Decision | Rationale |
|---|---|
| One ChromaDB collection per Plan ID | Zero cross-plan leakage — a query on plan A never touches plan B's data |
| Hierarchical chunking (child → parent) | Small child chunks give precise vector matches; parent chunks give the LLM rich surrounding context |
| `all-MiniLM-L6-v2` embeddings | Fast, local, no API key required — same model at ingest and query time |
| SSE streaming | Tokens appear in the browser as Claude generates them — no waiting for the full response |
| Node.js (HTTP) + Python (ML) | Express owns the HTTP layer; Python owns embeddings, retrieval, and Claude API calls |

---

## Project Structure

```
healthcare_assistant/
├── frontend_service/
│   ├── index.html                  # Single-page UI
│   └── requirements.txt            # No third-party Python packages
│
├── rag_backend_service/
│   ├── index.js                    # Express server — /ask endpoint
│   ├── generate_query_embed.py     # Embed user question
│   ├── retrieval.py                # ChromaDB top-k retrieval by plan ID
│   ├── prepare_prompt.py           # Assemble system prompt + context
│   ├── generation.py               # Pipeline entry: runs steps 1-4, streams to stdout
│   ├── package.json
│   ├── package-lock.json
│   └── requirements.txt            # Python packages used by generation/retrieval
│
└── rag_data_ingestion_service/
    ├── text_extraction.py          # PDF → raw text per page (pdfplumber)
    ├── preprocessing.py            # Clean hyphenation, noise, whitespace
    ├── chunking.py                 # Hierarchical parent/child chunking
    ├── ingest.py                   # Orchestrator — run this to build the vector DB
    ├── requirements.txt            # Python packages used by ingestion
    └── data/
        └── mapping                 # Plan ID → PDF path table
```

> **Not in the repo** (gitignored): `data/docs/` (PDFs), `data/vectordb/` (ChromaDB files), `node_modules/`

---

## Prerequisites

- [Anaconda / Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- A conda environment with Python 3.12 and Node.js 24 (see setup below)
- An [Anthropic API key](https://console.anthropic.com/)
- Benefit booklet PDFs placed in `rag_data_ingestion_service/data/docs/`

---

## Setup

### 1. Create and activate the conda environment

```bash
conda create -n llms python=3.12 nodejs -c conda-forge -y
conda activate llms
```

### 2. Install Python dependencies

```bash
pip install -r rag_backend_service/requirements.txt
pip install -r rag_data_ingestion_service/requirements.txt
```

`frontend_service/requirements.txt` is intentionally empty except for comments because the frontend is plain HTML/CSS/JS.

### 3. Install Node dependencies

```bash
conda activate llms
cd rag_backend_service
npm install
cd ..
```

Run `npm install` from the activated `llms` conda environment so it uses the conda-managed Node.js. If `npm` fails with an ICU library error from Homebrew Node, run:

```bash
PATH=/Users/prachi/anaconda3/envs/llms/bin:$PATH npm install
```

### 4. Add your PDFs and mapping

Place benefit booklet PDFs in `rag_data_ingestion_service/data/docs/` and update the mapping file at `rag_data_ingestion_service/data/mapping`:

```
Plan_ID  | Benefit-Booklet
------------------------------------
UC280509 | docs/UC_ppo_280509.pdf
AC000213 | docs/Duplin_BCBS_NC.pdf
N5082015 | docs/NC_bmp.pdf
M0025185 | docs/SantaBarbara_BC_BS.pdf
```

### 5. Set your Anthropic API key

Create a `.env` file in the project root (already gitignored):

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

The backend loads this automatically on startup via `dotenv` — no `export` needed.

Get your key at [console.anthropic.com](https://console.anthropic.com/) → **API Keys**.

---

## Running the System

### Step 1 — Build the vector database (run once)

```bash
conda activate llms
cd rag_data_ingestion_service
python ingest.py
```

This extracts, cleans, chunks, and embeds all benefit booklets into ChromaDB. Expect ~2 minutes for 4 booklets.

### Step 2 — Start the backend

In one terminal:

```bash
conda activate llms
cd rag_backend_service
node index.js
# Backend running on http://localhost:5001
```

If your shell is still picking up a broken Homebrew Node/npm, start it with:

```bash
cd rag_backend_service
PATH=/Users/prachi/anaconda3/envs/llms/bin:$PATH node index.js
```

### Step 3 — Serve the frontend

In a separate terminal, from the repo root:

```bash
conda activate llms
python3 -m http.server 3000 --directory frontend_service
```

### Step 4 — Open the app

Navigate to [http://localhost:3000](http://localhost:3000) in your browser.

Enter a Plan ID (e.g. `UC280509`) and ask a question — the answer streams in from Claude as it generates.

---

## Troubleshooting

### `Error: Cannot find module 'express'`

Install the Node dependencies:

```bash
conda activate llms
cd rag_backend_service
npm install
```

Then restart the backend with `node index.js`.

### `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`

The browser received an HTML page instead of the backend's JSON/SSE response. Check that the Express backend is running on port `5001`, and that the frontend is running on port `3000`:

```bash
lsof -nP -iTCP:5001 -sTCP:LISTEN
lsof -nP -iTCP:3000 -sTCP:LISTEN
```

If another process is using `5001`, stop it and restart the backend from `rag_backend_service`.

### `No benefit booklet found for plan ID ...`

The plan ID does not have a ChromaDB collection yet. Confirm the plan is listed in `rag_data_ingestion_service/data/mapping`, then rebuild the vector database:

```bash
conda activate llms
cd rag_data_ingestion_service
python ingest.py
```

### Claude API errors

Confirm `.env` exists at the project root and contains your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get your key at [console.anthropic.com](https://console.anthropic.com/) → **API Keys**.

---

## How a Query Works (end-to-end)

1. User submits `plan_id` + `question` from the browser
2. Express (`index.js`) spawns `generation.py` with the input via stdin
3. `generate_query_embed.py` encodes the question into a vector
4. `retrieval.py` queries **only** the ChromaDB collection for that `plan_id`, returning the top-5 parent chunk texts ranked by cosine similarity
5. `prepare_prompt.py` formats a system prompt + the retrieved passages + the question
6. `generation.py` calls Claude (`claude-sonnet-4-6`) with streaming enabled
7. Each token is written to stdout as `TOKEN:<text>` and piped through Express as a Server-Sent Event
8. The browser appends each token to the answer box in real time
