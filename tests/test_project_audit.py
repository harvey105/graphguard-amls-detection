"""Bounded negative checks and protected native Windows algorithm verification."""

from collections import Counter
import copy
import unittest

from src.common.project_audit import notebook_tables, reference_pagerank, verify_communities, verify_top10


class ProjectAuditTests(unittest.TestCase):
    def setUp(self):
        self.vertices = {key: {"id": key, "account_type": kind, "balance": 10.0}
                         for key, kind in (("A", "Customer"), ("B", "Merchant"), ("C", "Customer"))}
        self.edges = [{"src": "A", "dst": "B", "isFraud": 1},
                      {"src": "A", "dst": "B", "isFraud": 0},
                      {"src": "B", "dst": "B", "isFraud": 0}]
        self.assignments = [{**row, "label": "10" if key != "C" else "20"} for key, row in self.vertices.items()]
        self.summary = [{"label": "10", "member_count": "2", "customer_count": "1", "merchant_count": "1",
                         "total_tx_count": "3", "fraud_tx_count": "1", "internal_tx_count": "3",
                         "internal_fraud_count": "1", "fraud_rate": "0.3333", "avg_balance": "10.0"},
                        {"label": "20", "member_count": "1", "customer_count": "1", "merchant_count": "0",
                         "total_tx_count": "0", "fraud_tx_count": "0", "internal_tx_count": "0",
                         "internal_fraud_count": "0", "fraud_rate": "0.0", "avg_balance": "10.0"}]

    def test_community_counts_preserve_parallel_edges_self_loops_and_isolate(self):
        result = verify_communities(self.assignments, self.summary, self.vertices, self.edges, "paysim")
        self.assertEqual(result["communities"], 2)
        self.assertEqual(result["assigned_accounts"], 3)

    def test_zero_type_counts_with_nonempty_members_are_rejected(self):
        self.summary[0].update(customer_count="0", merchant_count="0")
        with self.assertRaisesRegex(ValueError, "customer_count: saved=0, expected=1"):
            verify_communities(self.assignments, self.summary, self.vertices, self.edges, "paysim")

    def test_wrong_fraud_count_is_rejected(self):
        self.summary[0]["fraud_tx_count"] = "2"
        with self.assertRaisesRegex(ValueError, "fraud_tx_count"):
            verify_communities(self.assignments, self.summary, self.vertices, self.edges, "paysim")

    def test_duplicate_assignments_are_rejected(self):
        self.assignments[-1] = copy.deepcopy(self.assignments[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verify_communities(self.assignments, self.summary, self.vertices, self.edges, "paysim")

    def test_truncated_community_summary_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Truncated"):
            verify_communities(self.assignments, self.summary[:1], self.vertices, self.edges, "paysim")

    def test_mixed_currency_nominal_total_is_rejected(self):
        for i, edge in enumerate(self.edges):
            edge["payment_currency"] = "USD" if i else "EUR"
        self.summary[0]["total_tx_amount"] = "100"
        with self.assertRaisesRegex(ValueError, "mixes 2 currencies"):
            verify_communities(self.assignments, self.summary, self.vertices, self.edges, "ibm_aml")

    def test_complete_summary_cannot_omit_communities(self):
        with self.assertRaisesRegex(ValueError, "omits"):
            verify_communities(self.assignments, self.summary, self.vertices, self.edges, "paysim", iter(self.summary[:1]))

    def test_complete_summary_checks_rows_beyond_the_display_view(self):
        full = copy.deepcopy(self.summary)
        full[1]["total_tx_count"] = "99"
        with self.assertRaisesRegex(ValueError, "total_tx_count"):
            verify_communities(self.assignments, self.summary, self.vertices, self.edges, "paysim", iter(full))

    def test_streamed_csv_preserves_previous_file_on_partition_failure(self):
        import tempfile
        from pathlib import Path
        from src.common.graph_utils import write_spark_csv
        class BrokenFrame:
            columns = ["id"]
            def toLocalIterator(self, prefetchPartitions=False):
                yield ["A"]
                raise ValueError("broken partition")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"
            path.write_bytes(b"previous\n")
            with self.assertRaisesRegex(ValueError, "broken partition"):
                write_spark_csv(BrokenFrame(), path)
            self.assertEqual(path.read_bytes(), b"previous\n")
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_temporal_split_releases_materialized_history(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock, patch
        from src.common.project_audit import evaluate_component_signals

        indexed = MagicMock()
        truth = indexed.select.return_value.localCheckpoint.return_value
        indexed.drop.return_value.approxQuantile.return_value = [1, 1, 1]
        with tempfile.TemporaryDirectory() as directory, \
             patch("src.common.project_audit.parquet_info", return_value=(None, 10, None)), \
             patch("src.common.graph_utils.load_graph"), patch("src.motif.features.normalize_edges"), \
             patch("src.motif.evaluation.index_transactions", return_value=indexed):
            with self.assertRaisesRegex(ValueError, "distinct time boundaries"):
                evaluate_component_signals(MagicMock(), "ibm_aml", "centrality", Path(directory), Path(directory) / "output")
        indexed.unpersist.assert_called_once()
        truth.unpersist.assert_called_once()

    def test_component_evidence_checks_float_labels_and_frozen_rule(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import pandas as pd
        from src.common.project_audit import verify_component_report
        from src.motif.evaluation import binary_metrics

        validation = [{"fold": fold, "family": "degree_high", "threshold": .9, "cut_value": 5.,
                       **binary_metrics(3, 1, 1, 1)} for fold in (1, 2)]
        rule = {"family": "degree_high", "threshold": .9, "score": "degree_score", "cut_value": 5., "direction": "high"}
        report = {"dataset": "ibm_aml", "branch": "centrality", "cutoffs": [1, 2, 3],
                  "scope": "unit fixture", "selection": {"family": "degree_high", "threshold": .9},
                  "final_rule": rule, "selected_test_metrics": binary_metrics(2, 1, 1, 0)}
        with tempfile.TemporaryDirectory() as directory, \
             patch("src.common.run_evidence.verify_run_evidence", return_value={"run_id": "fixture"}):
            root = Path(directory)
            pd.DataFrame(validation).to_csv(root / "validation.csv", index=False)
            (root / "test_predictions.csv").write_text(
                "event_id,step,isFraud,alert,degree_score\n1,4,1.0,true,6\n2,5,0.0,false,0\n", encoding="utf-8")
            (root / "account_snapshot.csv").write_text("id,as_of_step\nA,3\n", encoding="utf-8")
            (root / "report.json").write_text(json.dumps(report), encoding="utf-8")
            checked = verify_component_report(root, "ibm_aml", "centrality")
            self.assertEqual((checked["TP"], checked["FP"], checked["FN"], checked["TN"]), (1, 0, 0, 1))
            # Updating the test threshold after looking at test labels must fail.
            report["final_rule"]["threshold"] = .99
            (root / "report.json").write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differs from validation"):
                verify_component_report(root, "ibm_aml", "centrality")

    def test_equal_validation_scores_prefer_novelty_baseline(self):
        import pandas as pd
        from src.motif.evaluation import binary_metrics
        from src.motif.modeling import choose_walk_forward_rule

        rows = [{"fold": fold, "family": family, "threshold": threshold,
                 **binary_metrics(100, 10, 5, 5)}
                for fold in (1, 2) for family, threshold in (("novelty", 1.), ("community_size_low", .1))]
        selected, _ = choose_walk_forward_rule(pd.DataFrame(rows))
        self.assertEqual(selected["family"], "novelty")
        # Prefer structural evidence when it actually improves validation F1.
        for row in rows:
            if row["family"] == "community_size_low":
                row.update(binary_metrics(100, 10, 6, 5))
        selected, _ = choose_walk_forward_rule(pd.DataFrame(rows))
        self.assertEqual(selected["family"], "community_size_low")


    def test_graphx_fixed_iteration_reference_uses_rank_sum_N(self):
        # After >=3 updates on A->B->C plus isolated D, raw scores are
        # [0.15, 0.2775, 0.385875, 0.15], followed by GraphX's correction to N.
        vertices = dict.fromkeys("ABCD")
        edges = [{"src": "A", "dst": "B"}, {"src": "B", "dst": "C"}]
        scores = reference_pagerank(vertices, edges, Counter({"A": 1, "B": 1}))
        for key, raw in zip("ABCD", (0.15, 0.2775, 0.385875, 0.15)):
            self.assertAlmostEqual(scores[key], raw * 4 / 0.963375)
        self.assertAlmostEqual(sum(scores.values()), 4)

    def test_parallel_weights_and_self_loop_reference(self):
        edges = [*self.edges, {"src": "A", "dst": "C"}]
        scores = reference_pagerank(self.vertices, edges, Counter({"A": 3, "B": 1}), iterations=1)
        raw = {"A": 0.15, "B": 0.15 + 0.85 * (2 / 3 + 1), "C": 0.15 + 0.85 / 3}
        for key in raw:
            self.assertAlmostEqual(scores[key], raw[key] * 3 / sum(raw.values()))

    def test_truncated_top10_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ten distinct"):
            verify_top10([], self.vertices, self.edges, Counter(), Counter())

    def test_top10_fraud_annotations_are_reconciled_with_transactions(self):
        vertices = {**self.vertices, **dict.fromkeys("DEFGHIJ")}
        incoming = Counter(edge["dst"] for edge in self.edges)
        outgoing = Counter(edge["src"] for edge in self.edges)
        ranks = reference_pagerank(vertices, self.edges, outgoing)
        rows = [{"id": key, "pagerank": score, "inDegree": incoming[key], "outDegree": outgoing[key],
                 "degree": incoming[key] + outgoing[key], "incoming_fraud_tx": int(key == "B"),
                 "outgoing_fraud_tx": int(key == "A")}
                for key, score in sorted(ranks.items(), key=lambda pair: (-pair[1], pair[0]))]
        verify_top10(rows, vertices, self.edges, incoming, outgoing)
        next(row for row in rows if row["id"] == "A")["outgoing_fraud_tx"] = 0
        with self.assertRaisesRegex(ValueError, "outgoing_fraud_tx"):
            verify_top10(rows, vertices, self.edges, incoming, outgoing)

    def test_html_metrics_reading_ignores_row_index(self):
        html = "<table><tr><th></th><th>TP</th><th>FP</th></tr><tr><th>0</th><td>3</td><td>2</td></tr></table>"
        notebook = {"cells": [{"outputs": [{"data": {"text/html": html}}]}]}
        self.assertEqual(list(notebook_tables(notebook)), [[{"TP": "3", "FP": "2"}]])


@unittest.skipUnless(__import__("os").name == "nt", "Native Windows Spark verification")
class NativeAlgorithmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.common.spark_session import get_graph_session
        cls.spark = get_graph_session("Project-component-tests", driver_memory="4g",
            extra_configs={"spark.master": "local[2]", "spark.ui.enabled": "false", "spark.ui.showConsoleProgress": "false"})
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def graph(self, ibm=False):
        from graphframes import GraphFrame
        vertices = self.spark.sql("SELECT * FROM VALUES ('A','Customer',10.),('B','Merchant',20.),"
                                  "('C','Customer',30.),('D','Customer',40.) AS v(id,account_type,balance)")
        edges = self.spark.sql("SELECT * FROM VALUES ('A','B',100.,1,'TRANSFER',1),('A','B',20.,1,'TRANSFER',0),"
                              "('B','B',10.,2,'CASH_OUT',0),('C','A',30.,3,'PAYMENT',1) AS e(src,dst,amount,step,type,isFraud)")
        if ibm:
            from pyspark.sql import functions as F
            vertices = vertices.withColumn("bank_id", F.lit("1"))
            edges = edges.withColumn("payment_currency", F.when(F.col("amount") == 20, "Euro").otherwise("US Dollar"))
        return GraphFrame(vertices, edges)

    def assigned(self, graph):
        from pyspark.sql import functions as F
        return graph.vertices.withColumn("label", F.when(F.col("id").isin("A", "B"), 10).when(F.col("id") == "C", 20).otherwise(30))

    def test_task1_rejects_wrong_full_counts_invalid_labels_and_missing_raw(self):
        from graphframes import GraphFrame
        from pyspark.sql import functions as F
        from src.paysim.graph_analysis import verify_graph
        graph = self.graph()
        self.assertEqual(verify_graph(graph, sample=True)["num_edges"], 4)
        with self.assertRaisesRegex(ValueError, "cardinality"):
            verify_graph(graph)
        with self.assertRaisesRegex(ValueError, "Invalid"):
            verify_graph(GraphFrame(graph.vertices, graph.edges.withColumn("isFraud", F.lit(2))), sample=True)
        raw = self.spark.sql("SELECT 'X' nameOrig,'Y' nameDest,1 step,100. amount,'TRANSFER' type,0 isFraud")
        with self.assertRaisesRegex(ValueError, "absent from raw"):
            verify_graph(graph, sample=True, raw_df=raw)

    def test_task1_closes_spark_when_loading_fails(self):
        from unittest.mock import Mock, patch
        from src.paysim import graph_analysis
        session = Mock()
        with patch("sys.argv", ["graph_analysis", "--sample"]), patch.object(graph_analysis, "create_graph_spark_session", return_value=session), \
             patch("src.common.graph_utils.load_graph", side_effect=ValueError("bad source")):
            with self.assertRaisesRegex(ValueError, "bad source"):
                graph_analysis.main()
        session.stop.assert_called_once()

    def test_paysim_profiles_and_streamed_complete_export(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from pyspark.sql import DataFrame
        from src.paysim.community_detection import analyze_communities, export_results
        from src.common.project_audit import csv_rows
        graph = self.graph()
        labels = self.assigned(graph)
        _, summary = analyze_communities(labels, graph)
        root = next(row for row in summary.collect() if row.label == 10)
        self.assertEqual((root.member_count, root.customer_count, root.merchant_count), (2, 1, 1))
        self.assertEqual((root.total_tx_count, root.internal_tx_count, root.fraud_tx_count), (3, 3, 1))
        with tempfile.TemporaryDirectory() as directory, patch.object(DataFrame, "toPandas", side_effect=AssertionError("Unbounded collect")):
            export_results(labels, summary, Path(directory))
            self.assertEqual(len(csv_rows(Path(directory) / "communities.csv")), 4)
            self.assertEqual(len(csv_rows(Path(directory) / "community_summary_all.csv")), 3)

    def test_ibm_streaming_export_separates_currencies(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from pyspark.sql import DataFrame
        from src.ibm_aml.community_detection import analyze_communities, export_results
        from src.common.project_audit import csv_rows
        graph = self.graph(ibm=True)
        labels = self.assigned(graph)
        _, summary = analyze_communities(labels, graph)
        with tempfile.TemporaryDirectory() as directory, patch.object(DataFrame, "toPandas", side_effect=AssertionError("Unbounded collect")):
            export_results(labels, summary, Path(directory), graph)
            amounts = csv_rows(Path(directory) / "community_amounts_by_currency.csv")
            self.assertEqual(sum(float(row["total_tx_amount"]) for row in amounts if row["payment_currency"] == "Euro"), 20)
            self.assertNotIn("total_tx_amount", csv_rows(Path(directory) / "community_summary.csv")[0])

    def test_actual_pagerank_matches_independent_reference(self):
        from src.paysim.metrics import calculate_pagerank
        graph = self.graph()
        edges = [row.asDict() for row in graph.edges.collect()]
        expected = reference_pagerank({row.id: None for row in graph.vertices.collect()}, edges, Counter(e["src"] for e in edges))
        actual = calculate_pagerank(graph)
        try:
            for row in actual.select("id", "pagerank").collect():
                self.assertAlmostEqual(row.pagerank, expected[row.id], places=8)
        finally:
            actual.unpersist()

    def test_membership_comparison_detects_equal_size_different_groups(self):
        from src.ibm_aml.verify_communities import compare_partition_frames
        first = self.spark.sql("SELECT * FROM VALUES ('A',1),('B',1),('C',2),('D',2) AS t(id,label)")
        renamed = self.spark.sql("SELECT * FROM VALUES ('A',9),('B',9),('C',8),('D',8) AS t(id,label)")
        changed = self.spark.sql("SELECT * FROM VALUES ('A',1),('C',1),('B',2),('D',2) AS t(id,label)")
        self.assertTrue(compare_partition_frames(first, renamed)["same_partition"])
        self.assertFalse(compare_partition_frames(first, changed)["same_partition"])

    def test_snapshots_ignore_future_edges_and_reject_same_time_decisions(self):
        import tempfile
        from pathlib import Path
        from pyspark.sql import functions as F
        from src.paysim.metrics import snapshot_features as ranks
        from src.paysim.community_detection import snapshot_features as communities
        from src.common.project_audit import component_edge_features
        past = self.spark.sql("SELECT * FROM VALUES ('A','A',1),('B','B',2) AS e(src,dst,step)")
        future = self.spark.sql("SELECT 'C' src,'A' dst,100 step")
        with tempfile.TemporaryDirectory() as directory:
            for branch in ("centrality", "community"):
                make = (lambda frame, name: ranks(frame, 2)) if branch == "centrality" else \
                       (lambda frame, name: communities(frame, 2, self.spark, Path(directory) / name))
                first, extended = make(past, "one"), make(past.unionByName(future), "two")
                try:
                    columns = sorted(first.columns)
                    self.assertEqual(first.select(columns).exceptAll(extended.select(columns)).count(), 0)
                    self.assertEqual(extended.select(columns).exceptAll(first.select(columns)).count(), 0)
                    with self.assertRaisesRegex(ValueError, "precede every"):
                        component_edge_features(past, first, branch)
                    with self.assertRaisesRegex(ValueError, "Ground truth"):
                        component_edge_features(future.withColumn("isFraud", F.lit(1)), first, branch)
                    mapped = component_edge_features(future, first, branch).first()
                    self.assertEqual(mapped.novelty_score, 1)
                finally:
                    first.unpersist(); extended.unpersist()

    def test_component_protocol_exports_verifiable_frozen_results(self):
        import tempfile
        from pathlib import Path
        from graphframes import GraphFrame
        from src.common.graph_utils import save_graph
        from src.common.project_audit import evaluate_component_signals, verify_component_report
        edges = self.spark.sql("SELECT concat('A',cast(id%10 as string)) src,"
            "concat('A',cast((id+1)%10 as string)) dst,cast(id*3600 as bigint) step,"
            "cast(100+id as double) amount,'ACH' type,'USD' payment_currency,'USD' receiving_currency,"
            "cast(CASE WHEN id%10=0 THEN 1 ELSE 0 END as smallint) isFraud FROM range(200)")
        vertices = self.spark.sql("SELECT concat('A',cast(id as string)) id FROM range(10)")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            save_graph(GraphFrame(vertices, edges), str(root / "input"))
            report = evaluate_component_signals(self.spark, "ibm_aml", "centrality", root / "input", root / "output")
            checked = verify_component_report(root / "output", "ibm_aml", "centrality")
            self.assertEqual(checked["transactions"], report["selected_test_metrics"]["transactions"])
            self.assertEqual(checked["TP"] + checked["FN"], checked["fraud"])
            self.assertTrue((root / "output/account_snapshot.csv").is_file())


    def test_component_alerts_join_truth_only_for_confusion_counts(self):
        from src.common.project_audit import score_component_rules
        features = self.spark.sql("SELECT * FROM VALUES (1,0.),(2,5.),(3,10.) AS f(event_id,degree_score)")
        truth = self.spark.sql("SELECT * FROM VALUES (1,1),(2,0),(3,1) AS t(event_id,isFraud)")
        rules = [{"family": "degree_high", "threshold": .9, "cut_value": 5., "score": "degree_score", "direction": "high"}]
        row = score_component_rules(features, truth, rules)[0]
        self.assertEqual((row["TP"], row["FP"], row["FN"], row["TN"]), (1, 1, 1, 0))


class FullSystemPolicyTests(unittest.TestCase):
    def test_family_matrix_has_all_eight_distinct_combinations(self):
        from src.motif.config import SYSTEM_FAMILY_GROUPS, FullSystemConfig
        self.assertEqual(len({frozenset(x) for name,x in SYSTEM_FAMILY_GROUPS.items() if name != "transaction_novelty"}), 8)
        self.assertEqual(FullSystemConfig().analysis.driver_memory, "5g")
        with self.assertRaises(ValueError):
            FullSystemConfig(snapshot_fractions=(.4, .8))


class NativeFullSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        if os.name != "nt":
            raise unittest.SkipTest("Native Windows verification required")
        from src.common.spark_session import get_graph_session
        cls.spark = get_graph_session("Full-system-native-tests", driver_memory="4g", shuffle_partitions=32,
            extra_configs={"spark.master": "local[2]", "spark.ui.enabled": "false", "spark.ui.showConsoleProgress": "false"})
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_a_dataframe_pagerank_matches_independent_and_graphx(self):
        import tempfile
        from pathlib import Path
        from graphframes import GraphFrame
        from src.paysim.metrics import dataframe_pagerank, calculate_pagerank
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'),('B'),('C'),('D') AS v(id)")
        edges = self.spark.sql("SELECT * FROM VALUES ('A','B'),('A','B'),('B','B'),('C','A') AS e(src,dst)")
        source = [r.asDict() for r in edges.collect()]
        expected = reference_pagerank({r.id:{} for r in vertices.collect()}, source, Counter(r['src'] for r in source))
        with tempfile.TemporaryDirectory() as temporary:
            actual = {r.id:r.pagerank for r in dataframe_pagerank(vertices, edges, Path(temporary)/'pr').collect()}
            gx = calculate_pagerank(GraphFrame(vertices, edges))
            try:
                graphx = {r.id:r.pagerank for r in gx.collect()}
            finally:
                gx.unpersist(blocking=True)
        for key in expected:
            self.assertAlmostEqual(expected[key], actual[key], places=10)
            self.assertAlmostEqual(graphx[key], actual[key], places=10)

    def test_b_dataframe_lpa_matches_modal_oracle_and_keeps_isolate(self):
        import tempfile
        from pathlib import Path
        from src.paysim.community_detection import dataframe_lpa
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'),('B'),('C'),('D') AS v(id)").coalesce(1).sortWithinPartitions('id')
        edges = self.spark.sql("SELECT * FROM VALUES ('A','B'),('A','B'),('B','B'),('C','A') AS e(src,dst)")
        from pyspark.sql import functions as F
        labels = {r.id:r.label for r in vertices.withColumn('label',F.xxhash64('id')).collect()}
        initial_d = labels['D']
        pairs = [(r.src,r.dst) for r in edges.collect()]
        for _ in range(5):
            votes = {key:Counter() for key in labels}
            for a,b in pairs:
                votes[a][labels[b]] += 1
                votes[b][labels[a]] += 1
            labels = {key:min(votes[key], key=lambda value:(-votes[key][value],value)) if votes[key] else labels[key] for key in labels}
        with tempfile.TemporaryDirectory() as temporary:
            result = {r.id:r.label for r in dataframe_lpa(vertices, edges, Path(temporary)/'lpa').collect()}
        self.assertEqual(result, labels)
        self.assertEqual(result['D'], initial_d)

    def test_c_common_join_rejects_future_and_preserves_unseen(self):
        from pyspark.sql import functions as F
        from src.motif.pipeline import join_system_snapshot
        tx = self.spark.sql("SELECT * FROM VALUES (1L,'A','NEW',11L) AS t(event_id,src,dst,step)")
        snapshot = self.spark.sql("SELECT 'A' AS id, 7L AS community_key, 10L AS as_of_step, 1L AS inDegree, 2L AS outDegree, 3L AS degree, 1.2 AS pagerank, 2L AS community_size, 0.5 AS community_cross_fraction, 4L AS community_out_transactions")
        row = join_system_snapshot(tx, snapshot).first()
        self.assertEqual((row.src_seen,row.dst_seen,row.same_community,row.snapshot_as_of),(1,0,0,10))
        with self.assertRaises(ValueError):
            join_system_snapshot(tx.withColumn('step',F.lit(10)), snapshot)
        with self.assertRaises(ValueError):
            join_system_snapshot(tx.withColumn('isFraud',F.lit(1)), snapshot)

    def test_d_full_system_fixture_exports_all_ablations_and_replays(self):
        import tempfile
        import json
        from pathlib import Path
        from pyspark.sql import functions as F
        from src.motif.config import AnalysisConfig, FullSystemConfig
        from src.motif.pipeline import (start_full_system,full_system_centrality,full_system_communities,
            full_system_motif_features,full_system_feature_table,full_system_validation,full_system_test,finalize_full_system,
            full_system_motif_benchmark,full_system_reliability)
        from src.common.project_audit import verify_full_system_artifacts
        from src.common.run_evidence import REPO_ROOT
        # A repository path exercises spaces/Vietnamese with actual native Hadoop/ML IO.
        parent = REPO_ROOT / 'results' / 'full_system' / 'fixtures'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent, prefix='native-', ignore_cleanup_errors=True) as temporary:
            root = Path(temporary)
            rows=[]
            for i in range(240):
                a,b=i%12,(i+1)%12
                rows.append((f'C{a}',f'C{b}',float(10+i%13),i//4+1,'TRANSFER' if i%2 else 'CASH_OUT',int(i%7==0)))
            values=','.join(f"('{a}','{b}',{amount}D,{step}L,'{kind}',{label})" for a,b,amount,step,kind,label in rows)
            edges=self.spark.sql('SELECT * FROM VALUES '+values+' AS e(src,dst,amount,step,type,isFraud)')
            vertex_values=','.join(f"('C{i}','Customer',0.0D)" for i in range(12))
            vertices=self.spark.sql('SELECT * FROM VALUES '+vertex_values+' AS v(id,account_type,balance)')
            edges.write.parquet(str(root/'input/edges.parquet'))
            vertices.write.parquet(str(root/'input/vertices.parquet'))
            config=FullSystemConfig(analysis=AnalysisConfig(driver_memory='4g',tree_depth=3,minimum_leaf_rows=2))
            # Execute the exact visible notebook definitions, not a second demo implementation.
            import ast
            import __future__
            from functools import partial
            notebook=json.loads((REPO_ROOT/'notebooks/PaySIM_full_system.ipynb').read_text(encoding='utf-8'))
            namespace,visible={},{}
            copied={item['name'] for item in notebook['metadata']['graphguard_source_copies']}
            for cell in notebook['cells']:
                if cell['cell_type']!='code' or not any(item['cell_id']==cell['id'] for item in notebook['metadata']['graphguard_source_copies']):
                    continue
                nodes=[node for node in ast.parse(''.join(cell['source'])).body if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef))]
                exec(compile(ast.Module(body=nodes,type_ignores=[]),'<visible-notebook-kernel>','exec',
                             flags=__future__.annotations.compiler_flag),namespace)
                visible.update({node.name:namespace[node.name] for node in nodes if isinstance(node,(ast.FunctionDef,ast.ClassDef))})
            namespace.update(visible)
            namespace['pd']=__import__('pandas')
            kernels={name:fn for name,fn in visible.items() if name in copied}
            kernels['build_motif_features']=partial(visible['build_motif_features'],
                cycle_builder=visible['build_temporal_cycle_features'],topology_builder=visible['find_topological_cycles'])
            run=start_full_system(self.spark,'paysim',root/'output',config,input_dir=root/'input',fixture=True,kernels=kernels)
            full_system_centrality(run)
            full_system_communities(run)
            full_system_motif_features(run)
            full_system_feature_table(run)
            features=run.table('features')
            self.assertEqual(features.count(),240)
            self.assertEqual(features.where(F.col('snapshot_as_of')>=F.col('step')).count(),0)
            full_system_validation(run)
            metrics=full_system_test(run)
            self.assertEqual(len(metrics),9)
            self.assertEqual(metrics.transactions.nunique(),1)
            coverage=full_system_motif_benchmark(run)
            self.assertEqual(set(coverage.scope),{'full','test'})
            stability=full_system_reliability(run)
            self.assertEqual(len(stability),9)
            # Same-source resume verifies file hashes before reusing full phases.
            resumed=start_full_system(self.spark,'paysim',config=config,input_dir=root/'input',
                fixture=True,resume_from=root/'output')
            self.assertEqual(full_system_feature_table(resumed)['rows'],240)
            finalized=finalize_full_system(run)
            self.assertIn('PASS',set(finalized.result.astype(str)))
            with self.assertRaises(ValueError):
                verify_full_system_artifacts(root/'output',require_full=True)
            report=root/'output/report.json'
            data=json.loads(report.read_text(encoding='utf-8'))
            data['test_metrics'][0]['TP']+=1
            report.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_full_system_artifacts(root/'output',require_full=False)


class FullDegreeComparisonTests(unittest.TestCase):
    def test_full_distribution_keeps_isolates_and_parallel_transaction_degree(self):
        import pandas as pd
        from src.comparison.degree_distribution import validate_full_distribution
        table=pd.DataFrame({'degree':[0,1,3],'account_count':[1,1,1]})
        valid=validate_full_distribution(table,3,2)
        self.assertAlmostEqual(valid.proportion.sum(),1.0)
        with self.assertRaises(ValueError):
            validate_full_distribution(table[table.degree>0],3,2)
        with self.assertRaises(ValueError):
            validate_full_distribution(table.assign(degree=[0,1,2]),3,2)

    def test_fractional_or_duplicate_degree_bins_are_rejected(self):
        import pandas as pd
        from src.comparison.degree_distribution import validate_full_distribution
        for table,vertices,edges in ((pd.DataFrame({'degree':[.5,3.5],'account_count':[1,1]}),2,2),
                                     (pd.DataFrame({'degree':[1,1],'account_count':[2,2]}),4,2)):
            with self.assertRaises(ValueError):
                validate_full_distribution(table,vertices,edges)

    def test_foreign_latest_directory_cannot_be_used_as_full_comparison(self):
        import tempfile,json
        from pathlib import Path
        from src.comparison.degree_distribution import load_full_distributions
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);base=root/'results/full_system/paysim';base.mkdir(parents=True)
            (base/'latest.json').write_text(json.dumps({'status':'completed','directory':str(root/'sample')}),encoding='utf-8')
            with self.assertRaises(ValueError):
                load_full_distributions(root)


if __name__ == "__main__":
    unittest.main()
