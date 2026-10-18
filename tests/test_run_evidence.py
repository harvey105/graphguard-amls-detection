import json
from pathlib import Path
import tempfile
import unittest

from src.common.run_evidence import file_fingerprint, input_fingerprint, verify_run_evidence


class RunEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        self.input = directory / "input"
        self.input.mkdir()
        parquet_dir = self.input / "edges.parquet"
        parquet_dir.mkdir()
        self.parquet = parquet_dir / "part.parquet"
        self.parquet.write_bytes(b"fingerprint fixture, not a runnable graph")
        self.output = directory / "output.csv"
        self.output.write_text("a,b\n1,2\n", encoding="utf-8")
        self.source = directory / "source.py"
        self.source.write_text("# fingerprint fixture\n", encoding="utf-8")
        self.manifest = directory / "run.json"
        # Synthetic manifest for validation tests; it is not execution evidence.
        self.record = {"status": "PASS", "task": "fixture",
            "runtime": {"system": "Windows", "python": "3.12.10", "spark": "3.5.1",
                        "graphframes": "0.12.2", "java": "17.0.20.1"},
            "inputs": [input_fingerprint(self.input)], "outputs": [file_fingerprint(self.output)],
            "sources": [file_fingerprint(self.source)]}
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(self.record), encoding="utf-8")

    def test_matching_fingerprints_pass(self):
        verify_run_evidence(self.manifest, task="fixture")

    def test_fingerprint_skips_parquet_directories_and_crc_markers(self):
        (self.parquet.parent / ".part.parquet.crc").write_bytes(b"CRC marker")
        (self.parquet.parent / "_SUCCESS").write_bytes(b"")
        fingerprint = input_fingerprint(self.input)
        self.assertEqual([member["path"] for member in fingerprint["files"]], ["edges.parquet/part.parquet"])

    def test_changed_output_is_rejected(self):
        self.output.write_text("a,b\n1,3\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Output hash changed"):
            verify_run_evidence(self.manifest, task="fixture")

    def test_changed_input_is_rejected(self):
        self.parquet.write_bytes(b"changed input")
        with self.assertRaisesRegex(ValueError, "Input hash changed"):
            verify_run_evidence(self.manifest, task="fixture")

    def test_changed_source_is_rejected(self):
        self.source.write_text("# changed implementation\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Source hash changed"):
            verify_run_evidence(self.manifest, task="fixture")

    def test_linux_run_is_not_windows_evidence(self):
        self.record["runtime"]["system"] = "Linux"
        self.save()
        with self.assertRaisesRegex(ValueError, "Windows runtime"):
            verify_run_evidence(self.manifest, task="fixture")
