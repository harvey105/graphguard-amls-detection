"""Atomic notebook saving: retain prior evidence if replacement fails."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_n4_notebook as runner


class CheckpointTests(unittest.TestCase):
    def test_replacement_saves_utf8_without_temp_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trình bày.ipynb"
            with patch.object(runner, "NOTEBOOK", path):
                runner.save_notebook({"status": "đã chạy"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "đã chạy"})
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_failed_replace_preserves_previous_notebook(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notebook.ipynb"
            path.write_bytes(b'{"previous":"real output"}\n')
            previous = path.read_bytes()
            with patch.object(runner, "NOTEBOOK", path), patch.object(runner.os, "replace", side_effect=OSError("simulated failure")):
                with self.assertRaises(OSError):
                    runner.save_notebook({"new": "incomplete"})
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(path.parent.iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
