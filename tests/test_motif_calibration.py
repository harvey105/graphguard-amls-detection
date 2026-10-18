"""Guard against label leakage, future witnesses and inflated motif metrics."""

import unittest

import pandas as pd
from pyspark.sql import functions as F

from src.common.spark_session import get_graph_session
from src.ibm_aml.motif_finding import (
    build_temporal_cycle_features, find_topological_cycles, score_cycle_validation,
)
from src.motif.evaluation import (
    binary_metrics, evaluate_alerts, index_transactions, require_unlabelled,
    select_validation_rule,
)
from src.paysim.motif_finding import build_fanin_features, fanin_alerts, score_fanin_validation


class MetricTests(unittest.TestCase):
    def test_confusion_denominators_and_undefined_metrics(self):
        result = binary_metrics(100, 10, 3, 2)
        self.assertEqual((result["TP"], result["FP"], result["FN"], result["TN"]), (3, 2, 7, 88))
        self.assertAlmostEqual(result["F1"], 0.4)
        self.assertIsNone(binary_metrics(10, 0, 0, 0)["recall"])
        self.assertIsNone(binary_metrics(10, 1, 0, 0)["precision"])
        for args in ((1, 2, 0, 0), (10, 2, 3, 0), (10, 2, 1, 9), (10, 2, -1, 0)):
            with self.assertRaises(ValueError):
                binary_metrics(*args)

    def test_optimizer_abstains_or_uses_validation_f1(self):
        scores = pd.DataFrame([
            {"rule_id": "a", **binary_metrics(100, 10, 5, 5)},
            {"rule_id": "b", **binary_metrics(100, 10, 4, 0)},
        ])
        self.assertEqual(select_validation_rule(scores)["rule_id"], "b")
        self.assertEqual(select_validation_rule(pd.DataFrame([
            {"rule_id": "a", **binary_metrics(10, 2, 0, 2)}
        ]))["rule_id"], "abstain")


class CausalMotifTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = get_graph_session("Motif-calibration-tests", driver_memory="4g", shuffle_partitions=2,
            extra_configs={"spark.master": "local[2]", "spark.ui.enabled": "false",
                           "spark.ui.showConsoleProgress": "false"})
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_fanin_equals_explicit_motif_and_excludes_future_and_same_hour(self):
        features = self.spark.sql("SELECT * FROM VALUES "
            "(1,'A','Z',1,100.0,'CASH_OUT'),(2,'A','Z',2,120.0,'CASH_OUT'),"
            "(3,'A','Z',3,100.0,'CASH_OUT'),(4,'A','Z',4,130.0,'CASH_OUT'),"
            "(5,'B','Z',4,130.0,'CASH_OUT'),(6,'C','Z',6,140.0,'CASH_OUT') "
            "AS e(event_id,src,dst,step,amount,type)")
        fan = build_fanin_features(features, (2,))
        actual = {r.event_id for r in fan.where("witness_2 IS NOT NULL").select("event_id").collect()}
        expected = {r.event_id for r in features.alias("now").join(features.alias("old"),
            (F.col("now.dst") == F.col("old.dst")) & (F.col("now.src") != F.col("old.src"))
            & (F.col("old.step") < F.col("now.step"))
            & (F.col("old.step") >= F.col("now.step") - 2)
        ).select("now.event_id").distinct().collect()}
        self.assertEqual(actual, expected)
        self.assertEqual(actual, {5, 6})
        prefix = build_fanin_features(features.where("step<=4"), (2,))
        self.assertEqual(prefix.where("witness_2 IS NOT NULL").count(), 1)
        with self.assertRaises(ValueError):
            build_fanin_features(features.withColumn("isFraud", F.lit(1)))

    def cycle_fixture(self):
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'),('B'),('C') AS v(id)")
        features = self.spark.sql("SELECT * FROM VALUES "
            "(1,'C','A',1,100.0,'X','X'),(2,'C','A',1,100.0,'X','X'),"
            "(3,'A','B',2,99.0,'X','X'),(4,'B','C',3,98.0,'X','X'),"
            "(5,'B','C',3,100.0,'Y','Y'),(6,'B','C',2,98.0,'X','X'),"
            "(7,'B','C',4,100.0,'X','Y') "
            "AS e(event_id,src,dst,step,amount,payment_currency,receiving_currency)")
        topology = find_topological_cycles(vertices, features)
        return vertices, features, topology

    def test_cycle_rotates_to_earliest_edge_and_retains_real_duplicate_rows(self):
        vertices, features, topology = self.cycle_fixture()
        self.assertEqual(topology.count(), 1)
        result = build_temporal_cycle_features(topology, features).cache()
        self.assertEqual(result.count(), 2)
        self.assertEqual({r.event_id for r in result.select("event_id").collect()}, {4})
        self.assertEqual({(r.a, r.b, r.c) for r in result.select("a", "b", "c").collect()}, {("C", "A", "B")})
        prefix_features = features.where("step<=3")
        prefix = build_temporal_cycle_features(find_topological_cycles(vertices, prefix_features), prefix_features)
        self.assertEqual(prefix.count(), result.count())
        with self.assertRaises(ValueError):
            require_unlabelled(features.withColumn("isLaundering", F.lit(1)))
        result.unpersist()

    def test_test_labels_cannot_select_cycle_rule_and_tp_is_deduplicated(self):
        _, features, topology = self.cycle_fixture()
        evidence = build_temporal_cycle_features(topology, features).withColumn(
            "split", F.lit("validation")).withColumn("q50_amount", F.lit(50.0)).withColumn("q90_amount", F.lit(80.0))
        truth = self.spark.sql("SELECT * FROM VALUES "
            "(4,'validation',1),(8,'validation',0),(9,'test',0) AS t(event_id,split,isFraud)")
        first = score_cycle_validation(evidence, truth)
        changed = truth.withColumn("isFraud", F.when(F.col("split") == "test", 1).otherwise(F.col("isFraud")))
        pd.testing.assert_frame_equal(first, score_cycle_validation(evidence, changed))
        self.assertEqual(int(first.TP.max()), 1)
        metrics = evaluate_alerts(evidence, truth).set_index("split")
        self.assertEqual(int(metrics.loc["validation", "TP"]), 1)
        self.assertEqual(int(metrics.loc["validation", "transactions"]), 2)

    def test_identical_records_get_different_run_local_ids(self):
        rows = self.spark.sql("SELECT * FROM VALUES ('A','B',1),('A','B',1) AS e(src,dst,step)")
        indexed = index_transactions(rows)
        self.assertEqual(indexed.count(), indexed.select("event_id").distinct().count())
        self.assertEqual(indexed.count(), 2)
        indexed.unpersist()

    def test_fanin_grid_matches_prediction_and_never_scores_test_labels(self):
        features = self.spark.sql("SELECT * FROM VALUES "
            "(1,'A','Z',1,100.0,'CASH_OUT','train'),"
            "(2,'B','Z',2,200.0,'CASH_OUT','validation'),"
            "(3,'C','Y',3,300.0,'CASH_OUT','validation'),"
            "(4,'D','Z',4,400.0,'CASH_OUT','test') "
            "AS e(event_id,src,dst,step,amount,type,split)")
        truth = self.spark.sql("SELECT * FROM VALUES "
            "(1,'train',0),(2,'validation',1),(3,'validation',0),(4,'test',0) "
            "AS t(event_id,split,isFraud)")
        fan = build_fanin_features(features, (2,))
        thresholds = [{"quantile": 0.0, "minimum_amount": 0.0},
                      {"quantile": 0.9, "minimum_amount": 250.0}]
        scores = score_fanin_validation(fan, truth, thresholds, windows=(2,), minimum_priors=(1, 2))
        changed = truth.withColumn("isFraud", F.when(F.col("split") == "test", 1).otherwise(F.col("isFraud")))
        pd.testing.assert_frame_equal(scores, score_fanin_validation(
            fan, changed, thresholds, windows=(2,), minimum_priors=(1, 2)))
        rule = select_validation_rule(scores.query("family=='fanin'"))
        actual = evaluate_alerts(fanin_alerts(fan, rule), truth).set_index("split")
        self.assertEqual((actual.loc["validation", "TP"], actual.loc["validation", "FP"]), (rule["TP"], rule["FP"]))


if __name__ == "__main__":
    unittest.main()
