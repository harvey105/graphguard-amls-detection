"""Review the upstream documented-cycle figure without changing its detection scope."""

import copy
import csv
from pathlib import Path
import tempfile
import unittest

from src.ibm_aml.visualize import ROOT, read_three_account_cycles, select_example


class IbmCycleVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cycles = read_three_account_cycles(ROOT / "data/raw/ibm_aml/HI-Small_Patterns.txt")
        cls.cycle_csv = ROOT / "results/ibm_aml/fraud_directed_cycles.csv"

    def test_real_source_example_is_chronological_and_currency_qualified(self):
        self.assertEqual(len(self.cycles), 9)
        payments = select_example(self.cycles, self.cycle_csv)
        self.assertEqual({payment["payment_currency"] for payment in payments}, {"Saudi Riyal"})
        self.assertEqual([payment["source_line"] for payment in payments], [2070, 2071, 2072])
        self.assertTrue(payments[0]["timestamp"] < payments[1]["timestamp"] < payments[2]["timestamp"])

    def test_reverse_time_example_is_rejected(self):
        payments = copy.deepcopy(select_example(self.cycles, self.cycle_csv))
        payments[1]["timestamp"] = payments[0]["timestamp"]
        with self.assertRaisesRegex(ValueError, "No suitable"):
            select_example([payments], self.cycle_csv)

    def test_mixed_currency_example_is_rejected(self):
        payments = copy.deepcopy(select_example(self.cycles, self.cycle_csv))
        payments[1]["payment_currency"] = "US Dollar"
        with self.assertRaisesRegex(ValueError, "No suitable"):
            select_example([payments], self.cycle_csv)

    def test_cycle_missing_from_motif_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                csv.writer(stream).writerow(["a", "b", "c", "transaction_combinations"])
            with self.assertRaisesRegex(ValueError, "No suitable"):
                select_example(self.cycles, path)


if __name__ == "__main__":
    unittest.main()
