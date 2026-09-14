# Multi-Agent Study Planner — Build Guide

A weekend project: 7 small agents that read your course materials + schedule, rank what needs the most attention, protect your rest/creative time, and generate an adaptive weekly study plan. Built to be tested **one agent at a time**, then combined gradually, then deployed.

Architecture reference: Content Sources → Backend Agents (Batch Ingestion, Lightweight, Embeddings/Topics, Priority, Balance, Planner, Adapter) → Supabase (pgvector) → Frontend (Cloudflare Pages).

---

## 1. Tools & frameworks (all free tier)

| Layer | Tool | Purpose |
|---|---|---|
| Language | Python 3.11+ | All agents + backend |
| LLM (text) | Google AI Studio — Gemini Flash | Large free context window, multimodal |
| LLM (backup/fast) | Groq (Llama 3.3) | Fast, cheap re-ranking calls |
| Agent orchestration | CrewAI **or** LangGraph | Define agents, wire them together |
| Slide/PDF parsing | `python-pptx`, `PyMuPDF` (fitz) | Local text extraction, no LLM cost |
| Embeddings | Gemini embeddings API (or `sentence-transformers` locally, fully free/offline) | Turn text chunks into vectors |
| Database | Supabase (Postgres + `pgvector` extension) | Store courses, embeddings, plan, progress |
| Backend | FastAPI + Uvicorn | Wraps the agent pipeline as an API |
| Backend hosting | Render (free tier) | Hosts the FastAPI app |
| Frontend | Plain HTML/JS or React (your choice) | Weekly plan view |
| Frontend hosting | Cloudflare Pages | Hosts the static frontend |
| Automation | GitHub Actions (free cron) | Triggers weekly plan regeneration |
| Testing | `pytest` | Unit-test each agent independently |
| Env management | `python-dotenv`, `venv` | API keys, isolated environment |

> Note: the Balance Agent (new) needs no new tool — it's pure Python logic on top of what's already here, same as the Priority Agent.

---

## 2. Accounts to create first (all free, ~10 min)

- [ ] Google AI Studio → get a Gemini API key
- [ ] Groq → get an API key (backup/speed)
- [ ] Supabase → new project, note the project URL + service key
- [ ] Render → connect your GitHub account (for later deployment)
- [ ] Cloudflare Pages → connect your GitHub account (for later deployment)
- [ ] GitHub → a repo for this project (e.g. `study-agent-planner`)

---

## 3. Project structure

```
study-agent-planner/
├── agents/
│   ├── batch_ingestion_agent.py
│   ├── lightweight_agent.py
│   ├── embeddings_topics_agent.py
│   ├── priority_agent.py
│   ├── balance_agent.py
│   ├── planner_agent.py
│   └── adapter_agent.py
├── tests/
│   ├── test_batch_ingestion.py
│   ├── test_lightweight.py
│   ├── test_embeddings_topics.py
│   ├── test_priority.py
│   ├── test_balance.py
│   ├── test_planner.py
│   └── test_adapter.py
├── pipeline.py            # orchestrates all agents together
├── backend/
│   └── main.py            # FastAPI app
├── frontend/
│   └── (Cloudflare Pages project)
├── data/
│   ├── raw/                # your slides/PDFs go here for local testing
│   └── sample/              # small sample files for fast unit tests
├── .env
├── requirements.txt
└── README.md
```

---

## 4. Phase 0 — Local environment setup

```bash
mkdir study-agent-planner && cd study-agent-planner
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install python-dotenv pytest fastapi uvicorn \
    python-pptx pymupdf \
    google-generativeai groq \
    supabase crewai              # or: langgraph
```

Create `.env`:
```
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
SUPABASE_URL=your_url_here
SUPABASE_KEY=your_service_key_here
```

Drop a couple of small **sample** files into `data/sample/` (e.g. a 5-slide deck, a 1-page PDF) — don't test against your real 290-slide deck yet. Fast feedback loop first.

---

## 5. Phase 1 — Build and test each agent individually

Test each one **alone**, with a tiny sample input and a printed/asserted output. No orchestration yet.

### 5.1 Batch Ingestion Agent
**Job:** splits large decks into batches (~25–30 slides), and per slide decides: extract text locally (no LLM) or send to a vision model (image-heavy slide).

