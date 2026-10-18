"""Adversarial CSV checks using a known graph with parallel, cross and self-loop edges."""

import csv
from pathlib import Path
import tempfile
import unittest

from src.common.spark_session import get_graph_session
from src.common.graph_utils import load_graph
from src.ibm_aml.community_detection import run_lpa
from src.ibm_aml.verify_communities import (
    compare_partitions, verify_communities, verify_community_frames,
)


class Task4CheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = get_graph_session("GraphGuard-Task4-Checker-Tests", driver_memory="4g",
            shuffle_partitions=2, extra_configs={"spark.default.parallelism": "2"})
        cls.workspace = tempfile.TemporaryDirectory()
        cls.graph_dir = Path(cls.workspace.name) / "graph"
        vertices = cls.spark.sql("SELECT * FROM VALUES ('A','1',10.0), ('B','1',20.0), "
                                 "('C','2',30.0), ('D','3',40.0) AS v(id,bank_id,balance)")
        edges = cls.spark.sql("SELECT * FROM VALUES "
            "('A','B',100.0,'US Dollar',1), ('A','B',50.0,'Euro',0), "
            "('B','C',200.0,'US Dollar',0), ('C','C',300.0,'US Dollar',1), "
            "('C','A',70.0,'US Dollar',0) AS e(src,dst,amount,payment_currency,isFraud)")
        vertices.write.parquet(str(cls.graph_dir / "vertices.parquet"))
        edges.write.parquet(str(cls.graph_dir / "edges.parquet"))

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.workspace.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.tables = {
            "communities.csv": (["id", "bank_id", "label"],
                [["A", "1", "10"], ["B", "1", "10"], ["C", "2", "20"], ["D", "3", "30"]]),
            "community_summary_all.csv": (["label", "member_count", "unique_banks_count", "avg_balance",
                "total_tx_count", "laundering_tx_count", "internal_tx_count", "internal_laundering_count", "laundering_rate"],
                [["10", "2", "1", "15.0", "3", "1", "2", "1", "0.3333"],
                 ["20", "1", "1", "30.0", "2", "1", "1", "1", "0.5"],
                 ["30", "1", "1", "40.0", "0", "0", "0", "0", "0.0"]]),
            "community_amounts_by_currency.csv": (["label", "payment_currency", "total_tx_count", "total_tx_amount"],
                [["10", "Euro", "1", "50.0"], ["10", "US Dollar", "2", "300.0"], ["20", "US Dollar", "2", "370.0"]]),
        }
        header, rows = self.tables["community_summary_all.csv"]
        self.tables["community_summary.csv"] = (list(header), [list(row) for row in rows])

    def write_outputs(self):
        for name, (header, rows) in self.tables.items():
            with (self.output / name).open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(header)
                writer.writerows(rows)

    def verify(self):
        self.write_outputs()
        return verify_communities(self.spark, self.graph_dir, self.output)

    def test_valid_counts_include_parallel_edges_self_loop_and_isolated_account(self):
        metrics = self.verify()
        self.assertEqual((metrics["vertices"], metrics["communities"], metrics["edges"]), (4, 3, 5))
        self.assertEqual((metrics["internal_edges"], metrics["cross_edges"], metrics["fraud_edges"]), (3, 2, 2))

    def test_notebook_frames_reconcile_without_exporting_files(self):
        # Notebook tables have numeric labels already; CSV adapters use strings.
        from pyspark.sql import functions as F

        frames = {}
        for name, (header, rows) in self.tables.items():
            # Match the notebook's SQL/DataFrame execution path. PythonRDD
            # fixture construction would start an unrelated Python worker.
            values = ", ".join(
                "(" + ", ".join("'" + value.replace("'", "''") + "'" for value in row) + ")"
                for row in rows
            )
            frame = self.spark.sql(f"SELECT * FROM VALUES {values} AS fixture({', '.join(header)})")
            frames[name] = frame.withColumn("label", F.col("label").cast("long"))
        metrics = verify_community_frames(
            load_graph(self.spark, str(self.graph_dir)),
            frames["communities.csv"], frames["community_summary_all.csv"],
            frames["community_summary.csv"], frames["community_amounts_by_currency.csv"],
        )
        self.assertEqual((metrics["vertices"], metrics["communities"], metrics["edges"]), (4, 3, 5))
        self.assertEqual(list(self.output.iterdir()), [])

    def test_lpa_projection_preserves_account_coverage_and_vertex_metadata(self):
        graph = load_graph(self.spark, str(self.graph_dir))
        result = run_lpa(graph, self.spark, max_iter=5,
                         checkpoint_dir=Path(self.workspace.name) / "checkpoint")
        try:
            rows = result.select("id", "bank_id", "balance", "label").collect()
            self.assertEqual(sorted((row.id, row.bank_id, float(row.balance)) for row in rows),
                             [('A', '1', 10.0), ('B', '1', 20.0), ('C', '2', 30.0), ('D', '3', 40.0)])
            self.assertTrue(all(row.label is not None for row in rows))
        finally:
            result.unpersist()

    def test_missing_account_is_rejected(self):
        self.tables["communities.csv"][1].pop()
        with self.assertRaisesRegex(ValueError, "assignments: incomplete"):
            self.verify()

    def test_duplicate_account_is_rejected(self):
        self.tables["communities.csv"][1].append(["A", "1", "10"])
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            self.verify()

    def test_null_label_is_rejected(self):
        self.tables["communities.csv"][1][0][2] = ""
        with self.assertRaisesRegex(ValueError, "Invalid numeric"):
            self.verify()

    def test_foreign_account_is_rejected(self):
        self.tables["communities.csv"][1][-1][0] = "FOREIGN"
        with self.assertRaisesRegex(ValueError, "extra=1"):
            self.verify()

    def test_incomplete_summary_is_rejected(self):
        self.tables["community_summary_all.csv"][1].pop()
        with self.assertRaisesRegex(ValueError, "summary: incomplete"):
            self.verify()

    def test_inflated_fraud_count_is_rejected(self):
        self.tables["community_summary_all.csv"][1][0][5] = "2"
        with self.assertRaisesRegex(ValueError, "statistics differ"):
            self.verify()

    def test_mixed_currency_total_is_rejected(self):
        header, rows = self.tables["community_summary_all.csv"]
        header.append("total_tx_amount")
        for row in rows:
            row.append("1000.0")
        with self.assertRaisesRegex(ValueError, "payment_currency"):
            self.verify()

    def test_incorrect_currency_amount_is_rejected(self):
        self.tables["community_amounts_by_currency.csv"][1][0][3] = "51.0"
        with self.assertRaisesRegex(ValueError, "amounts by currency: statistics differ"):
            self.verify()

    def test_nan_amount_is_rejected(self):
        self.tables["community_amounts_by_currency.csv"][1][0][3] = "NaN"
        with self.assertRaisesRegex(ValueError, "Invalid numeric"):
            self.verify()

    def test_label_renumbering_is_same_partition(self):
        self.write_outputs()
        with tempfile.TemporaryDirectory() as name:
            previous = Path(name)
            with (previous / "communities.csv").open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerows([["id", "label"], ["A", "9007199254740993"],
                    ["B", "9007199254740993"], ["C", "9007199254740994"], ["D", "9007199254740995"]])
            self.assertTrue(compare_partitions(self.spark, self.output, previous)["same_partition"])

    def test_changed_membership_is_reported_without_requiring_fixed_label_numbers(self):
        self.write_outputs()
        with tempfile.TemporaryDirectory() as name:
            previous = Path(name)
            with (previous / "communities.csv").open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerows([["id", "label"], ["A", "10"], ["B", "20"], ["C", "20"], ["D", "30"]])
            comparison = compare_partitions(self.spark, self.output, previous)
            self.assertFalse(comparison["same_partition"])
            self.assertEqual(comparison["accounts_with_changed_canonical_community"], 2)


if __name__ == "__main__":
    unittest.main()
