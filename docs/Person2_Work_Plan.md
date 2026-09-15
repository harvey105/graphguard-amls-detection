# Person 2 — Detailed Work Plan
## GraphGuard: AML Network Detection with GraphFrames

**Role per PCCV/General Plan:** Data Engineering — dataset selection/validation, ETL mapping (Section 4.1), joint builder of Task 1 with Person 1.

---

## How task numbering works in this plan
Tasks are labeled `2.x` = Person 2's x-th subtask, mapped directly to the Week-by-Week PCCV rows assigned to "Người 2". Each task lists **Objective → Input → Method/Notes → Expected Output → Dependency/Handoff → Teammate Communication**.

## A note on working solo vs. waiting for teammates
You can execute every task below without waiting for anyone else's output — the raw CSV is all you need to start. But "not waiting" and "not communicating" are different things: Tasks 2.2–2.5 are officially **jointly credited with Person 1** in the PCCV (Task 1 = 15 pts, shared). If you build the full pipeline solo to save time, that's fine and genuinely helpful — just don't present the finished script as a closed deliverable. Push your work early and often as "here's a working draft, review when you can" so Person 1 stays a real co-owner instead of finding out later they were bypassed on a shared grade item. The **Teammate Communication** line under each task tells you exactly what to send and to whom.

---

### TASK 2.1 — Dataset Survey & Validation
**Week:** 1 (Foundation) | **Deadline:** End of Week 1
**Goal:** Decide the official dataset (PaySim vs AMLSim) and confirm the raw data actually contains enough structure (repeated triangles, dense clusters) to make Task 3 (Motif Finding) and Task 4 (LPA) produce non-trivial results later.

