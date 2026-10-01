"""Small malformed CSV cases for the IBM HI-Small ETL review fixes."""

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.common.spark_session import get_graph_session
from src.ibm_aml.etl import (
    ACCOUNTS_HEADER, TRANS_HEADER, build_ibm_edges, build_ibm_vertices,
    invalid_required_values,
)


class IbmEtlGuardrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = get_graph_session(app_name="IBM-ETL-Guardrails")
        cls.temp_dir = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp_dir.cleanup()

    def csv_path(self, name, header, rows):
        path = Path(self.temp_dir.name) / name
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)
        return str(path)

    def test_duplicate_account_header_must_stay_in_original_positions(self):
        bad = TRANS_HEADER.copy()
        bad[4] = "Account Destination"
        path = self.csv_path("bad_trans.csv", bad, [])
        with self.assertRaisesRegex(ValueError, "Unexpected CSV header"):
            build_ibm_edges(self.spark, path)

    def test_accounts_header_is_checked(self):
        path = self.csv_path("bad_accounts.csv", ACCOUNTS_HEADER[::-1], [])
        with self.assertRaisesRegex(ValueError, "Unexpected CSV header"):
            build_ibm_vertices(self.spark, path, self.spark.createDataFrame([], "src string, dst string"))

    def test_missing_bank_and_bad_casts_are_visible_to_quality_gate(self):
        row = [
            "bad timestamp", "", "ACCOUNT_A", "001", "ACCOUNT_B", "bad amount",
            "US Dollar", "10.5", "US Dollar", "Wire", "bad label",
        ]
        path = self.csv_path("invalid_trans.csv", TRANS_HEADER, [row])
        edges = build_ibm_edges(self.spark, path)
        counts = invalid_required_values(edges, edges.columns)
        for name in ("src", "amount_received", "step", "timestamp", "isFraud", "isLaundering"):
            self.assertEqual(counts[name], 1, name)
        self.assertEqual(counts["dst"], 0)


if __name__ == "__main__":
    unittest.main()
