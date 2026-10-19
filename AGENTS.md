# GraphGuard repository instructions

- The team runs this project with native Windows PowerShell, without WSL. Write setup, run, and verification commands for PowerShell 5.1 or newer; use Windows paths and the repository-local `.venv\Scripts\python.exe`.
- Use Python 3.12 and JDK 17 for the pinned `requirements.txt`. Validate runnable deliverables with Windows Python and Java. A WSL run is not evidence that the Windows workflow works.
- Read `.agents/skills/graphguard-powershell/SKILL.md` when changing environment setup, scripts, notebooks, or run instructions.
- Python modules remain Python; PowerShell is the team shell and automation entry point. Keep paths robust to spaces and Vietnamese characters.
- Follow `BDA - PCCV - Trang tính1.csv` for assignment scope and dates; do not implement later tasks while working on the N4 toy motif demo.
- Protect the user's hardware: only one heavy workload at a time, including notebooks, Spark tests, ETL and LPA. Use the mandatory guard in `src/common/spark_session.py`; never bypass its CPU/RAM caps or raise resources to force a successful run. Read the hardware-protection section in the GraphGuard skill before computation. A pressure stop or abnormal noise/shutdown means stop heavy work and investigate; it is not permission for an automatic retry.
