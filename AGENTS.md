# GraphGuard repository instructions

- Run and verify this project with native Windows PowerShell 5.1+, repository-local `.venv\Scripts\python.exe`, Python 3.12 and JDK 17. A WSL run is not Windows execution evidence.
- Read `.agents/skills/graphguard-powershell/SKILL.md` before changing environment setup, scripts, notebooks or run instructions. Keep paths robust to spaces and Vietnamese characters.
- Python modules remain Python; PowerShell is the team shell and automation entry point.
- Follow the scope and task definitions in `BIG_Data_Group6.md`. Preserve assignment boundaries; do not implement later tasks while working on the N4 toy motif demo.

## Hardware protection and CPU authorization

- Only one heavy workload at a time, including notebooks, Spark tests, ETL and LPA. Use the mandatory guard in `src/common/spark_session.py`.
- The user authorizes all available CPUs: job CPU capacity 100%, full allowed Windows affinity, Spark task concurrency bounded by the unchanged memory budget. Do not restore the historical 10% / 2-logical-CPU production profile or ask again for CPU authorization already granted.
- Keep the 5 GiB heap / 8 GiB job profile, approximately 8 GiB host RAM/commit reserve, workload mutex, spill and pressure shutdown. Do not raise memory caps to force a PASS.
- Full-data motif intermediates use Parquet stages; avoid deserialized local checkpoints that exhausted the heap at high concurrency. Preserve the notebook's 32 MiB Parquet row groups and bounded batches.
- A pressure stop, OOM or abnormal noise/shutdown means stop heavy work and investigate. Never automatically retry an unchanged workload or increase memory limits after a failure.
- Report measured throughput/utilization. Serial and I/O phases need not sustain 90–100% CPU; artificial CPU load is not useful work. GPU has no verified backend in this native Windows pipeline.

## Provenance and publication

- Preserve actual executed source hashes and historical results. Never relabel old outputs with new hashes; computational-source changes may require a fresh run.
- Verified resume is explicit and requires matching source/input/config plus completed output inventories and hashes. Read the public workflow in `README.md` and acceptance evidence in `docs/Project_Code_Audit_2026-10-22.md`.
- Both full-system notebooks and the full native project gate completed successfully. Do not restart heavy computation for documentation-only changes.
- The latest user request authorizes publishing the current changes to `main`. Keep internal planning/presentation notes local, and make public Markdown links resolve to files included in the repository.
