"""Small GraphFrame checks for the Week 2 N4 motif counting rules."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graphframes import GraphFrame

from src.common.spark_session import get_graph_session
from src.ibm_aml.motif_finding import directed_account_cycles, find_usd_cycles
from src.motif.toy_cycle import find_three_node_cycles
from src.paysim.motif_finding import find_relays


class Task3MotifTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = get_graph_session(
            "GraphGuard-Task3-Tests", shuffle_partitions=2,
            extra_configs={"spark.sql.adaptive.enabled": "false",
                           "spark.default.parallelism": "2"},
        )

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_parallel_edges_and_opposite_orientations(self):
        vertices = self.spark.sql(
            "SELECT * FROM VALUES ('A'), ('B'), ('C') AS v(id)"
        )
        edges = self.spark.sql(
            "SELECT * FROM VALUES ('A','B'), ('A','B'), ('B','C'), "
            "('C','A'), ('A','C'), ('C','B'), ('B','A'), ('A','A') "
            "AS e(src,dst)"
        )
        cycles = find_three_node_cycles(GraphFrame(vertices, edges))
        self.assertEqual(cycles.count(), 9)
        directed = directed_account_cycles(cycles).collect()
        self.assertEqual(len(directed), 2)
        self.assertEqual(sorted(row.transaction_combinations for row in directed), [1, 2])

    def test_relay_requires_amount_distinct_accounts_and_time_window(self):
        vertices = self.spark.sql(
            "SELECT * FROM VALUES ('A'), ('B'), ('C'), ('D'), ('E') AS v(id)"
        )
        edges = self.spark.sql(
            "SELECT * FROM VALUES "
            "('A','B','TRANSFER',12000.0,10), "
            "('B','C','CASH_OUT',11000.0,12), "
            "('B','D','CASH_OUT',11000.0,10), "
            "('B','E','CASH_OUT',11000.0,40), "
            "('B','D','CASH_OUT',9000.0,12), "
            "('B','A','CASH_OUT',11000.0,12) "
            "AS e(src,dst,type,amount,step)"
        )
        graph = GraphFrame(vertices, edges)
        self.assertEqual(find_relays(graph, 10_000.0, 24).count(), 2)
        self.assertEqual(find_relays(graph, 10_000.0, 24, strict_time=True).count(), 1)

    def test_two_account_cycle_and_self_loop_are_not_three_node_cycles(self):
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'), ('B') AS v(id)")
        edges = self.spark.sql(
            "SELECT * FROM VALUES ('A','B'), ('B','A'), ('A','A') AS e(src,dst)"
        )
        self.assertEqual(find_three_node_cycles(GraphFrame(vertices, edges)).count(), 0)

    def test_usd_threshold_applies_to_every_edge_without_label_filter(self):
        vertices = self.spark.sql(
            "SELECT * FROM VALUES ('A'), ('B'), ('C'), ('D'), ('E'), ('F'), "
            "('G'), ('H'), ('I') AS v(id)"
        )
        edges = self.spark.sql(
            "SELECT * FROM VALUES "
            "('A','B',11000.0,'US Dollar',0), ('B','C',12000.0,'US Dollar',1), "
            "('C','A',13000.0,'US Dollar',0), "
            "('D','E',11000.0,'US Dollar',1), ('E','F',10000.0,'US Dollar',1), "
            "('F','D',13000.0,'US Dollar',1), "
            "('G','H',11000.0,'US Dollar',1), ('H','I',12000.0,'Euro',1), "
            "('I','G',13000.0,'US Dollar',1) "
            "AS e(src,dst,amount,payment_currency,isFraud)"
        )
        graph = GraphFrame(vertices, edges)
        cycles = directed_account_cycles(find_usd_cycles(graph, 10_000.0)).collect()
        self.assertEqual([(row.a, row.b, row.c) for row in cycles], [('A', 'B', 'C')])
        for invalid in (float('nan'), float('inf'), -1.0):
            with self.assertRaises(ValueError):
                find_usd_cycles(graph, invalid)

    def test_relay_boundary_strict_threshold_reverse_time_and_labels(self):
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'), ('B'), ('D'), ('E'), ('F'), ('X') AS v(id)")
        edges = self.spark.sql("SELECT * FROM VALUES "
            "('A','B','TRANSFER',10000.0,10,0), ('X','B','TRANSFER',11000.0,10,1), "
            "('B','A','CASH_OUT',10000.0,12,0), ('B','D','CASH_OUT',11000.0,10,0), "
            "('B','E','CASH_OUT',11000.0,34,0), ('B','F','CASH_OUT',11000.0,35,0), "
            "('B','A','CASH_OUT',11000.0,9,0), ('B','X','CASH_OUT',11000.0,12,0) "
            "AS e(src,dst,type,amount,step,isFraud)")
        graph = GraphFrame(vertices, edges)
        rows = find_relays(graph, 10000.0, 24).select("c.id").collect()
        self.assertEqual(sorted(row.id for row in rows), ['D', 'E'])
        self.assertEqual(find_relays(graph, 10000.0, 24, strict_time=True).count(), 1)
        for invalid in (float('nan'), float('inf'), -1.0):
            with self.assertRaises(ValueError):
                find_relays(graph, invalid, 24)


if __name__ == "__main__":
    unittest.main()
