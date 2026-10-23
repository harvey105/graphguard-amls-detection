# GraphGuard repository instructions

- The team runs this project with native Windows PowerShell, without WSL. Write setup, run, and verification commands for PowerShell 5.1 or newer; use Windows paths and the repository-local `.venv\Scripts\python.exe`.
- Use Python 3.12 and JDK 17 for the pinned `requirements.txt`. Validate runnable deliverables with Windows Python and Java. A WSL run is not evidence that the Windows workflow works.
- Read `.agents/skills/graphguard-powershell/SKILL.md` when changing environment setup, scripts, notebooks, or run instructions.
- Python modules remain Python; PowerShell is the team shell and automation entry point. Keep paths robust to spaces and Vietnamese characters.
- Follow `BDA - PCCV - Trang tính1.csv` for assignment scope and dates; do not implement later tasks while working on the N4 toy motif demo.
- Protect the user's hardware: only one heavy workload at a time, including notebooks, Spark tests, ETL and LPA. Use the mandatory guard in `src/common/spark_session.py`; never bypass its CPU/RAM caps or raise resources to force a successful run. Read the hardware-protection section in the GraphGuard skill before computation. A pressure stop or abnormal noise/shutdown means stop heavy work and investigate; it is not permission for an automatic retry.


## Latest user decision — 24 October 2026

- The user explicitly requested a safe stop and Git push of the current checkpoint. Do not restart heavy work until the user resumes it. Exact progress/checkpoints and next-session priorities are in `agent_job.md`.
- On the next resumed run, the user authorizes high CPU usage around **90%+** and rejects the historical 10% / 2-logical-CPU production profile. Implement and validate a bounded high-throughput CPU policy, affinity and matching Spark parallelism before running full workloads. Do not silently reuse the old low-CPU profile or ask again for already-granted CPU authorization.
- This CPU authorization overrides the older skill's CPU/affinity defaults only. Preserve the mandatory guard, one-heavy-workload mutex, memory/commit limits (5 GiB heap / 8 GiB job), roughly 8 GiB host reserve, spill and pressure shutdown. Higher CPU parallelism must fit the unchanged memory budget. Do not disable caps to force a PASS.
- Optimize repeated preprocessing and implement verified checkpoint reuse/resume. Current runner does not automatically resume. Report actual throughput/utilization by phase; serial/I/O work need not sustain 90% and artificial CPU load is not useful work.
- Changing execution-source files may invalidate current-source acceptance of old runs. Preserve actual executed hashes and disclose historical results; never relabel old outputs with new source hashes. GPU has no verified backend in the current native Windows pipeline.
