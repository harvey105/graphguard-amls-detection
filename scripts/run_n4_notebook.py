r"""Execute the N4 notebook with the current Windows virtual environment.

PowerShell: & .\.venv\Scripts\python.exe scripts\run_n4_notebook.py
"""

from __future__ import annotations

import json
import argparse
import hashlib
from datetime import datetime, timezone
import os
from queue import Empty
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path
import time

from jupyter_client import KernelManager


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO_ROOT / "notebooks" / "02_n4_toy_motif.ipynb"
KERNEL_NAME = "graphguard-windows"
CELL_TIMEOUT = 2700


def notebook_source_hashes(notebook):
    """Read source bytes before execution without importing Spark in the runner."""
    names = set(notebook["metadata"].get("graphguard_source_sha256", {}))
    names.add("scripts/run_n4_notebook.py")
    return {name: hashlib.sha256((REPO_ROOT / name).read_bytes()).hexdigest()
            for name in sorted(names)}


def complete_execution(notebook, started_hashes):
    """Publish new provenance only after all cells ran against unchanged source."""
    if notebook_source_hashes(notebook) != started_hashes:
        raise RuntimeError("Source changed during notebook execution; rerun after edits are complete")
    notebook["metadata"]["graphguard_source_sha256"] = started_hashes
    notebook["metadata"].pop("graphguard_post_execution_whitespace", None)
    notebook["metadata"]["graphguard_execution"]["status"] = "completed"
    code_sources = ["".join(cell["source"]) for cell in notebook.get("cells", []) if cell["cell_type"] == "code"]
    notebook["metadata"]["graphguard_executed_code_sha256"] = hashlib.sha256(
        json.dumps(code_sources, ensure_ascii=False).encode("utf-8")).hexdigest()


def save_notebook(notebook):
    # Replace on the same filesystem only after a complete, flushed UTF-8/LF
    # write. An interrupted write must not truncate the previous saved notebook.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=NOTEBOOK.parent, prefix=".graphguard-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write((json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, NOTEBOOK)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    if os.name != "nt":
        raise RuntimeError("Run this notebook with Windows PowerShell and Windows Python.")

    subprocess.run(
        [
            sys.executable, "-m", "ipykernel", "install",
            "--prefix", sys.prefix, "--name", KERNEL_NAME,
            "--display-name", "GraphGuard (.venv Windows)",
        ],
        check=True,
    )
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    started_hashes = notebook_source_hashes(notebook)
    notebook["metadata"]["kernelspec"] = {
        "display_name": "GraphGuard (.venv Windows)",
        "language": "python",
        "name": KERNEL_NAME,
    }
    notebook["metadata"]["graphguard_execution"] = {"status": "running", "completed_code_cells": 0}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []

    manager = KernelManager(kernel_name=KERNEL_NAME)
    manager.session.key = secrets.token_hex(32).encode("ascii")
    manager.start_kernel(cwd=str(NOTEBOOK.parent))
    client = manager.client()
    client.start_channels()
    try:
        client.wait_for_ready(timeout=180)
        execution_count = 0
        for cell in notebook["cells"]:
            if cell["cell_type"] != "code":
                continue
            execution_count += 1
            cell["execution_count"] = execution_count
            cell["outputs"] = []
            message_id = client.execute("".join(cell["source"]), allow_stdin=False)
            deadline = time.monotonic() + CELL_TIMEOUT
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Notebook cell {execution_count} exceeded {CELL_TIMEOUT} seconds; no automatic retry")
                try:
                    message = client.get_iopub_msg(timeout=5)
                except Empty:
                    if not manager.is_alive():
                        raise RuntimeError("Notebook kernel stopped; inspect resource guard/system state before retry")
                    continue
                if message["parent_header"].get("msg_id") != message_id:
                    continue
                kind = message["msg_type"]
                content = message["content"]
                if kind == "stream":
                    output = {
                        "output_type": "stream",
                        "name": content["name"],
                        "text": content["text"],
                    }
                    cell["outputs"].append(output)
                    for line in content["text"].splitlines():
                        if line.startswith(("Features:", "Validation ", "Refit frozen", "[RESOURCE", "[SYSTEM]")):
                            print(line, flush=True)
                elif kind in ("display_data", "execute_result"):
                    output = {
                        "output_type": kind,
                        "data": content["data"],
                        "metadata": content.get("metadata", {}),
                    }
                    if kind == "execute_result":
                        output["execution_count"] = execution_count
                    cell["outputs"].append(output)
                elif kind == "error":
                    cell["outputs"].append({
                        "output_type": "error",
                        "ename": content["ename"],
                        "evalue": content["evalue"],
                        "traceback": content["traceback"],
                    })
                    raise RuntimeError(
                        f"Notebook cell {execution_count}: "
                        f"{content['ename']}: {content['evalue']}"
                    )
                elif kind == "status" and content["execution_state"] == "idle":
                    break
            notebook["metadata"]["graphguard_execution"]["completed_code_cells"] = execution_count
            save_notebook(notebook)
            print(f"Cell {execution_count}: PASS", flush=True)
        complete_execution(notebook, started_hashes)
    except BaseException as error:
        notebook["metadata"]["graphguard_execution"].update(status="failed", error=str(error))
        raise
    finally:
        notebook["metadata"]["graphguard_execution"]["saved_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            client.stop_channels()
            manager.shutdown_kernel(now=True)
        finally:
            # Admission failure in cell 1 must retain the prior saved evidence.
            if notebook["metadata"]["graphguard_execution"]["completed_code_cells"]:
                save_notebook(notebook)
    print(f"Notebook saved: {NOTEBOOK}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=NOTEBOOK)
    parser.add_argument("--cell-timeout", type=int, default=CELL_TIMEOUT)
    arguments = parser.parse_args()
    if arguments.cell_timeout < 60:
        parser.error("--cell-timeout must be at least 60 seconds")
    CELL_TIMEOUT = arguments.cell_timeout
    NOTEBOOK = arguments.notebook.resolve()
    main()
