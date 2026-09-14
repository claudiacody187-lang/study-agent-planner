# AI-Powered Weekly Study Planner — Software Architecture

## 1. Overview

This architecture describes an AI-powered study-planning system that transforms raw course materials into a personalized weekly study plan.

The system is organized into four horizontal zones:

1. **Content Sources** — raw course materials and documents.
2. **Backend (Agents)** — AI agents that ingest, analyze, prioritize, balance, plan, and adapt.
3. **Database** — persistent storage for courses, embeddings, and generated study plans.
4. **Frontend** — a web interface for viewing, completing, and regenerating the weekly plan.

The backend follows a multi-agent pipeline in which specialized agents perform different responsibilities rather than relying on one large agent.

---

## 2. Architecture Flow

```text
Content Sources
      │
      ▼
Batch Ingestion Agent
      │
      ▼
Lightweight Agent
      │
      ▼
Embeddings + Topic Summary
      │
      ▼
Priority Agent ───────────────┐
                              │
                              ├──► Planner Agent ───► Database
                              │
Balance Agent ────────────────┘
      │
      ▼
Planner Agent
      │
      ▼
Adapter Agent
      │
      └──── Weekly feedback ───► Priority / Balance / Planner
```

The **Priority Agent** and **Balance Agent** provide independent inputs to the **Planner Agent** in parallel.

---

# 3. Content Sources

The system accepts several types of educational content.

### Slide Decks

- **Computer Vision** — 290 slides
- **Geo** — 276 slides
- **Web of Things** — 141 slides
- **MLOps** — 85 slides

### Other Formats

- **Fintech** — PDF (9 pages)
- **ML — AWS modules** — 12 modules

These materials represent the raw knowledge base from which the system builds the study plan.

---

# 4. Backend — AI Agents

The backend contains **seven specialized agents**.

## 4.1 Batch Ingestion Agent

The Batch Ingestion Agent handles large slide decks.

### Responsibilities

- Splits large slide decks into manageable batches.
- Routes each slide to the appropriate processing method.
- Uses:
  - **Text extractor** for text-based content.
  - **Vision model** for visual/image-based content.

This allows large course materials to be processed without requiring the entire document to be handled at once.

---

## 4.2 Lightweight Agent

The Lightweight Agent performs efficient processing of smaller or simpler documents.

### Responsibilities

- Processes Fintech documents.
- Processes ML — AWS modules.
- Handles these sources in a single pass when possible.

Its goal is to avoid unnecessary heavy processing for relatively lightweight material.

---

## 4.3 Embeddings + Topic Summary Agent

This agent converts processed course content into representations that can be searched and analyzed.

### Responsibilities

- Creates vector embeddings from course content.
- Generates topic summaries.
- Stores the resulting representations in the database.

Embeddings enable semantic retrieval, while topic summaries provide a compact description of the course material.

---

## 4.4 Priority Agent

The Priority Agent determines how important each course/topic is when constructing the study plan.

### Main factors

- **Exam weight %**
- **CC weight %**
- **Content volume**

The resulting priorities are passed independently to the Planner Agent.

---

## 4.5 Balance Agent

The Balance Agent ensures that the generated plan is realistic and does not overload the student.

### Main constraints

- **Study budget %** — limits the amount of available study time.
- **Protected rest blocks** — reserves periods for rest.
- **No study after 22:00** — prevents late-night study scheduling.

The Balance Agent works independently from the Priority Agent and sends its constraints to the Planner Agent.

### Why it exists

The Priority Agent answers:

> **What should be studied first?**

The Balance Agent answers:

> **What is realistically possible without overloading the schedule?**

The Planner Agent combines both perspectives.

---

## 4.6 Planner Agent

The Planner Agent generates the final weekly study plan.

It combines:

- Course priorities from the **Priority Agent**.
- Time and wellbeing constraints from the **Balance Agent**.
- Available study time.
- Course/topic information.
- Previously generated planning information.

### Output

A weekly schedule assigning study tasks to available days and time slots.

The planner also respects protected/rest periods. In the architecture diagram, these are represented by muted grey cells alongside normal colored study cells.

---

## 4.7 Adapter Agent

The Adapter Agent evaluates the results of the generated plan and adapts it when necessary.

### Responsibilities

- Checks completed tasks.
- Evaluates weekly feedback.
- Detects whether the current plan needs adjustment.
- Triggers adaptations for the next planning cycle.

This creates a feedback loop rather than a one-time plan generation process.

---

# 5. Database

The system uses:

**Stupabase (pgvector)**

The database stores both structured information and vector representations.

### Main logical tables

```text
┌───────────────┐
│    courses    │
├───────────────┤
│ course data   │
│ topics        │
│ metadata      │
└───────────────┘

┌───────────────┐
│  embeddings   │
├───────────────┤
│ vector data   │
│ semantic data │
└───────────────┘

┌───────────────┐
│  study_plan   │
├───────────────┤
│ tasks         │
│ dates/times   │
│ status        │
│ constraints   │
└───────────────┘
```

