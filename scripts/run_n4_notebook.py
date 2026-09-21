r"""Execute the N4 notebook with the current Windows virtual environment.

PowerShell: & .\.venv\Scripts\python.exe scripts\run_n4_notebook.py
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

from jupyter_client import KernelManager


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO_ROOT / "notebooks" / "02_n4_toy_motif.ipynb"
KERNEL_NAME = "graphguard-windows"


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
    notebook["metadata"]["kernelspec"] = {
        "display_name": "GraphGuard (.venv Windows)",
        "language": "python",
        "name": KERNEL_NAME,
    }
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
    NOTEBOOK.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )

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
            while True:
                message = client.get_iopub_msg(timeout=600)
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
            print(f"Cell {execution_count}: PASS")
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)
        NOTEBOOK.write_text(
            json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
    print(f"Notebook saved: {NOTEBOOK}")


if __name__ == "__main__":
    main()
