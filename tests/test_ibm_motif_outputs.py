"""Check that the delivery gate rejects corrupted or incomplete CSV artifacts."""

import csv
from pathlib import Path
import shutil
import tempfile
import unittest

from src.ibm_aml.verify_motif_outputs import compare_outputs, verify_outputs


BASELINE = Path(__file__).resolve().parents[1] / "results" / "ibm_aml"


class IbmMotifOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for filename in ("motif_summary.csv", "fraud_directed_cycles.csv", "fraud_currency_counts.csv"):
            shutil.copyfile(BASELINE / filename, self.directory / filename)

    def change_cycles(self, change):
        path = self.directory / "fraud_directed_cycles.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            header, rows = reader.fieldnames, list(reader)
        change(rows)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)

    def test_full_delivered_csv_passes(self):
        compare_outputs(self.directory, BASELINE)

    def test_missing_cycle_is_rejected(self):
        self.change_cycles(lambda rows: rows.pop())
        with self.assertRaisesRegex(ValueError, "truncated"):
            verify_outputs(self.directory)

    def test_inflated_multiplicity_is_rejected(self):
        self.change_cycles(lambda rows: rows[0].update(transaction_combinations="491"))
        with self.assertRaisesRegex(ValueError, "Edge combinations"):
            verify_outputs(self.directory)

    def test_duplicate_cycle_is_rejected(self):
        self.change_cycles(lambda rows: rows.__setitem__(1, dict(rows[0])))
        with self.assertRaisesRegex(ValueError, "duplicates"):
            verify_outputs(self.directory)


if __name__ == "__main__":
    unittest.main()
