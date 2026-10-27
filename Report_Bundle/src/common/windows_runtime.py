"""Prepare native Windows Spark for this repository's Unicode path."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _java_home() -> Path:
    candidate = os.environ.get("JAVA_HOME")
    if candidate and (Path(candidate) / "bin" / "java.exe").is_file():
        return Path(candidate)

    import winreg

    key_name = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    for hive, key_path in ((winreg.HKEY_LOCAL_MACHINE, key_name),
                           (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                candidate = winreg.QueryValueEx(key, "JAVA_HOME")[0]
        except OSError:
            continue
        if (Path(candidate) / "bin" / "java.exe").is_file():
            return Path(candidate)
    raise RuntimeError("JDK 17 Windows not found. Install it and set JAVA_HOME.")


def _short_repo_path(repo: Path) -> Path:
    for letter in "GZYXWVUTSRQPONMLKJIH":
        drive = Path(f"{letter}:\\")
        if drive.exists():
            try:
                if os.path.samefile(drive, repo):
                    return drive
            except OSError:
                pass
            continue
        result = subprocess.run(
            ["subst.exe", f"{letter}:", str(repo)],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return drive
    raise RuntimeError("No free Windows drive letter for Spark path mapping.")


def prepare_windows_spark() -> None:
    """Map the repo to an ASCII drive and configure Java/Hadoop/Spark paths."""
    if os.name != "nt":
        return

    repo = Path(__file__).resolve().parents[2]
    short_repo = _short_repo_path(repo)
    venv = short_repo / ".venv"
    python = venv / "Scripts" / "python.exe"
    spark_home = venv / "Lib" / "site-packages" / "pyspark"
    hadoop_home = venv / "hadoop"
    winutils = hadoop_home / "bin" / "winutils.exe"
    for path in (python, spark_home, winutils):
        if not path.exists():
            raise RuntimeError(
                f"Missing {path}. Run the PowerShell setup in README.md."
            )

    java_home = _java_home()
    os.environ["JAVA_HOME"] = str(java_home)
    os.environ["HADOOP_HOME"] = str(hadoop_home)
    os.environ["SPARK_HOME"] = str(spark_home)
    os.environ["PYSPARK_PYTHON"] = str(python)
    os.environ["PYTHONUTF8"] = "1"
    prefixes = (venv / "Scripts", java_home / "bin", hadoop_home / "bin")
    os.environ["PATH"] = os.pathsep.join(map(str, prefixes)) + os.pathsep + os.environ["PATH"]

    # Spark's Windows batch launcher also uses the current directory. A
    # notebook commonly starts in notebooks/ instead of the repository root.
    os.chdir(short_repo)
