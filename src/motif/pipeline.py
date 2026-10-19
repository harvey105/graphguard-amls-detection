r"""Run the same causal motif experiment from Python, notebooks or PowerShell.

Windows PowerShell:
    & .\.venv\Scripts\python.exe -m src.motif.pipeline --dataset ibm_aml --output-dir results\motif\v2\ibm_aml

Notebook calls do not write artifacts. CLI export is explicit and refuses a
nonempty output directory so an earlier experiment is not silently overwritten.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import pandas as pd
from graphframes import GraphFrame
from pyspark.sql import DataFrame, functions as F

from src.common.graph_utils import check_integrity, load_graph
from src.common.run_evidence import REPO_ROOT, file_fingerprint, write_run_evidence
from src.motif.config import AnalysisConfig, DATASETS, DatasetSpec
from src.motif.evaluation import index_transactions
from src.motif.features import build_motif_features, normalize_edges
from src.motif.modeling import (
    FAMILIES, choose_walk_forward_rule, fit_risk_model, metrics_at_threshold,
    precision_recall_curve, score_histogram, score_transactions, wilson_interval,
)


@dataclass
class Experiment:
    spec: DatasetSpec
    config: AnalysisConfig
    input_dir: Path
    features: DataFrame
    truth: DataFrame
    cutoffs: tuple[int, ...]
    support: pd.DataFrame
    integrity: dict
    state: str = "prepared"
    folds: pd.DataFrame = field(default_factory=pd.DataFrame)
    leaderboard: pd.DataFrame = field(default_factory=pd.DataFrame)
    selection: dict = field(default_factory=dict)
    family_rules: dict = field(default_factory=dict)
    models: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    curves: dict = field(default_factory=dict)
    timings: dict = field(default_factory=dict)
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rule_digest: str = ""

    def close(self):
        """Release this experiment's caches; the caller still owns SparkSession."""
        for frame in [self.features, self.truth, *self.scores.values()]:
            frame.unpersist()
        for model in self.models.values():
            model.scales.unpersist()

    def report(self) -> dict:
        if self.state != "evaluated":
            raise ValueError("Evaluate frozen models before creating a final report")
        return {
            "schema_version": "graphguard.motif.v2", "dataset": self.spec.name,
            "created_utc": self.created_utc, "config": self.config.as_dict(),
            "cutoffs": self.cutoffs, "support": self.support.to_dict("records"),
            "integrity": self.integrity, "selection": self.selection,
            "family_rules": self.family_rules, "test_metrics": _records(self.metrics),
            "final_training": {name: model.training for name, model in self.models.items()},
            "timings_seconds": self.timings,
            "interpretation": "Supervised risk scoring of causal graph features; alert != proof of fraud",
            "test_status": "Reused internal temporal holdout; previously explored in this project; not an untouched external benchmark",
        }


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", double_precision=15))


def _expect_state(experiment: Experiment, expected: str):
    if experiment.state != expected:
        raise ValueError(f"Expected experiment state {expected!r}, found {experiment.state!r}")


def _rule_digest(experiment: Experiment) -> str:
    payload = {"selection": experiment.selection, "families": experiment.family_rules}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _check_frozen(experiment: Experiment):
    if _rule_digest(experiment) != experiment.rule_digest:
        raise ValueError("Selected configuration changed after validation; start a new declared experiment")