- **Input:** Raw PaySim CSV (`PS_..._log.csv`, ~493MB, 11 columns per Kaggle screenshot); AMLSim docs (backup option only, don't need to download unless PaySim fails validation).
- **Method/Notes:**
  - Load a manageable sample (or full file if memory allows) with PySpark.
  - Check schema against Kaggle's documented columns (already confirmed via screenshot: `step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud`).
  - Quantify structural signal *before* committing: overlap between `nameOrig` and `nameDest` sets (accounts acting as both sender/receiver — a precondition for cycles to exist at all), frequency of repeated (src,dst) pairs, and fraud-transaction density.
  - This is **not** full graph construction (that's Task 1) — just a lightweight feasibility check.
- **Expected Output:** A short decision note: "PaySim confirmed / rejected as official dataset" + 3–5 sentence justification with numbers (e.g., "% of accounts appear as both sender and receiver", "fraud transaction count", "isFlaggedFraud count").
- **Dependency/Handoff:** Feeds directly into Task 1 (Person 1 + Person 2). Also informs Person 4 (Motif threshold tuning) and Person 5/6 (whether LPA will find meaningful clusters).
- **Teammate Communication:** Post the decision note + key numbers (overlap %, cycle-feasibility result, fraud count) in the group chat as soon as you finish — don't wait to be asked. Tag Person 1 (they're listed as reviewer for this task in the PCCV) and explicitly flag Person 4 and Person 5/6 by name, since your cycle/community feasibility numbers directly change how they'll approach Tasks 3 and 4.

---

### TASK 2.2 — Build Column Mapping Logic (Vertices)
**Week:** 2 (Task 1) | **Deadline:** End of Week 2
**Goal:** Implement the account-extraction + `account_type` + `balance` mapping from Section 4.1 of the General Plan.

- **Input:** Validated PaySim dataframe from 2.1; mapping table (Section 4.1).
- **Method/Notes:**
  - Union `nameOrig` and `nameDest` into one distinct account set → this becomes vertex `id`.
  - Derive `account_type` from the name prefix: `C` = Customer, `M` = Merchant.
  - Derive `balance`: use `oldbalanceOrg` when the account appears as sender, `oldbalanceDest` when it appears as receiver. **Explicitly document** the tie-breaking rule for accounts appearing as both (per General Plan's own caveat — e.g., "most recent balance by max `step`" or "average", state your choice in the report).
  - Write this as a reusable function in `src/utils/etl_mapping.py` (per repo.txt structure) so Person 1 can call it too.
- **Expected Output:** `build_vertices_df(spark_df) -> DataFrame[id, account_type, balance]` function + a quick sample print (row count, 10 sample rows).
- **Dependency/Handoff:** Direct input to Task 1's `GraphFrame(vertices, edges)` instantiation, done jointly with Person 1.
- **Teammate Communication:** Before (or right as) you start coding, send Person 1 the specific tie-break rule you've chosen for accounts with multiple balances (e.g., "latest balance by max step"). This is a genuine ambiguity the proposal itself flags — if Person 1 independently assumes a different rule, you'll end up with two incompatible vertex tables. One message with your resolved rule is enough; keep coding, don't wait for a reply.

---

### TASK 2.3 — Build Column Mapping Logic (Edges)
**Week:** 2 (Task 1) | **Deadline:** End of Week 2
**Goal:** Implement the edge-side mapping from Section 4.1.

- **Input:** Validated PaySim dataframe from 2.1.
- **Method/Notes:**
  - `src` = `nameOrig`, `dst` = `nameDest` (direct passthrough, no transformation needed).
  - `amount` = `amount` (direct passthrough).
  - `timestamp` = `step`, but **document clearly** in the report that this is a simulation-hour proxy, not real wall-clock time (per Section 7.5 caveat) — don't silently convert to a fake datetime without a disclaimer.
  - Keep `isFraud` as an edge attribute too — it's useful later for validating whether Motif/LPA findings correlate with ground-truth fraud labels (nice bonus for the interpretation sections).
- **Expected Output:** `build_edges_df(spark_df) -> DataFrame[src, dst, amount, step, isFraud]` function + sample print + edge count.
- **Dependency/Handoff:** Same as 2.2 — feeds Task 1's GraphFrame instantiation.
- **Teammate Communication:** Mention to Person 1 (and Person 4, who'll consume this later for Motif Finding) that you're keeping `step` as a raw int and *not* converting it to a fake datetime — so nobody downstream accidentally builds logic assuming real calendar time.

---

### TASK 2.4 — Data Quality Checks & Parquet Export
**Week:** 2 (Task 1) | **Deadline:** End of Week 2
**Goal:** Sanity-check the vertices/edges tables before they become the official Task 1 deliverable, then persist them.

- **Input:** Outputs of 2.2 and 2.3.
- **Method/Notes:**
  - Checks to run: no null `id`/`src`/`dst`; every `src`/`dst` in edges exists in vertices `id` set (referential integrity); vertex count roughly matches `len(unique(nameOrig ∪ nameDest))`; edge count matches original row count.
  - Export to `data/processed/vertices.parquet` and `data/processed/edges.parquet` per repo.txt structure (only commit a small sample subset to git, per `.gitignore` policy — full parquet stays local/gitignored).
- **Expected Output:** Data quality report (pass/fail per check) + the two parquet files on disk.
- **Dependency/Handoff:** This *is* the formal Task 1 output — hand off to Person 1 to instantiate `GraphFrame(vertices, edges)` and run the verification counts required by the rubric (15 pts, Graph Construction & Metrics).
- **Teammate Communication:** This is your single most important message in the whole plan. The moment `vertices.parquet`/`edges.parquet` land in `data/processed/`, notify the **entire team**, not just Person 1 — Persons 3, 4, 5, and 6 are all structurally blocked until this file exists. Include the row counts and the path in the message so nobody has to ask.

---

### TASK 2.5 — Task 1 Finalization (credited jointly with Person 1)
**Week:** 2 (Task 1) | **Deadline:** End of Week 2
**Goal:** Get `src/graph_analysis.py` finished and verified.

- **Input:** Parquet files from 2.4.
- **Method/Notes:** You can write this solo to move fast: load parquet → `GraphFrame(vertices, edges)` → print `graph.vertices.count()`, `graph.edges.count()`, and spot-check 5–10 rows against raw data to confirm the mapping didn't corrupt anything.
- **Expected Output:** Working `graph_analysis.py`, verified vertex/edge counts documented for the report.
- **Dependency/Handoff:** Unlocks Task 2 (Degree/PageRank, Person 3) and everything downstream.
- **Teammate Communication:** Because this is a jointly-credited rubric item (not solely yours), send Person 1 the script + verified counts framed as "draft ready for your review" rather than "done." A 2-minute confirmation from them is enough — you don't need to co-write it line by line, but they should get a real look before it's called final.

---

## Deliverables Checklist (Person 2's contribution to the 100-pt rubric)
| Item | Rubric bucket | Status |
|---|---|---|
| Dataset decision note (2.1) | Supports Part A "Dataset" section | ☐ |
| `etl_mapping.py` (2.2, 2.3) | Graph Construction & Metrics (15 pts) | ☐ |
| `vertices.parquet` / `edges.parquet` (2.4) | Graph Construction & Metrics (15 pts) | ☐ |
| Verified GraphFrame counts (2.5, joint) | Graph Construction & Metrics (15 pts) | ☐ |

## Notes carried over from the General Plan (don't lose these)
- Ask the instructor to confirm whether degree distribution counts toward the 15-pt or 25-pt bucket — not Person 2's job to resolve, but be aware the ETL output feeds both.
- Balance mapping tie-break rule (account appears as both sender/receiver) must be explicitly written in the final report — the proposal flags this as a known ambiguity.
- `step` is a simulation-hour proxy, not real time — repeat this caveat wherever timestamps are discussed.
