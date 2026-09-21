---
name: graphguard-powershell
description: Use when setting up, running, documenting, or verifying GraphGuard code and notebooks for the team's native Windows PowerShell workflow.
---

# GraphGuard PowerShell workflow

- Use native Windows PowerShell 5.1+ to set up, run, and verify this project; do not use WSL as the project runtime. Resolve paths from the repository root and quote or use `Join-Path` for directories with spaces and Vietnamese text.
- Use a Windows Python 3.12 virtual environment at `.venv`, install `requirements.txt` there, and run modules with `& .\.venv\Scripts\python.exe ...` so activation and execution policy changes are unnecessary.
- Run `scripts/setup_windows.ps1` to install pinned Python requirements and verified Hadoop 3.3.4 native tools into `.venv`. Use `src/common/windows_runtime.py` for Spark environment setup, including JDK 17, Hadoop, the Windows Python worker, and a `subst` alias for repository paths with spaces or Vietnamese text.
- Prefer `scripts/run_n4.ps1` for the 21/9 N4 demo. Run other Python modules with `& .\.venv\Scripts\python.exe -m ...` from Windows PowerShell.
- For notebooks, select the Windows `.venv` kernel, execute the cells with that interpreter, and save real outputs. Refresh environment and status labels when changing the execution platform.
- Check `pip check`, the relevant module, and notebook execution before reporting PASS. State the precise missing prerequisite when native Windows verification cannot finish.
- Keep Python algorithm code in Python and assignment boundaries from `BDA - PCCV - Trang tính1.csv`. Use PowerShell for setup and run scripts.