def prepare_experiment(spark, dataset: str, input_dir: Path | str | None = None,
                       config: AnalysisConfig | None = None) -> Experiment:
    """Validate inputs and extract features without using labels in motifs."""
    started = time.perf_counter()
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset: {dataset}")
    spec, config = DATASETS[dataset], config or AnalysisConfig()
    source = Path(input_dir or REPO_ROOT / spec.input_dir).resolve()
    graph = load_graph(spark, str(source))
    vertices = graph.vertices.select("id")
    integrity = check_integrity(GraphFrame(vertices, graph.edges), verbose=False)
    if (integrity["null_vertices"] or integrity["null_edges"] or integrity["dangling_edges"]
            or vertices.distinct().count() != integrity["num_vertices"]):
        raise ValueError("Invalid graph: null/duplicate vertex or dangling edge")
    normalized = normalize_edges(graph.edges, spec)
    indexed = index_transactions(normalized)
    truth = indexed.select("event_id", "step", "isFraud").localCheckpoint(eager=True)
    try:
        raw_features = indexed.drop("isFraud")
        cuts = tuple(int(x) for x in raw_features.approxQuantile("step", list(config.fold_fractions), 0.001))
        if len(set(cuts)) != len(config.fold_fractions):
            raise ValueError("Not enough distinct timestamps for walk-forward folds")
        phase = F.when(F.col("step") <= cuts[0], "initial_train")
        for i, cutoff in enumerate(cuts[1:], 1):
            phase = phase.when(F.col("step") <= cutoff, f"validation_{i}")
        support = truth.withColumn("phase", phase.otherwise("reused_test")).groupBy("phase").agg(
            F.count("*").alias("transactions"), F.sum("isFraud").alias("fraud"),
            F.min("step").alias("first_step"), F.max("step").alias("last_step"),
        ).orderBy("first_step").toPandas()
        if len(support) != len(cuts) + 1 or (support.transactions <= 0).any():
            raise ValueError("Empty temporal partition; cannot evaluate this protocol")
        validation_support = support[support.phase.str.startswith("validation_")]
        if (validation_support.fraud <= 0).any():
            raise ValueError("Insufficient positive support in a validation period; choose another protocol before evaluating test")
        features = build_motif_features(raw_features, vertices, spec, config.windows_hours)
        if features.count() != integrity["num_edges"]:
            features.unpersist()
            raise AssertionError("Feature extraction lost or duplicated transactions")
    except BaseException:
        truth.unpersist()
        raise
    finally:
        indexed.unpersist()
    result = Experiment(spec, config, source, features, truth, cuts, support, integrity)
    result.timings["prepare_features"] = round(time.perf_counter() - started, 3)
    return result


def run_walk_forward(experiment: Experiment) -> pd.DataFrame:
    """Three expanding-prefix fits per family; never inspect the final test labels."""
    _expect_state(experiment, "prepared")
    started, records = time.perf_counter(), []
    for fold, (start, end) in enumerate(zip(experiment.cutoffs[:-1], experiment.cutoffs[1:]), 1):
        for family in FAMILIES:
            print(f"Validation {fold}: {family}; training through {start}, validation through {end}", flush=True)
            model = fit_risk_model(experiment.features, experiment.truth, start, family, experiment.config)
            try:
                validation = experiment.features.where((F.col("step") > start) & (F.col("step") <= end))
                scores = score_transactions(model, validation)
                histogram = score_histogram(scores, experiment.truth, start, end)
                expected = int(experiment.support.loc[experiment.support.phase == f"validation_{fold}", "transactions"].iloc[0])
                if int(histogram["count"].sum()) != expected:
                    raise AssertionError("Validation score coverage mismatch")
                for threshold in experiment.config.score_thresholds:
                    records.append({"fold": fold, "family": family, "threshold": threshold,
                                    **metrics_at_threshold(histogram, threshold)})
            finally:
                model.scales.unpersist()
    experiment.folds = pd.DataFrame(records)
    selected, experiment.leaderboard = choose_walk_forward_rule(experiment.folds)
    experiment.selection = _records(pd.DataFrame([selected]))[0]
    for family in FAMILIES:
        ranked = experiment.leaderboard[experiment.leaderboard.family == family]
        experiment.family_rules[family] = _records(ranked.head(1))[0]
    experiment.rule_digest = _rule_digest(experiment)
    experiment.state = "selected"
    experiment.timings["walk_forward"] = round(time.perf_counter() - started, 3)
    return experiment.leaderboard


def fit_final_models(experiment: Experiment) -> dict:
    """Refit preprocessing and models through the final development cutoff only."""
    _expect_state(experiment, "selected")
    _check_frozen(experiment)
    started = time.perf_counter()
    test_start = experiment.cutoffs[-1]
    test_features = experiment.features.where(F.col("step") > test_start)
    for family in FAMILIES:
        print(f"Refit frozen {family}; test is not used in fitting", flush=True)
        model = fit_risk_model(experiment.features, experiment.truth, test_start, family, experiment.config)
        experiment.models[family] = model
        experiment.scores[family] = score_transactions(model, test_features).localCheckpoint(eager=True)
    experiment.state = "fitted"
    experiment.timings["final_fit"] = round(time.perf_counter() - started, 3)
    return {family: model.training for family, model in experiment.models.items()}