### Database responsibilities

- Store processed course information.
- Store embeddings for semantic retrieval.
- Store generated weekly study plans.
- Persist task completion and planning information used by future adaptations.

---

# 6. Frontend

The frontend provides the user interface for viewing and managing the generated plan.

The architecture shows the application deployed through **Cloudflare Pages**.

## Weekly Study Plan

The interface presents a calendar-style weekly view with:

- Computer Vision
- Geo
- Web of Things
- MLOps

Study tasks are represented by checkboxes that the user can mark as completed.

### Protected Rest

The interface also displays protected rest periods.

These are visually different from normal study tasks:

- Greyed-out cells/rows.
- No checkboxes.
- Lock or moon icons.
- Label such as **Protected — rest**.

This makes it clear that these periods are constraints rather than tasks that the student is expected to complete.

### Regenerate Plan

The frontend includes a **Regenerate Plan** action.

This allows the user to request a new schedule when the current plan is no longer suitable.

---

# 7. Feedback Loop

The system is designed as an iterative planning system.

```text
                 ┌─────────────────────┐
                 │    Weekly Plan      │
                 └──────────┬──────────┘
                            │
                            ▼
                     User completes
                        tasks
                            │
                            ▼
                    Weekly feedback
                            │
                            ▼
                 ┌─────────────────────┐
                 │   Adapter Agent     │
                 └──────────┬──────────┘
                            │
                            ▼
              Adjust priorities / constraints
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
      Priority Agent                 Balance Agent
             │                             │
             └──────────────┬──────────────┘
                            ▼
                     Planner Agent
                            │
                            ▼
                  New weekly study plan
```

This enables the system to adapt based on actual user progress rather than generating a fixed schedule once.

---

# 8. Agent Responsibilities Summary

| Agent | Main Responsibility |
|---|---|
| **Batch Ingestion Agent** | Splits and routes large slide decks |
| **Lightweight Agent** | Processes smaller documents/modules efficiently |
| **Embeddings + Topic Summary Agent** | Creates embeddings and topic summaries |
| **Priority Agent** | Calculates study priorities |
| **Balance Agent** | Applies study-budget and rest constraints |
| **Planner Agent** | Generates the weekly study schedule |
| **Adapter Agent** | Evaluates results and adapts future plans |

---

# 9. End-to-End Data Flow

```text
1. Raw course materials
        │
        ▼
2. Ingestion and extraction
        │
        ▼
3. Processed course content
        │
        ▼
4. Embeddings + topic summaries
        │
        ▼
5. Priority analysis ─────────┐
                              │
6. Balance analysis ──────────┤
                              ▼
                       7. Plan generation
                              │
                              ▼
                       8. Store study plan
                              │
                              ▼
                       9. Display in frontend
                              │
                              ▼
                     10. User completes tasks
                              │
                              ▼
                       11. Weekly feedback
                              │
                              ▼
                     12. Plan adaptation
```

---

# 10. Key Architectural Principles

### Separation of responsibilities

Each agent has a focused responsibility. This makes the system easier to understand, test, and modify.

### Parallel planning inputs

The **Priority Agent** and **Balance Agent** independently feed the Planner Agent.

This prevents priority calculation from being mixed with workload and rest constraints.

### Constraint-aware planning

The planner does not simply maximize study time. It must respect constraints such as:

- Study budget.
- Protected rest periods.
- No study after 22:00.

### Persistent knowledge

Processed course content, embeddings, and plans are stored in the database so that the system can reuse information across planning cycles.

### Feedback-driven adaptation

The plan can evolve based on completed tasks and weekly feedback.

---

# 11. Architecture at a Glance

```text
┌──────────────────────────────────────────────────────────┐
│                    CONTENT SOURCES                        │
│  Computer Vision │ Geo │ Web of Things │ MLOps │ PDF... │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│                  BACKEND — 7 AI AGENTS                   │
│                                                          │
│ Batch → Lightweight → Embeddings → Priority ──┐         │
│                                                ├→ Planner → Adapter
│                               Balance ─────────┘         │
│                                                          │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│                  DATABASE — STUPABASE                    │
│             courses │ embeddings │ study_plan            │
└─────────────────────────────┬────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│                     FRONTEND                             │
│          Weekly Study Plan + Protected Rest              │
│                    Regenerate Plan                       │
└──────────────────────────────────────────────────────────┘
                              │
                              └────── feedback ──────► Agents
```

## Conclusion

The architecture implements a **seven-agent AI study-planning pipeline**. Course materials are ingested and semantically processed, priorities are calculated, workload and rest constraints are evaluated independently, and the Planner Agent produces a realistic weekly schedule. The Adapter Agent closes the loop by using user progress and feedback to improve future plans.

The central design idea is the separation between **priority** and **balance**: the system decides both **what is important** and **what is realistically sustainable**, before generating the final study plan.
