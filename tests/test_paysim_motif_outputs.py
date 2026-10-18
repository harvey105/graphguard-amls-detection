import csv
from pathlib import Path
import shutil
import tempfile
import unittest

from src.paysim.verify_motif_outputs import compare_outputs, verify_outputs


BASELINE = Path(__file__).resolve().parents[1] / "results/paysim"


class PaySimOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        for name in ("motif_summary.csv", "relay_candidates.csv"):
            shutil.copyfile(BASELINE / name, self.output / name)

    def modify_rows(self, change):
        path = self.output / "relay_candidates.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        change(rows)
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_delivered_csv_passes(self):
        compare_outputs(self.output, BASELINE)

    def test_missing_row_is_rejected(self):
        self.modify_rows(lambda rows: rows.pop())
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            verify_outputs(self.output)

    def test_amount_equal_to_threshold_is_rejected(self):
        self.modify_rows(lambda rows: rows[0].update(transfer_amount="10000"))
        with self.assertRaisesRegex(ValueError, "amount"):
            verify_outputs(self.output)

    def test_reverse_time_is_rejected(self):
        self.modify_rows(lambda rows: rows[0].update(cashout_step="23"))
        with self.assertRaisesRegex(ValueError, "time window"):
            verify_outputs(self.output)