def evaluate_final_models(experiment: Experiment) -> pd.DataFrame:
    """Only this final stage reads test labels for performance measurement."""
    _expect_state(experiment, "fitted")
    _check_frozen(experiment)
    started, rows = time.perf_counter(), []
    for family in FAMILIES:
        histogram = score_histogram(experiment.scores[family], experiment.truth, experiment.cutoffs[-1], None)
        expected = int(experiment.support.loc[experiment.support.phase == "reused_test", "transactions"].iloc[0])
        if int(histogram["count"].sum()) != expected:
            raise AssertionError("Test scores lost or duplicated transactions")
        threshold = float(experiment.family_rules[family]["threshold"])
        metrics = metrics_at_threshold(histogram, threshold)
        curve, average_precision = precision_recall_curve(histogram)
        experiment.curves[family] = curve
        precision_low, precision_high = wilson_interval(metrics["TP"], metrics["alerts"])
        recall_low, recall_high = wilson_interval(metrics["TP"], metrics["fraud"])
        rows.append({"model": family, "threshold": threshold, **metrics, "average_precision": average_precision,
            "precision_low95": precision_low, "precision_high95": precision_high,
            "recall_low95": recall_low, "recall_high95": recall_high,
            "selected_on_validation": family == experiment.selection["family"]})
    experiment.metrics = pd.DataFrame(rows)
    experiment.state = "evaluated"
    experiment.timings["test_evaluation"] = round(time.perf_counter() - started, 3)
    return experiment.metrics


def selected_test_predictions(experiment: Experiment) -> DataFrame:
    if experiment.state != "evaluated":
        raise ValueError("Evaluate before inspecting labelled test examples")
    _check_frozen(experiment)
    family = experiment.selection["family"]
    scores = (experiment.scores[FAMILIES[0]].withColumn("risk_score", F.lit(0.0))
              if family == "abstain" else experiment.scores[family])
    threshold = float(experiment.selection["threshold"])
    return scores.withColumn("alert", (F.col("risk_score") >= threshold).cast("int")).join(
        experiment.truth.select("event_id", "isFraud"), "event_id"
    )


def example_transactions(experiment: Experiment, case: str) -> pd.DataFrame:
    if case not in {"TP", "FP", "FN", "TN"}:
        raise ValueError("case must be TP, FP, FN or TN")
    alert, label = {"TP": (1, 1), "FP": (1, 0), "FN": (0, 1), "TN": (0, 0)}[case]
    frame = selected_test_predictions(experiment).where((F.col("alert") == alert) & (F.col("isFraud") == label))
    long_window = max(experiment.config.windows_hours)
    return frame.orderBy(F.desc("risk_score"), "step", "event_key", "event_id").select(
        "event_id", "event_key", "src", "dst", "step", "type", "amount", "payment_currency",
        "risk_score", "isFraud", f"fanin_{long_window}h", f"fanout_{long_window}h",
        f"relay_{long_window}h", f"reciprocal_{long_window}h", "cycle3_count",
    ).limit(experiment.config.example_limit).toPandas()


def motif_coverage(experiment: Experiment) -> pd.DataFrame:
    """Count unique closing events per family; overlaps are not additive."""
    from functools import reduce
    predicates = {
        name: F.col("cycle3_count") > 0 if name == "cycle3" else reduce(
            lambda a, b: a | b, [F.col(f"{name}_{h}h") > 0 for h in experiment.config.windows_hours])
        for name in ("fanin", "fanout", "relay", "reciprocal", "cycle3")
    }
    # Ground truth is joined for audit only after feature extraction.
    frame = experiment.features.join(experiment.truth.select("event_id", "isFraud"), "event_id")
    counts = frame.agg(*[F.sum(F.when(predicate, 1).otherwise(0)).alias(name) for name, predicate in predicates.items()],
        *[F.sum(F.when(predicate & (F.col("isFraud") == 1), 1).otherwise(0)).alias(name + "_fraud")
          for name, predicate in predicates.items()]).first()
    return pd.DataFrame([{"motif": name, "closing_transactions": counts[name],
                          "fraud_closing_transactions": counts[name + "_fraud"]} for name in predicates])


def source_paths() -> list[Path]:
    return sorted((REPO_ROOT / "src/motif").glob("*.py")) + [REPO_ROOT / name for name in (
        "src/common/graph_utils.py", "src/common/spark_session.py", "src/common/windows_runtime.py",
        "src/common/run_evidence.py", "src/common/hardware_guard.py", "src/ibm_aml/motif_finding.py", "src/ibm_aml/visualize.py",
        "src/paysim/motif_finding.py")]


