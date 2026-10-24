"""Independent checks of causal features, model selection and reusable artifacts."""

from pathlib import Path
import tempfile
import unittest

import pandas as pd
from graphframes import GraphFrame
from pyspark.sql import functions as F

from src.common.graph_utils import save_graph
from src.common.spark_session import get_graph_session
from src.motif.config import AnalysisConfig, DATASETS
from src.motif.evaluation import binary_metrics, require_unlabelled
from src.motif.features import build_motif_features, motif_numeric_columns, normalize_edges, resolve_star_witness
from src.motif.modeling import (
    choose_walk_forward_rule, metrics_at_threshold, precision_recall_curve,
    score_transactions, wilson_interval,
)
from src.motif.pipeline import (
    evaluate_final_models, export_experiment, fit_final_models, load_exported_model,
    prepare_experiment, run_walk_forward,
)


class ProtocolTests(unittest.TestCase):
    def test_reject_invalid_protocol(self):
        for kwargs in ({"windows_hours": (0, 24)}, {"windows_hours": (24, 24)},
                       {"fold_fractions": (0.6, 0.5, 0.8)}, {"score_thresholds": (float("nan"),)},
                       {"score_thresholds": (1.1,)}, {"tree_depth": 99}, {"parallelism": 0}, {"parallelism": 65}):
            with self.assertRaises(ValueError):
                AnalysisConfig(**kwargs)

    def test_tied_scores_exact_ap_and_undefined_ci(self):
        histogram = pd.DataFrame([
            {"risk_score": 0.9, "isFraud": 1, "count": 1},
            {"risk_score": 0.9, "isFraud": 0, "count": 1},
            {"risk_score": 0.1, "isFraud": 1, "count": 1},
            {"risk_score": 0.1, "isFraud": 0, "count": 7},
        ])
        metrics = metrics_at_threshold(histogram, 0.5)
        self.assertEqual((metrics["TP"], metrics["FP"], metrics["FN"], metrics["TN"]), (1, 1, 1, 7))
        _, ap = precision_recall_curve(histogram)
        self.assertAlmostEqual(ap, 0.35)
        self.assertEqual(wilson_interval(0, 0), (None, None))
        lo, hi = wilson_interval(10, 10)
        self.assertGreater(lo, 0.7)
        self.assertLessEqual(hi, 1.0)

    def test_walk_forward_prefers_simple_ties_and_rejects_missing_fold(self):
        records = [{"fold": fold, "family": family, "threshold": 0.5,
                    **binary_metrics(100, 10, 5, 5)}
                   for fold in (1, 2, 3) for family in ("transaction_only", "motif_assisted")]
        scores = pd.DataFrame(records)
        chosen, _ = choose_walk_forward_rule(scores)
        self.assertEqual(chosen["family"], "transaction_only")
        with self.assertRaises(ValueError):
            choose_walk_forward_rule(scores.iloc[:-1])


class NativePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = get_graph_session("GraphGuard-v2-tests", driver_memory="4g", shuffle_partitions=2,
            extra_configs={"spark.master": "local[2]", "spark.ui.enabled": "false", "spark.ui.showConsoleProgress": "false"})
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def feature_fixture(self):
        frame = self.spark.sql("SELECT * FROM VALUES "
            "(1,'A','B',1,100.,'ACH','USD','USD'),(2,'C','B',2,100.,'ACH','USD','USD'),"
            "(3,'B','C',3,100.,'ACH','USD','USD'),(4,'B','A',4,100.,'ACH','USD','USD'),"
            "(5,'C','A',5,100.,'ACH','USD','USD'),(6,'D','A',5,100.,'ACH','USD','USD'),"
            "(7,'A','A',6,100.,'ACH','USD','USD'),(8,'A','B',6,100.,'ACH','USD','EUR'),"
            "(9,'B','A',6,0.,'ACH','USD','USD') "
            "AS e(event_id,src,dst,step,amount,type,payment_currency,receiving_currency)")
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'),('B'),('C'),('D') AS v(id)")
        return frame, vertices

    def test_feature_prefix_invariance_and_actual_witness_paths(self):
        frame, vertices = self.feature_fixture()
        full = build_motif_features(frame, vertices, DATASETS["ibm_aml"], (24,))
        prefix = build_motif_features(frame.where("step<=5"), vertices, DATASETS["ibm_aml"], (24,))
        try:
            columns = sorted(full.columns)
            self.assertEqual(full.where("step<=5").select(columns).exceptAll(prefix.select(columns)).count(), 0)
            self.assertEqual(prefix.select(columns).exceptAll(full.where("step<=5").select(columns)).count(), 0)
            rows = {r.event_id: r for r in full.collect()}
            self.assertEqual(rows[2].fanin_24h, 1)
            self.assertEqual(rows[3].relay_24h, 1)  # C->B->C is a reciprocal, not a three-account relay.
            self.assertEqual(rows[3].reciprocal_witness_24h, 2)
            self.assertEqual(rows[4].fanout_24h, 1)
            self.assertEqual(rows[5].cycle3_count, 1)
            # Same-time row 5 cannot be the fan-in witness of row 6.
            witnesses = resolve_star_witness(frame, 6, DATASETS["ibm_aml"], "fanin", 24).collect()
            self.assertTrue(witnesses)
            self.assertTrue(all(w.step < rows[6].step for w in witnesses))
            for event_id in (7, 8, 9):
                self.assertEqual(rows[event_id].cycle3_count, 0)
                self.assertEqual(rows[event_id].reciprocal_24h, 0)
            # Independent self-join counts valid A->B->C paths, including time
            # ties and distinct accounts, rather than mirroring the window code.
            eligible = frame.where("src!=dst AND amount>0 AND payment_currency=receiving_currency")
            reference = eligible.alias("now").join(eligible.alias("old"),
                (F.col("old.dst") == F.col("now.src")) & (F.col("old.src") != F.col("now.dst"))
                & (F.col("old.payment_currency") == F.col("now.payment_currency"))
                & (F.col("old.step") < F.col("now.step"))
                & (F.col("now.step") - F.col("old.step") <= 24 * 3600)
            ).groupBy(F.col("now.event_id").alias("event_id")).count().collect()
            expected = {r.event_id: r["count"] for r in reference}
            for event_id, row in rows.items():
                self.assertEqual(row.relay_24h, expected.get(event_id, 0))
        finally:
            full.unpersist()
            prefix.unpersist()

    def test_nested_label_and_invalid_contract_rejected(self):
        with self.assertRaises(ValueError):
            require_unlabelled(self.spark.sql("SELECT struct(1 AS isFraud) AS edge"))
        frame, _ = self.feature_fixture()
        labelled = frame.withColumn("isFraud", F.lit(0))
        for invalid in (labelled.withColumn("step", F.lit(1.5)), labelled.withColumn("isFraud", F.lit(2)),
                        labelled.withColumn("amount", F.lit(float("nan"))), labelled.withColumn("src", F.lit(""))):
            with self.assertRaises(ValueError):
                normalize_edges(invalid, DATASETS["ibm_aml"])

    def test_one_timestamp_histories_preserve_duplicate_rows_with_zero_counts(self):
        frame = self.spark.sql("SELECT * FROM VALUES "
            "(1,'A','B',1,100.,'ACH','USD','USD'),"
            "(2,'A','B',1,100.,'ACH','USD','USD'),"
            "(3,'C','B',1,100.,'ACH','USD','USD') "
            "AS e(event_id,src,dst,step,amount,type,payment_currency,receiving_currency)")
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'),('B'),('C') AS v(id)")
        features = build_motif_features(frame, vertices, DATASETS["ibm_aml"], (24,))
        try:
            rows = features.collect()
            self.assertEqual({row.event_id for row in rows}, {1, 2, 3})
            for row in rows:
                for name in motif_numeric_columns((24,)):
                    self.assertEqual(row[name], 0)
        finally:
            features.unpersist()

    def test_paysim_hour_boundary_typed_relay_and_reverse_partner(self):
        frame = self.spark.sql("SELECT * FROM VALUES "
            "(1,'A','B',1,100.,'TRANSFER','UNIT','UNIT'),"
            "(2,'C','B',24,100.,'TRANSFER','UNIT','UNIT'),"
            "(3,'B','C',25,100.,'CASH_OUT','UNIT','UNIT'),"
            "(4,'X','B',25,100.,'TRANSFER','UNIT','UNIT'),"
            "(5,'B','D',26,100.,'CASH_OUT','UNIT','UNIT') "
            "AS e(event_id,src,dst,step,amount,type,payment_currency,receiving_currency)")
        vertices = self.spark.sql("SELECT * FROM VALUES ('A'),('B'),('C'),('D'),('X') AS v(id)")
        result = build_motif_features(frame, vertices, DATASETS["paysim"], (24,))
        try:
            rows = {r.event_id: r for r in result.collect()}
            self.assertEqual(rows[3].relay_24h, 1)  # Exactly 24 hours; excludes reciprocal and same-hour edge.
            self.assertEqual({r.event_id for r in resolve_star_witness(
                frame, 3, DATASETS["paysim"], "relay", 24).collect()}, {1})
            self.assertEqual(rows[5].relay_24h, 2)  # A->B is now too old; C and X remain valid.
            self.assertEqual(rows[1].relay_24h, 0)  # TRANSFER cannot close the PaySim typed relay.
        finally:
            result.unpersist()

    def test_complete_protocol_model_reload_and_tamper_rejection(self):
        # A synthetic sanity fixture is intentionally separable. Its score is
        # NOT an estimate of IBM/PaySim performance.
        edges = self.spark.sql("SELECT concat('A',cast(id%10 as string)) src,"
            "concat('A',cast((id+1)%10 as string)) dst,cast(id*3600 as bigint) step,"
            "cast(CASE WHEN id%10=0 THEN 10000 ELSE 100+id%20 END as double) amount,"
            "'ACH' type,'USD' payment_currency,'USD' receiving_currency,"
            "cast(CASE WHEN id%10=0 THEN 1 ELSE 0 END as smallint) isFraud FROM range(1000)")
        vertices = self.spark.sql("SELECT concat('A',cast(id as string)) id FROM range(10)")
        with tempfile.TemporaryDirectory(prefix="graphguard-v2-test-", ignore_cleanup_errors=True) as temp:
            root = Path(temp)
            save_graph(GraphFrame(vertices, edges), str(root / "input"))
            config = AnalysisConfig(tree_depth=3, minimum_leaf_rows=2, parallelism=2)
            experiment = prepare_experiment(self.spark, "ibm_aml", root / "input", config)
            try:
                with self.assertRaises(ValueError):
                    evaluate_final_models(experiment)
                # Change only FUTURE labels before selection: the walk-forward
                # training/validation periods must be unchanged.
                original_truth = experiment.truth
                future_changed = original_truth.withColumn("isFraud", F.when(
                    F.col("step") > experiment.cutoffs[-1], 1 - F.col("isFraud")).otherwise(F.col("isFraud")))
                experiment.truth = future_changed
                run_walk_forward(experiment)
                self.assertEqual(experiment.selection["family"], "transaction_only")
                self.assertEqual(experiment.selection["mean_F1"], 1.0)
                experiment.truth = original_truth
                threshold = experiment.selection["threshold"]
                experiment.selection["threshold"] = 0.123
                with self.assertRaises(ValueError):
                    fit_final_models(experiment)
                experiment.selection["threshold"] = threshold
                fit_final_models(experiment)
                metrics = evaluate_final_models(experiment)
                self.assertTrue((metrics.transactions == 200).all())
                self.assertTrue((metrics.TP == 20).all())
                with self.assertRaises(ValueError):
                    run_walk_forward(experiment)
                export_experiment(experiment, root / "output")
                restored, rule = load_exported_model(self.spark, root / "output")
                expected = experiment.scores[rule["family"]].select("event_id", "risk_score")
                actual = score_transactions(restored, experiment.features.where(F.col("step") > experiment.cutoffs[-1]))
                mismatch = expected.alias("a").join(actual.alias("b"), "event_id").where(
                    F.abs(F.col("a.risk_score") - F.col("b.risk_score")) > 1e-12).count()
                self.assertEqual(mismatch, 0)
                path = root / "output/examples_TP.csv"
                path.write_bytes(path.read_bytes() + b"tampered\n")
                with self.assertRaises(ValueError):
                    load_exported_model(self.spark, root / "output")
            finally:
                experiment.close()


if __name__ == "__main__":
    unittest.main()