- Input: path to a `.pptx` or `.pdf`
- Output: list of `{slide_number, text, needs_vision: bool}`
- Rule of thumb: `if len(extracted_text.split()) < 20: needs_vision = True`

Test: `pytest tests/test_batch_ingestion.py` — assert it correctly splits your 5-slide sample into 1 batch, and correctly flags an image-only slide as `needs_vision=True`.

### 5.2 Lightweight Agent
**Job:** single-pass processing for small content (Fintech's 9 pages, AWS module list for ML course).

- Input: a small PDF, or a manually-entered list of module titles (for the AWS course, since there's nothing to "scan")
- Output: same shape as above, just processed in one call instead of batches

Test: feed it the 9-page sample, confirm it returns without chunking logic kicking in.

### 5.3 Embeddings + Topic Summary Agent
**Job:** takes ingested text (from either agent above), creates embeddings, and generates a short topic outline per course.

- Input: list of `{slide_number, text}`
- Output: `{embeddings: [...], topics: ["topic 1", "topic 2", ...]}`

Test: run on your sample deck's extracted text, check embeddings have the expected vector length and topics list isn't empty.

### 5.4 Priority Agent
**Job:** scores each course using coefficient, EX%/CC% split, and content volume.

- Input: course metadata (from `programme_AIM.md`-style data) + content volume from ingestion
- Output: `{course: "...", priority_score: float}`

Test: hardcode two fake courses (one 100%-EX high-coefficient, one 100%-CC low-coefficient) and assert the EX one scores higher — this is pure logic, no LLM needed, so it should be instant and deterministic.

### 5.5 Balance Agent (new)
**Job:** decides how much of your free time should actually be used for study, and protects the rest — so you don't need to guess a percentage yourself.

- Input: total free hours this week (from `emploi_du_temps.md`-style data), number/volume of courses
- Output: a list of **protected blocks**, same shape as study blocks but tagged differently: `{day, time_slot, task_type: "protected"}`
- Default rules of thumb (tune later if you want):
  - Never use more than ~65–70% of free time for study
  - No more than 2–3 study blocks back-to-back without a break
  - At least one evening per week fully protected, no exceptions
  - Nothing scheduled after 22:00
  - One weekend slot always tagged "open" (hobbies/personal project — not assigned by the system)

Test: give it a fake week with 20 free hours, assert it protects at least ~30% of them and that the output includes at least one full evening block.

### 5.6 Planner Agent
**Job:** takes free time slots, priority scores, **and now the Balance Agent's protected blocks**, and builds a weekly plan.

- Input: list of free slots + ranked courses + protected blocks
- Output: `{day, time_slot, course, task_type}` list — where `task_type` can now be `revision`, `practice`, `project`, or `protected`
- Rule: protected blocks are treated exactly like class time — never overwritten, no matter how high a course's priority score is

Test: give it a tiny fake schedule (2 free slots, 2 courses, 1 protected block) and check it doesn't double-book a slot, respects the higher-priority course getting more slots, and never touches the protected one.

### 5.7 Adapter Agent
**Job:** looks at completed vs incomplete tasks from last week, nudges priority scores for next week.

- Input: last week's plan + completion status
- Output: adjusted priority scores

Test: simulate "Fintech tasks were skipped 3 times" → assert its priority goes up.

> At this point, all 7 agents work **standalone** with sample data. Don't touch real data yet.

---

## 6. Phase 2 — Combine agents into one local pipeline

Now wire them together in `pipeline.py` using CrewAI (or LangGraph) — still fully local, no database, no backend, no frontend.

```
raw files ──> Batch/Lightweight agents ──> Embeddings/Topics agent ──> Priority agent ─┐
                                                                                         ├──> Planner agent ──> (print the weekly plan)
free time slots ────────────────────────────────────────────────> Balance agent ───────┘
```

Priority Agent and Balance Agent run independently of each other (neither needs the other's output) — both just feed into the Planner Agent at the end.

Run it once on your **real** files (`emploi_du_temps.md`, `programme_AIM.md`, and your actual slide decks) and just print the output — no DB writes yet. This is where you'll notice rate-limit issues if any — if so, throttle batch requests or reduce batch size.

Test: does the printed weekly plan look sane? Does Fintech's tiny 9 pages get proportionally less time than CV's 290 slides? Does Projet Tutoré not get mixed in as "revision"? Does at least one evening show up as "protected" instead of study?

---

## 7. Phase 3 — Database (Supabase + pgvector)

In the Supabase SQL editor:

```sql
-- enable vector support
create extension if not exists vector;

create table courses (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text check (type in ('cours','td','tp','at','pr')),
  period text,
  coefficient numeric,
  cc_percent numeric,
  ex_percent numeric
);

create table schedule_slots (
  id uuid primary key default gen_random_uuid(),
  day text,
  start_time time,
  end_time time,
  course_id uuid references courses(id),
  is_free boolean default false
);

create table embeddings (
  id uuid primary key default gen_random_uuid(),
  course_id uuid references courses(id),
  content text,
  embedding vector(768)  -- match your embedding model's dimension
);

create table study_plan (
  id uuid primary key default gen_random_uuid(),
  date date,
  time_slot text,
  course_id uuid references courses(id),   -- nullable: protected blocks have no course
  task_type text check (task_type in ('revision','practice','project','protected')),
  status text default 'pending'
);
```

Update the pipeline to **write** its output into these tables instead of just printing — including the Balance Agent's protected blocks (as `study_plan` rows with `course_id = null` and `task_type = 'protected'`). Test by querying Supabase's table view directly to confirm rows appear correctly, protected blocks included.

---

## 8. Phase 4 — Backend API (FastAPI)

`backend/main.py` wraps the pipeline behind an API:

- `POST /generate-plan` — runs the full pipeline, writes to Supabase
- `GET /plan?week=...` — returns the current week's plan for the frontend (study + protected blocks together)
- `PATCH /task/{id}` — marks a task done/undone (feeds the Adapter agent next run; protected blocks aren't checkable, just displayed)

Run locally:
```bash
uvicorn backend.main:app --reload
```

Test each endpoint with `curl` or Postman before touching the frontend.

---

## 9. Phase 5 — Deploy backend to Render

- Push your repo to GitHub
- On Render: New → Web Service → connect the repo
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Add your `.env` variables in Render's dashboard (never commit `.env`)

Test: hit your live Render URL's `/generate-plan` endpoint and confirm it still writes to Supabase correctly from production.

---

## 10. Phase 6 — Frontend (Cloudflare Pages)

Keep it simple for a weekend build:
- A weekly grid (days × time slots)
- Checkboxes per study task → calls `PATCH /task/{id}` on click
- Protected/rest blocks shown visually distinct (e.g. greyed out or a different color), no checkbox
- A "Regenerate Plan" button → calls `POST /generate-plan`

Deploy: connect the repo's `frontend/` folder to Cloudflare Pages, point it at your Render backend URL.

---

## 11. Phase 7 — Automation (optional, nice touch for the LinkedIn post)

`.github/workflows/weekly-plan.yml` — a GitHub Action that calls your Render `/generate-plan` endpoint every Sunday night, so the plan auto-refreshes without you touching anything.

---

## 12. Suggested weekend flow

- **Saturday morning:** Phase 0–1 (env setup + all 7 agents tested standalone)
- **Saturday afternoon:** Phase 2 (combine locally, run on real data, sanity-check output — including that rest time actually shows up)
- **Saturday evening:** Phase 3 (Supabase schema + pipeline writes to DB)
- **Sunday morning:** Phase 4–5 (FastAPI + deploy to Render)
- **Sunday afternoon:** Phase 6 (frontend + deploy to Cloudflare Pages)
- **Sunday evening:** Phase 7 (automation) + write the LinkedIn post 🙂

---

## 13. Notes for the LinkedIn post later

Worth mentioning if you write it up: the "single agent can't handle 290 slides" realization, the text-vs-vision routing trick to save free-tier quota, the fact the whole stack runs on free tiers (Gemini, Supabase, Render, Cloudflare Pages) — and the moment you realized the planner needed to protect rest time instead of just maximizing study hours. That last one is a genuinely relatable story beat: an AI planner that doesn't know when to stop is a good demo of why "agentic" systems need explicit guardrails, not just optimization.