def export_experiment(experiment: Experiment, output_dir: Path, *, export_features: bool = False) -> dict:
    """Export a reusable fitted model, measured metrics, examples and fingerprints."""
    report = experiment.report()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Use a new/empty output directory for each experiment")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, frame in (("test_metrics.csv", experiment.metrics), ("walk_forward.csv", experiment.folds),
                        ("validation_leaderboard.csv", experiment.leaderboard)):
        path = output_dir / name
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        outputs.append(path)
    for case in ("TP", "FP", "FN"):
        path = output_dir / f"examples_{case}.csv"
        example_transactions(experiment, case).to_csv(path, index=False, encoding="utf-8-sig")
        outputs.append(path)
    family = experiment.selection["family"]
    if family != "abstain" and experiment.models[family].pipeline is not None:
        model = experiment.models[family]
        model.pipeline.write().save(str(output_dir / "model"))
        model.scales.write.parquet(str(output_dir / "amount_scales.parquet"))
        report["feature_names"] = model.feature_names
    if export_features:
        experiment.features.write.parquet(str(output_dir / "motif_features.parquet"))
    payload = output_dir / "report.json"
    payload.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    outputs.append(payload)
    # Fingerprint all model/optional Parquet members through a separate index.
    members = [{**file_fingerprint(path), "path": path.relative_to(output_dir).as_posix()}
               for path in sorted(output_dir.rglob("*")) if path.is_file()]
    index = output_dir / "artifact_index.json"
    index.write_text(json.dumps(members, indent=2) + "\n", encoding="utf-8")
    outputs.append(index)
    return write_run_evidence(output_dir / "run.json", experiment.features.sparkSession,
        task="Motif analysis v2 " + experiment.spec.name, inputs=[experiment.input_dir], outputs=outputs,
        sources=source_paths(), parameters=experiment.config.as_dict(), metrics=report)


def load_exported_model(spark, directory: Path):
    """Verify portable artifact hashes before loading the selected model.

    Training raw data need not be present for inference. The full run.json can
    additionally be checked with verify_run_evidence on the original workstation.
    """
    from pyspark.ml import PipelineModel
    from pyspark.ml.util import JavaMLReader
    from src.motif.modeling import RiskModel

    directory = Path(directory).resolve()
    run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    expected_index = next((item for item in run["outputs"] if Path(item["path"]).name == "artifact_index.json"), None)
    if run["status"] != "PASS" or expected_index is None:
        raise ValueError("Missing valid experiment manifest")
    if file_fingerprint(directory / "artifact_index.json")["sha256"] != expected_index["sha256"]:
        raise ValueError("Artifact index changed")
    for member in json.loads((directory / "artifact_index.json").read_text(encoding="utf-8")):
        path = (directory / member["path"]).resolve()
        if not path.is_relative_to(directory) or file_fingerprint(path)["sha256"] != member["sha256"]:
            raise ValueError("Exported artifact changed: " + member["path"])
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    if report["schema_version"] != "graphguard.motif.v2":
        raise ValueError("Unsupported experiment schema")
    family = report["selection"]["family"]
    if family == "abstain" or not (directory / "model").exists():
        raise ValueError("This experiment abstained; no fitted model to load")
    # All exported stages are JVM Spark ML stages. Spark 3.5.1's generic Python
    # PipelineModelReader first calls sc.textFile(...).first(), unnecessarily
    # starting a Python worker that crashes in this pinned native Windows stack.
    # Use the same JavaMLReader that generic reader would delegate to afterwards.
    fitted_pipeline = JavaMLReader(PipelineModel).session(spark).load(str(directory / "model"))
    model = RiskModel(family, fitted_pipeline,
        spark.read.parquet(str(directory / "amount_scales.parquet")), report["feature_names"], report["final_training"][family])
    return model, report["selection"]


def main(argv=None):
    from src.common.spark_session import get_graph_session
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--driver-memory", default="6g")
    parser.add_argument("--parallelism", type=int, default=2)
    parser.add_argument("--export-features", action="store_true")
    args = parser.parse_args(argv)
    # Resolve before Windows Spark maps/chdirs to the ASCII repository drive.
    args.output_dir = args.output_dir.resolve()
    if args.input_dir is not None:
        args.input_dir = args.input_dir.resolve()
    if args.sample and args.input_dir:
        parser.error("Choose --sample or --input-dir")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("--output-dir must be new or empty")
    source = REPO_ROOT / "data/processed/sample" / args.dataset if args.sample else args.input_dir
    config = AnalysisConfig(driver_memory=args.driver_memory, parallelism=args.parallelism)
    spark = get_graph_session("GraphGuard-Motif-v2-" + args.dataset, driver_memory=config.driver_memory,
        extra_configs={"spark.master": f"local[{config.parallelism}]", "spark.ui.showConsoleProgress": "false"})
    experiment = None
    try:
        experiment = prepare_experiment(spark, args.dataset, source, config)
        run_walk_forward(experiment)
        fit_final_models(experiment)
        print(evaluate_final_models(experiment).to_string(index=False))
        export_experiment(experiment, args.output_dir, export_features=args.export_features)
        print("[PASS] Executed and exported; inspect test_metrics.csv before claiming detection quality")
    finally:
        if experiment is not None:
            experiment.close()
        spark.stop()


if __name__ == "__main__":
    main()
