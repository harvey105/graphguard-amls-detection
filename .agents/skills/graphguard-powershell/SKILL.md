---
name: graphguard-powershell
description: Set up, run, document, or verify GraphGuard code and notebooks on native Windows PowerShell with conservative CPU/RAM protection and sequential heavy workloads.
---

# GraphGuard PowerShell workflow

- Use native Windows PowerShell 5.1+ to set up, run, and verify this project; do not use WSL as the project runtime. Resolve paths from the repository root and quote or use `Join-Path` for directories with spaces and Vietnamese text.
- Use a Windows Python 3.12 virtual environment at `.venv`, install `requirements.txt` there, and run modules with `& .\.venv\Scripts\python.exe ...` so activation and execution policy changes are unnecessary.
- Run `scripts/setup_windows.ps1` to install pinned Python requirements and verified Hadoop 3.3.4 native tools into `.venv`. Use `src/common/windows_runtime.py` for Spark environment setup, including JDK 17, Hadoop, the Windows Python worker, and a `subst` alias for repository paths with spaces or Vietnamese text.
- Prefer `scripts/run_n4.ps1` for the 21/9 N4 demo. Run other Python modules with `& .\.venv\Scripts\python.exe -m ...` from Windows PowerShell.
- For notebooks, select the Windows `.venv` kernel, execute the cells with that interpreter, and save real outputs. Refresh environment and status labels when changing the execution platform.
- Check `pip check`, the relevant module, and notebook execution before reporting PASS. State the precise missing prerequisite when native Windows verification cannot finish.
- Keep Python algorithm code in Python and assignment boundaries from `BDA - PCCV - Trang tính1.csv`. Use PowerShell for setup and run scripts.

## Protect this workstation before computation

The user reported an unexpected shutdown while two full notebooks and a Spark
test gate ran concurrently. Hardware protection takes priority over completion
speed or a desired score. Never repeat that execution pattern.

- Run **one heavy workload at a time**: one notebook, Spark CLI, ETL, LPA or test
  gate. Do not background a second job while waiting, including across turns.
- If the user pauses Spark, stop the owned orchestration process tree so it
  cannot launch the next job. Continue edits and tests that start no JVM; keep
  runtime checks pending until the user explicitly resumes Spark work.
- Use `src/common/spark_session.py`; its mandatory Windows guard acquires a
  machine-session mutex before Java starts. Close the previous Python/kernel
  before starting another task: `Spark.stop()` alone can leave a JVM resident.
- `src/common/hardware_guard.py` applies inherited Windows Job Object CPU,
  commit-memory, affinity and priority limits, checks RAM/commit/disk reserves,
  and stops its own process group on sustained resource pressure. Never disable
  it, raise memory caps, or run unguarded Spark to get a PASS. The latest user CPU authorization overrides the historical CPU defaults below: permit all available CPUs, retain full allowed affinity and resolve `local[*]` to an explicit memory-bounded task count before Java starts.
- Historical profile (superseded for CPU by the latest user request): at most 2 logical CPUs, 10% CPU hard cap,
  6 GiB JVM heap, 10 GiB total job commit; retain roughly 8 GiB host RAM/commit
  reserve. Defaults scale down or refuse admission on smaller/busy machines.
  A 4 GiB sample/test heap uses a lower **7 GiB hard job cap**, retaining the
  same reserve and mutex; CPU quota is now100% with memory-bounded task slots. Smaller profiles cannot be upgraded in an
  existing Python/kernel. A full-data run may explicitly request a **5 GiB heap /
  8 GiB hard job cap** when the unchanged admission reserve permits it.
  `GRAPHGUARD_MAX_HEAP` is an optional ceiling in the session factory: it can
  only reduce a caller request, never increase it. `check_project.ps1` and
  `check_task3.ps1` default to `-MaxHeap 5g`; notebook sessions request 5 GiB.
  Release intermediate caches with blocking unpersist at phase boundaries and
  retain disk-backed checkpoints rather than truncating data or evaluation.
  The 5/8 GiB profile completed both full motif notebooks and the full project
  gate on 22 October 2026; see `docs/Project_Code_Audit_2026-10-22.md` for measured
  peaks and scope. This evidence does not waive fresh admission on later runs.
  This reduces the actual OS allocation limit, not the
  safety reserve; full 6 GiB workloads retain their original 10 GiB profile.
- Validate the guard with small native tests **before** Spark. Then execute
  guard/tests → one full notebook → inspect measurements/exit → next notebook,
  sequentially. Use disk spill, column projection and cache release to reduce
  memory. Never stress-test the machine or deliberately exhaust host resources.
- Full CPU concurrency requires disk-backed motif intermediates. On24October,
  twenty tasks materializing deserialized `localCheckpoint` UnsafeRows exhausted
  the5GiB Java heap while host RAM still had headroom. Do not reintroduce that
  full-data cache path. Use Parquet stage boundaries,32MiB Parquet row groups,
  reader batch1024 and columnar cache batch1000 in the notebook session; keep
  the5/8GiB limits. After diagnosing that failure, tiny visible-kernel tests and
  the full IBM run passed with peak job commit6.27GiB and minimum free RAM13.39GiB.
  A changed implementation needs its own verification; historical measurements
  are evidence, not admission permission or a guarantee for a new workload.
- Save notebook outputs after each completed cell and preserve partial outputs
  after failure. A resource stop is a failed run, not PASS. Do not auto-retry or
  increase resources after a pressure stop/OOM/shutdown; inspect the failure and
  change the plan while retaining caps. Finish independent edits if a run cannot
  safely proceed and report the precise blocked verification.
- Do not claim GPU acceleration without a supported, verified backend. The
  project's native Windows GraphFrames/Spark ML stack currently runs on CPU;
  possessing an NVIDIA GPU does not offload it automatically. Do not migrate to
  WSL/Linux or install GPU drivers/libraries just to bypass these limits.
- CPU temperature is not reliably exposed here. Software limits mitigate load;
  they cannot guarantee protection from cooling, power or hardware faults. If
  the user reports another abnormal noise/shutdown, stop heavy work immediately.
