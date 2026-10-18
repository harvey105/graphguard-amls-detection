"""Record native runtime, code and input/output fingerprints for a checked run."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import uuid


REPO_ROOT = Path(__file__).resolve().parents[2]


def file_fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def input_fingerprint(path: Path) -> dict:
    if path.is_file():
        return file_fingerprint(path)
    files = sorted(file for file in path.rglob("*.parquet") if file.is_file())
    if not files:
        raise ValueError(f"No Parquet files in {path}")
    members = [{**file_fingerprint(file), "path": file.relative_to(path).as_posix()}
               for file in files]
    content = json.dumps(members, sort_keys=True).encode("utf-8")
    return {"path": str(path), "files": members, "sha256": hashlib.sha256(content).hexdigest()}


def write_run_evidence(
    path: Path, spark, *, task: str, inputs: list[Path], outputs: list[Path],
    sources: list[Path], parameters: dict, metrics: dict,
) -> dict:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                capture_output=True, text=True, check=True)
        revision = result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    manifest = {
        "status": "PASS", "task": task, "run_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification": "automated run; does not record human reviewer approval",
        "git_revision": revision,
        # Source hashes describe working-tree changes even when HEAD is unchanged.
        "sources": [file_fingerprint(source) for source in sources],
        "runtime": {
            "system": platform.system(), "python": platform.python_version(),
            "python_executable": sys.executable, "spark": spark.version,
            "graphframes": importlib.metadata.version("graphframes-py"),
            "java": spark.sparkContext._jvm.java.lang.System.getProperty("java.version"),
            "spark_master": spark.sparkContext.master,
            "driver_memory": spark.sparkContext.getConf().get("spark.driver.memory", "unknown"),
            "java_max_heap_bytes": spark.sparkContext._jvm.java.lang.Runtime.getRuntime().maxMemory(),
        },
        "parameters": parameters, "metrics": metrics,
        "inputs": [input_fingerprint(source) for source in inputs],
        "outputs": [file_fingerprint(output) for output in outputs],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_run_evidence(path: Path, *, task: str) -> dict:
    """Reject a stale or edited manifest/output set before claiming reproducibility."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("task") != task:
        raise ValueError("Unexpected run status/task")
    runtime = manifest["runtime"]
    if (runtime["system"] != "Windows" or not runtime["python"].startswith("3.12.")
            or runtime["spark"] != "3.5.1" or runtime["graphframes"] != "0.12.2"
            or not runtime["java"].startswith("17.")):
        raise ValueError("Run evidence does not match the required Windows runtime")
    for output in manifest["outputs"]:
        actual = file_fingerprint(path.parent / Path(output["path"]).name)
        if actual["sha256"] != output["sha256"]:
            raise ValueError(f"Output hash changed: {output['path']}")
    for source in manifest["sources"]:
        if file_fingerprint(Path(source["path"]))["sha256"] != source["sha256"]:
            raise ValueError(f"Source hash changed: {source['path']}")
    for source in manifest["inputs"]:
        if input_fingerprint(Path(source["path"]))["sha256"] != source["sha256"]:
            raise ValueError(f"Input hash changed: {source['path']}")
    return manifest
