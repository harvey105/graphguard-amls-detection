r"""Run the same causal motif experiment from Python, notebooks or PowerShell.

Windows PowerShell:
    & .\.venv\Scripts\python.exe -m src.motif.pipeline --dataset ibm_aml --output-dir results\motif\v2\ibm_aml

Full-system notebooks and CLI export reproducible artifacts to a new run
directory. A nonempty output directory is refused to preserve earlier evidence.
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
            frame.unpersist(blocking=True)
        for model in self.models.values():
            model.scales.unpersist(blocking=True)

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
            features.unpersist(blocking=True)
            raise AssertionError("Feature extraction lost or duplicated transactions")
    except BaseException:
        truth.unpersist(blocking=True)
        raise
    finally:
        indexed.unpersist(blocking=True)
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
                model.scales.unpersist(blocking=True)
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
    import sys
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--full-system" in arguments:
        return full_system_main([item for item in arguments if item != "--full-system"])
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




# Full-system orchestration: all phases share one indexed population on disk.
@dataclass
class FullSystemRun:
    spark: object
    dataset: str
    input_dir: Path
    output_dir: Path
    config: object
    record: dict

    def table(self, name):
        return self.spark.read.parquet(str(self.output_dir / (name + ".parquet")))

    def save(self):
        import os
        path = self.output_dir / "system_state.json"
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(self.record, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)


def system_sources():
    return sorted(set(source_paths() + [REPO_ROOT / p for p in (
        "src/paysim/metrics.py", "src/paysim/community_detection.py", "src/ibm_aml/community_detection.py",
        "src/common/project_audit.py", "src/ibm_aml/verify_communities.py", "src/ibm_aml/etl.py",
        "src/paysim/etl_mapping.py", "tests/test_ibm_aml_etl.py", "scripts/run_n4_notebook.py")]))


def start_full_system(spark, dataset, output_dir=None, config=None, *, input_dir=None, fixture=False):
    """Freeze actual full input, source/config and a single physical-row index."""
    from pyspark import StorageLevel
    from src.motif.config import FullSystemConfig
    from src.common.run_evidence import input_fingerprint
    if dataset not in DATASETS:
        raise ValueError("Unknown dataset")
    config = config or FullSystemConfig()
    spark.conf.set("spark.sql.shuffle.partitions", str(config.partitions))
    source = Path(input_dir or REPO_ROOT / DATASETS[dataset].input_dir).resolve()
    expected_source = (REPO_ROOT / DATASETS[dataset].input_dir).resolve()
    if not fixture and source != expected_source:
        raise ValueError("Full runs require the canonical full input, never sample/custom input")
    output = Path(output_dir or REPO_ROOT / "results/full_system" / dataset / ("run_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))).resolve()
    if not fixture and not output.is_relative_to((REPO_ROOT / "results/full_system" / dataset).resolve()):
        raise ValueError("Full output must be inside results/full_system/<dataset>/")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Use a new/empty full-system output directory")
    output.mkdir(parents=True, exist_ok=True)
    graph = load_graph(spark, str(source))
    ids = graph.vertices.select("id").persist(StorageLevel.DISK_ONLY)
    try:
        integrity = check_integrity(GraphFrame(ids, graph.edges), verbose=False)
        if any(integrity[k] for k in ("null_vertices", "null_edges", "dangling_edges")):
            raise ValueError("Invalid full graph")
        if ids.groupBy("id").count().where("count<>1").limit(1).count():
            raise ValueError("Vertex IDs are not unique")
        expected = {"paysim": (9073900, 6362620), "ibm_aml": (518581, 5078345)}[dataset]
        if not fixture and (integrity["num_vertices"], integrity["num_edges"]) != expected:
            raise ValueError("Full dataset cardinality differs from the declared benchmark")
        normalized = normalize_edges(graph.edges, DATASETS[dataset]).repartition(config.partitions)
        normalized.withColumn("event_id", F.monotonically_increasing_id()).write.parquet(str(output / "transactions.parquet"))
    finally:
        ids.unpersist(blocking=True)
    tx = spark.read.parquet(str(output / "transactions.parquet"))
    support = tx.agg(F.count("*").alias("n"), F.countDistinct("event_id").alias("unique_ids"),
                     F.sum("isFraud").alias("positives"), F.min("step").alias("first_step"), F.max("step").alias("last_step")).first().asDict()
    if support["n"] != integrity["num_edges"] or support["unique_ids"] != support["n"]:
        raise ValueError("The common transaction index lost/duplicated physical rows")
    cuts = tuple(int(c) for c in tx.approxQuantile("step", list(config.snapshot_fractions), .001))
    if len(set(cuts)) != len(cuts):
        raise ValueError("Insufficient distinct time boundaries")
    record = {"schema_version": "graphguard.full_system.v1", "dataset": dataset,
        "scope": "synthetic_fixture" if fixture else "full", "status": "running",
        "created_utc": datetime.now(timezone.utc).isoformat(), "config": config.as_dict(),
        "input": input_fingerprint(source), "source_sha256": {str(p.relative_to(REPO_ROOT)): file_fingerprint(p)["sha256"] for p in system_sources()},
        "integrity": integrity, "support": support, "snapshot_cutoffs": cuts, "phases": {},
        "test_status": "Reused internal temporal holdout; not an untouched external benchmark",
        "backend": "SQL disk-checkpoint PageRank; modal-neighbor LPA with stable xxhash64 seed labels (collision checked) and minimum-label ties"}
    run = FullSystemRun(spark, dataset, source, output, config, record)
    run.save()
    print(f"[SYSTEM] Indexed {support['n']:,} {record['scope']} transactions once; cutoffs={cuts}", flush=True)
    return run


def _finish_system_phase(run, phase, started, details):
    from src.common.hardware_guard import protection_snapshot
    run.record["phases"][phase] = {"status": "PASS", "elapsed_seconds": round(time.perf_counter()-started, 3),
                                    **details, "hardware": protection_snapshot()}
    run.save()
    print(f"[SYSTEM] {phase}: PASS", flush=True)
    return run.record["phases"][phase]


def full_system_centrality(run):
    """Task 2 on ALL accounts/edges; summaries are views, not input sampling."""
    from src.paysim.metrics import dataframe_pagerank
    from src.common.graph_utils import write_spark_csv
    started = time.perf_counter()
    graph = load_graph(run.spark, str(run.input_dir))
    ids = graph.vertices.select("id")
    edges = graph.edges.select("src", "dst")
    ranks = dataframe_pagerank(ids, edges, run.output_dir / ".work/full_pagerank", run.config.pagerank_iterations)
    incoming = edges.groupBy("dst").count().select(F.col("dst").alias("id"), F.col("count").alias("inDegree"))
    outgoing = edges.groupBy("src").count().select(F.col("src").alias("id"), F.col("count").alias("outDegree"))
    accounts = (ranks.join(incoming, "id", "left").join(outgoing, "id", "left").fillna(0, subset=["inDegree", "outDegree"])
        .withColumn("degree", F.col("inDegree")+F.col("outDegree")))
    accounts.write.parquet(str(run.output_dir / "account_metrics.parquet"))
    accounts = run.table("account_metrics")
    counts = accounts.agg(F.count("*").alias("accounts"), F.sum("degree").alias("degree_sum"),
                          F.sum("pagerank").alias("rank_sum")).first().asDict()
    if counts["accounts"] != run.record["integrity"]["num_vertices"] or counts["degree_sum"] != 2*run.record["support"]["n"]:
        raise ValueError("Full centrality account/degree coverage mismatch")
    if abs(counts["rank_sum"] - counts["accounts"]) > counts["accounts"]*1e-9:
        raise ValueError("PageRank normalization mismatch")
    distribution = accounts.groupBy("degree").count().withColumnRenamed("count", "account_count").orderBy("degree")
    write_spark_csv(distribution, run.output_dir / "degree_distribution.csv")
    write_spark_csv(accounts.orderBy(F.desc("pagerank"), "id").limit(10), run.output_dir / "top10_pagerank.csv")
    return _finish_system_phase(run, "centrality_full", started, counts)


def full_system_communities(run):
    """Task 4 full assignments, every community and per-currency amounts."""
    from src.paysim.community_detection import dataframe_lpa
    from src.common.graph_utils import write_spark_csv
    started = time.perf_counter()
    graph = load_graph(run.spark, str(run.input_dir))
    assignments = dataframe_lpa(graph.vertices, graph.edges.select("src", "dst"),
                               run.output_dir / ".work/full_lpa", run.config.lpa_iterations)
    assignments.write.parquet(str(run.output_dir / "communities.parquet"))
    assignments = run.table("communities")
    members = assignments.groupBy("label").agg(F.count("*").alias("member_count"))
    for kind in ("Customer", "Merchant") if run.dataset == "paysim" else ():
        counts = assignments.where(F.col("account_type") == kind).groupBy("label").count()
        members = members.join(counts.withColumnRenamed("count", kind.lower()+"_count"), "label", "left").fillna(0)
    if run.dataset == "ibm_aml":
        banks = assignments.groupBy("label").agg(F.countDistinct("bank_id").alias("unique_banks_count"))
        members = members.join(banks, "label")
    tx = run.table("transactions")
    links = tx.join(assignments.select(F.col("id").alias("src"), F.col("label").alias("source_group")), "src").join(
        assignments.select(F.col("id").alias("dst"), F.col("label").alias("dest_group")), "dst")
    stats = links.groupBy("source_group").agg(F.count("*").alias("total_tx_count"),
        F.sum("isFraud").cast("long").alias("positive_tx_count"),
        F.sum((F.col("source_group")==F.col("dest_group")).cast("long")).alias("internal_tx_count"))
    summary = members.join(stats.withColumnRenamed("source_group", "label"), "label", "left").fillna(0)
    summary = summary.withColumn("cross_tx_count", F.col("total_tx_count")-F.col("internal_tx_count"))
    summary.write.parquet(str(run.output_dir / "community_summary_all.parquet"))
    summary = run.table("community_summary_all")
    amounts = links.groupBy("source_group", "payment_currency").agg(F.count("*").alias("total_tx_count"),
        F.sum("amount").alias("total_tx_amount")).withColumnRenamed("source_group", "label")
    amounts.write.parquet(str(run.output_dir / "community_amounts_by_currency.parquet"))
    write_spark_csv(summary.orderBy(F.desc("member_count"), "label").limit(50), run.output_dir / "community_top50.csv")
    write_spark_csv(summary.groupBy("member_count").count().orderBy("member_count"), run.output_dir / "community_size_distribution.csv")
    from src.common.project_audit import verify_full_system_communities
    details = verify_full_system_communities(run)
    return _finish_system_phase(run, "communities_full", started, details)


def full_system_motif_features(run):
    """Run existing causal motifs on the same full indexed transaction table."""
    started = time.perf_counter()
    tx = run.table("transactions")
    raw = tx.drop("isFraud")
    vertices = load_graph(run.spark, str(run.input_dir)).vertices.select("id")
    features = build_motif_features(raw, vertices, DATASETS[run.dataset], run.config.analysis.windows_hours)
    try:
        features.write.parquet(str(run.output_dir / "motif_features.parquet"))
    finally:
        features.unpersist(blocking=True)
    table = run.table("motif_features")
    counts = table.agg(F.count("*").alias("rows"), F.countDistinct("event_id").alias("unique_ids")).first().asDict()
    if counts["rows"] != run.record["support"]["n"] or counts["unique_ids"] != counts["rows"]:
        raise ValueError("Motif features lost/duplicated full transaction rows")
    return _finish_system_phase(run, "motif_features", started, counts)


def historical_system_snapshot(run, cutoff, directory):
    """Label-blind historical graph; same PageRank/LPA backends as full outputs."""
    from src.motif.evaluation import require_unlabelled
    from src.paysim.metrics import dataframe_pagerank
    from src.paysim.community_detection import dataframe_lpa
    edges = run.table("transactions").where(F.col("step") <= cutoff).select("src", "dst")
    require_unlabelled(edges)
    ids = edges.select(F.col("src").alias("id")).unionByName(edges.select(F.col("dst").alias("id"))).distinct()
    ranks = dataframe_pagerank(ids, edges, Path(directory)/"pagerank", run.config.pagerank_iterations)
    labels = dataframe_lpa(ids, edges, Path(directory)/"lpa", run.config.lpa_iterations)
    incoming = edges.groupBy("dst").count().select(F.col("dst").alias("id"), F.col("count").alias("inDegree"))
    outgoing = edges.groupBy("src").count().select(F.col("src").alias("id"), F.col("count").alias("outDegree"))
    sizes = labels.groupBy("label").agg(F.count("*").alias("community_size"))
    links = edges.join(labels.select(F.col("id").alias("src"), F.col("label").alias("s")), "src").join(
        labels.select(F.col("id").alias("dst"), F.col("label").alias("d")), "dst")
    stats = links.groupBy("s").agg(F.count("*").alias("community_out_transactions"),
        F.avg((F.col("s")!=F.col("d")).cast("double")).alias("community_cross_fraction")).withColumnRenamed("s", "label")
    return (labels.join(sizes, "label").join(stats, "label", "left").join(ranks, "id").join(incoming, "id", "left")
        .join(outgoing, "id", "left").fillna(0).withColumn("degree", F.col("inDegree")+F.col("outDegree"))
        .withColumnRenamed("label", "community_key").withColumn("as_of_step", F.lit(int(cutoff)).cast("long")))


def join_system_snapshot(transactions, snapshot):
    """Join one snapshot to a strictly later block without changing its rows."""
    from src.motif.config import CENTRALITY_COLUMNS, COMMUNITY_COLUMNS
    from src.motif.evaluation import require_unlabelled
    require_unlabelled(transactions)
    names = ["inDegree", "outDegree", "degree", "pagerank", "community_size", "community_cross_fraction", "community_out_transactions"]
    result = transactions
    if snapshot is None:
        for name in [*CENTRALITY_COLUMNS, *COMMUNITY_COLUMNS]:
            result = result.withColumn(name, F.lit(0.0))
        return result.withColumn("snapshot_as_of", F.lit(None).cast("long"))
    require_unlabelled(snapshot)
    cuts = snapshot.select("as_of_step").distinct().limit(2).collect()
    if len(cuts) != 1 or transactions.where(F.col("step") <= cuts[0].as_of_step).limit(1).count():
        raise ValueError("Every decision row must strictly follow one snapshot cutoff")
    for side in ("src", "dst"):
        lookup = snapshot.select(F.col("id").alias(side), F.lit(1.0).alias(side+"_seen"),
            F.col("community_key").alias(side+"_community_key"), *[F.col(n).cast("double").alias(side+"_"+n) for n in names])
        result = result.join(lookup, side, "left")
    seen = (F.coalesce(F.col("src_seen"), F.lit(0))==1) & (F.coalesce(F.col("dst_seen"), F.lit(0))==1)
    result = result.withColumn("community_endpoints_seen", seen.cast("double")).withColumn(
        "same_community", (seen & (F.col("src_community_key")==F.col("dst_community_key"))).cast("double"))
    return result.fillna(0, subset=[*CENTRALITY_COLUMNS, *COMMUNITY_COLUMNS]).drop("src_community_key", "dst_community_key").withColumn(
        "snapshot_as_of", F.lit(int(cuts[0].as_of_step)).cast("long"))


def full_system_feature_table(run):
    """Five declared snapshots cover training, all validation folds and test."""
    started = time.perf_counter()
    cuts = run.record["snapshot_cutoffs"]
    features = run.table("motif_features")
    block_paths = []
    boundaries = [None, *cuts]
    for index, cutoff in enumerate(boundaries):
        block = features
        if cutoff is not None:
            block = block.where(F.col("step") > cutoff)
        if index < len(cuts):
            block = block.where(F.col("step") <= cuts[index])
        snapshot = None
        if cutoff is not None:
            print(f"[SYSTEM] Historical snapshot {index}/{len(cuts)}, cutoff={cutoff}", flush=True)
            work = run.output_dir / ".work" / f"snapshot_{index}"
            snapshot = historical_system_snapshot(run, cutoff, work)
            path = run.output_dir / "snapshots" / f"snapshot_{index}.parquet"
            snapshot.write.parquet(str(path))
            snapshot = run.spark.read.parquet(str(path))
        joined = join_system_snapshot(block, snapshot).withColumn("time_block", F.lit(index))
        path = run.output_dir / "feature_blocks" / f"block_{index}.parquet"
        joined.write.parquet(str(path))
        block_paths.append(path)
    common = run.spark.read.parquet(*[str(p) for p in block_paths])
    common.write.parquet(str(run.output_dir / "features.parquet"))
    table = run.table("features")
    counts = table.agg(F.count("*").alias("rows"), F.countDistinct("event_id").alias("unique_ids"),
        F.sum(F.when(F.col("snapshot_as_of") >= F.col("step"), 1).otherwise(0)).alias("future_snapshot_rows")).first().asDict()
    if counts["rows"] != run.record["support"]["n"] or counts["unique_ids"] != counts["rows"] or counts["future_snapshot_rows"]:
        raise ValueError("Common feature table failed coverage/causality invariants")
    return _finish_system_phase(run, "common_features", started, counts)


def full_system_validation(run):
    """All eight families see identical rows, folds and declared tuning budget."""
    from src.motif.config import SYSTEM_FAMILY_GROUPS
    from src.motif.evaluation import require_unlabelled
    started = time.perf_counter()
    features = run.table("features")
    require_unlabelled(features)
    truth = run.table("transactions").select("event_id", "isFraud")
    boundaries = run.record["snapshot_cutoffs"][1:]
    records, aps = [], []
    for fold, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:]), 1):
        for family in SYSTEM_FAMILY_GROUPS:
            print(f"[SYSTEM] Validation {fold}/3: {family}, train<={start}, validation<={end}", flush=True)
            model = fit_risk_model(features, truth, start, family, run.config.analysis, spill_training=True)
            try:
                interval = features.where((F.col("step") > start) & (F.col("step") <= end))
                scores = score_transactions(model, interval)
                histogram = score_histogram(scores, truth, start, end)
                curve, ap = precision_recall_curve(histogram)
                aps.append({"fold": fold, "family": family, "average_precision": ap,
                            "transactions": int(histogram["count"].sum())})
                for threshold in run.config.analysis.score_thresholds:
                    records.append({"fold": fold, "family": family, "threshold": threshold, **metrics_at_threshold(histogram, threshold)})
            finally:
                model.scales.unpersist(blocking=True)
    folds = pd.DataFrame(records)
    counts = folds.groupby("fold").transactions.nunique()
    if not (counts == 1).all():
        raise ValueError("Ablation validation populations differ")
    selection, leaderboard = choose_walk_forward_rule(folds)
    rules = {name: _records(leaderboard[leaderboard.family == name].head(1))[0] for name in SYSTEM_FAMILY_GROUPS}
    payload = {"selection": _records(pd.DataFrame([selection]))[0], "family_rules": rules,
               "selection_criterion": "mean validation F1; worst-fold F1, fewer FP, simpler family, higher threshold ties"}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    (run.output_dir / "frozen_rules.json").write_text(json.dumps({**payload, "sha256": digest}, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    folds.to_csv(run.output_dir / "walk_forward.csv", index=False, encoding="utf-8-sig")
    leaderboard.to_csv(run.output_dir / "validation_leaderboard.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(aps).to_csv(run.output_dir / "validation_average_precision.csv", index=False, encoding="utf-8-sig")
    run.record["frozen_rule_sha256"] = digest
    _finish_system_phase(run, "validation", started, {"selection": payload["selection"], "families": len(rules), "folds": 3})
    return leaderboard


def frozen_system_rules(run):
    payload = json.loads((run.output_dir / "frozen_rules.json").read_text(encoding="utf-8"))
    expected = payload.pop("sha256")
    actual = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if actual != expected or actual != run.record["frozen_rule_sha256"]:
        raise ValueError("Frozen selection changed after validation")
    return payload


def system_budget_metrics(predictions, features, fractions):
    """Exactly K reviews; ties break by content key then common run-local ID."""
    import math
    labelled = predictions.join(features.select("event_id", "event_key"), "event_id")
    counts = labelled.agg(F.count("*").alias("n"), F.sum("isFraud").alias("p")).first()
    budgets = sorted(set(max(1, min(counts.n, math.ceil(counts.n*f))) for f in fractions))
    top = (labelled.orderBy(F.desc("risk_score"), "event_key", "event_id").limit(max(budgets))
           .select("event_id", "risk_score", "isFraud").toPandas())
    if len(top) != max(budgets):
        raise ValueError("Top-K coverage mismatch")
    return [{"review_fraction": fraction, "K": max(1, min(counts.n, math.ceil(counts.n*fraction))),
        "transactions": counts.n, "fraud": int(counts.p),
        "TP_at_K": int(top.head(max(1, min(counts.n, math.ceil(counts.n*fraction)))).isFraud.sum()),
        "precision_at_K": float(top.head(max(1, min(counts.n, math.ceil(counts.n*fraction)))).isFraud.mean()),
        "recall_at_K": float(top.head(max(1, min(counts.n, math.ceil(counts.n*fraction)))).isFraud.sum()/counts.p) if counts.p else None,
        "tie_policy": "risk descending, event_key ascending, event_id ascending"} for fraction in fractions]


def load_full_system_model(run, family):
    """Native JVM reader avoids the Spark 3.5 Python worker metadata path."""
    from pyspark.ml import PipelineModel
    from pyspark.ml.util import JavaMLReader
    from src.motif.modeling import RiskModel
    directory = run.output_dir / "models" / family
    metadata = json.loads((directory / "training.json").read_text(encoding="utf-8"))
    fitted = JavaMLReader(PipelineModel).session(run.spark).load(str(directory / "model")) if metadata["has_model"] else None
    return RiskModel(family, fitted, run.spark.read.parquet(str(directory / "amount_scales.parquet")),
                     metadata["feature_names"], metadata["training"])


def full_system_test(run):
    """Freeze -> refit -> export all ablations; test never selects a new rule."""
    from src.motif.config import SYSTEM_FAMILY_GROUPS
    from src.motif.evaluation import binary_metrics
    started = time.perf_counter()
    rules = frozen_system_rules(run)
    features = run.table("features")
    cutoff = run.record["snapshot_cutoffs"][-1]
    future = features.where(F.col("step") > cutoff)
    tx = run.table("transactions")
    truth = tx.select("event_id", "isFraud")
    support = tx.where(F.col("step") > cutoff).agg(F.count("*").alias("n"), F.sum("isFraud").alias("p")).first()
    metrics, budgets, importances = [], [], []
    for family in SYSTEM_FAMILY_GROUPS:
        frozen_system_rules(run)
        print(f"[SYSTEM] Frozen refit/test: {family}", flush=True)
        model = fit_risk_model(features, truth, cutoff, family, run.config.analysis, spill_training=True)
        try:
            directory = run.output_dir / "models" / family
            directory.mkdir(parents=True, exist_ok=True)
            if model.pipeline is not None:
                model.pipeline.write().save(str(directory / "model"))
            model.scales.write.parquet(str(directory / "amount_scales.parquet"))
            metadata = {"feature_names": model.feature_names, "training": model.training, "has_model": model.pipeline is not None}
            (directory / "training.json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
            importance = model.importance().assign(family=family)
            importances += importance.to_dict("records")
            threshold = float(rules["family_rules"][family]["threshold"])
            scores = score_transactions(model, future).select("event_id", "risk_score")
            prediction = scores.withColumn("alert", F.col("risk_score") >= threshold).join(truth, "event_id")
            path = run.output_dir / "predictions" / (family+".parquet")
            prediction.write.parquet(str(path))
            saved = run.spark.read.parquet(str(path))
            checks = saved.agg(F.count("*").alias("n"), F.countDistinct("event_id").alias("unique_ids"), F.sum("isFraud").alias("p"),
                F.sum(F.when(F.col("alert") & (F.col("isFraud")==1), 1).otherwise(0)).alias("tp"),
                F.sum(F.when(F.col("alert") & (F.col("isFraud")==0), 1).otherwise(0)).alias("fp")).first()
            if checks.n != support.n or checks.unique_ids != support.n or checks.p != support.p:
                raise ValueError("Final ablation coverage differs from the common test denominator")
            histogram = saved.groupBy("risk_score", "isFraud").count().toPandas()
            curve, ap = precision_recall_curve(histogram)
            curve.to_csv(run.output_dir / ("pr_curve_"+family+".csv"), index=False, encoding="utf-8-sig")
            row = {"model": family, "threshold": threshold, **binary_metrics(checks.n, checks.p, checks.tp, checks.fp),
                   "average_precision": ap, "selected_on_validation": family == rules["selection"]["family"]}
            row["precision_low95"], row["precision_high95"] = wilson_interval(row["TP"], row["alerts"])
            row["recall_low95"], row["recall_high95"] = wilson_interval(row["TP"], row["fraud"])
            metrics.append(row)
            budgets += [{"model": family, **row} for row in system_budget_metrics(saved, future, run.config.review_fractions)]
            # Test-only examples are exported after frozen fitting and scoring.
            cases = {"TP": "alert AND isFraud=1", "FP": "alert AND isFraud=0", "FN": "NOT alert AND isFraud=1"}
            context = saved.join(future, "event_id")
            for case, condition in cases.items():
                examples = context.where(condition).orderBy(F.desc("risk_score"), "event_key", "event_id").limit(run.config.analysis.example_limit)
                columns = [c for c in ("event_id", "event_key", "step", "src", "dst", "type", "amount", "payment_currency", "risk_score", "alert", "isFraud", "snapshot_as_of", "src_seen", "dst_seen", "cycle3_count", "cycle3_witness") if c in examples.columns]
                examples.select(columns).toPandas().to_json(run.output_dir / f"examples_{family}_{case}.json", orient="records", indent=2, force_ascii=False)
        finally:
            model.scales.unpersist(blocking=True)
    table = pd.DataFrame(metrics)
    table.to_csv(run.output_dir / "test_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(budgets).to_csv(run.output_dir / "review_budgets.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(importances).to_csv(run.output_dir / "feature_importance.csv", index=False, encoding="utf-8-sig")
    selected = rules["selection"]["family"]
    if selected != "abstain":
        loaded = load_full_system_model(run, selected)
        try:
            replay = score_transactions(loaded, future).select("event_id", F.col("risk_score").alias("replayed"))
            saved = run.spark.read.parquet(str(run.output_dir / "predictions" / (selected+".parquet")))
            if replay.join(saved, "event_id").where(F.abs(F.col("replayed")-F.col("risk_score")) > 1e-12).limit(1).count():
                raise ValueError("Reloaded selected model does not reproduce test scores")
        finally:
            loaded.scales.unpersist(blocking=True)
    if selected == "abstain":
        final = future.select("event_id").withColumn("risk_score", F.lit(0.0)).withColumn("alert", F.lit(False)).join(truth, "event_id")
    else:
        final = run.spark.read.parquet(str(run.output_dir / "predictions" / (selected+".parquet")))
    context_columns = ["event_id", "event_key", "step", "src", "dst", "amount", "type", "payment_currency", "receiving_currency", "snapshot_as_of", "time_block", "src_seen", "dst_seen"]
    final = (final.join(future.select(context_columns), "event_id")
        .withColumn("dataset", F.lit(run.dataset)).withColumn("run_id", F.lit(run.output_dir.name))
        .withColumn("model", F.lit(selected)).withColumn("threshold", F.lit(float(rules["selection"]["threshold"])))
        .withColumn("decision_policy", F.lit("ABSTAIN" if selected=="abstain" else "validation_F1_threshold")))
    final.write.parquet(str(run.output_dir / "final_predictions.parquet"))
    final = run.table("final_predictions")
    cold = final.withColumn("history_group", F.when((F.col("src_seen")==0) & (F.col("dst_seen")==0), "both_unseen")
        .when((F.col("src_seen")==0) | (F.col("dst_seen")==0), "one_unseen").otherwise("both_seen"))
    groups = cold.groupBy("history_group").agg(F.count("*").alias("n"), F.sum("isFraud").alias("p"),
        F.sum((F.col("alert") & (F.col("isFraud")==1)).cast("long")).alias("tp"),
        F.sum((F.col("alert") & (F.col("isFraud")==0)).cast("long")).alias("fp")).collect()
    pd.DataFrame([{"history_group": g.history_group, **binary_metrics(g.n,g.p,g.tp,g.fp)} for g in groups]).to_csv(
        run.output_dir / "selected_cold_start.csv", index=False, encoding="utf-8-sig")
    categories = F.when(F.col("alert") & (F.col("isFraud")==1), "TP").when(F.col("alert"), "FP").when(F.col("isFraud")==1,"FN").otherwise("TN")
    final.withColumn("case",categories).groupBy("payment_currency","case").agg(F.count("*").alias("transactions"),
        F.sum("amount").alias("payment_amount")).toPandas().to_csv(run.output_dir / "selected_amounts_by_currency.csv",index=False,encoding="utf-8-sig")
    unknown = future.withColumn("novelty_alert", (F.col("src_seen")==0) | (F.col("dst_seen")==0)).join(truth, "event_id")
    novelty_counts = unknown.agg(F.sum(F.col("novelty_alert").cast("long")).alias("alerts"),
        F.sum((F.col("novelty_alert") & (F.col("isFraud")==1)).cast("long")).alias("tp")).first()
    run.record["novelty_baseline"] = binary_metrics(support.n, support.p, int(novelty_counts.tp), int(novelty_counts.alerts-novelty_counts.tp))
    if selected == "abstain":
        run.record["selected_test_metrics"] = binary_metrics(support.n, support.p, 0, 0)
    else:
        run.record["selected_test_metrics"] = _records(table[table.model==selected])[0]
    _finish_system_phase(run, "frozen_test", started, {"models": len(metrics), "test_transactions": support.n,
        "test_positives": int(support.p), "selected_family": selected, "full_test_model_reload": "PASS" if selected!="abstain" else "ABSTAIN"})
    return table


def full_system_baseline(run):
    """Original coursework queries remain separate from label-blind inference."""
    from src.motif.presentation import baseline_audit
    started = time.perf_counter()
    audit = baseline_audit(run.spark, run.dataset, run.input_dir if run.record["scope"]!="full" else None)
    audit.summary.to_csv(run.output_dir / "baseline_summary.csv", index=False, encoding="utf-8-sig")
    audit.examples.to_csv(run.output_dir / "baseline_examples.csv", index=False, encoding="utf-8-sig")
    _finish_system_phase(run, "motif_baseline", started, {"interpretation": "original query / label audit; never inference features"})
    return audit


def finalize_full_system(run):
    """Publish latest only after sources, full coverage, exports and replay pass."""
    from src.common.hardware_guard import protection_snapshot
    required = ("centrality_full", "communities_full", "motif_features", "common_features", "validation", "frozen_test")
    if any(run.record["phases"].get(name, {}).get("status") != "PASS" for name in required):
        raise ValueError("Full system still has incomplete phases")
    if run.record["scope"] == "full" and run.record["phases"].get("raw_reconciliation", {}).get("status") != "PASS":
        raise ValueError("Full raw reconciliation is required before acceptance")
    if run.record.get("status") == "completed":
        raise ValueError("Completed runs are immutable; start a new run")
    frozen_system_rules(run)
    current = {str(p.relative_to(REPO_ROOT)): file_fingerprint(p)["sha256"] for p in system_sources()}
    if current != run.record["source_sha256"]:
        raise ValueError("Source changed during the full run; do not publish stale outputs")
    report = {**run.record, "status": "completed", "finished_utc": datetime.now(timezone.utc).isoformat(),
              "frozen_rules": frozen_system_rules(run), "hardware": protection_snapshot(),
              "test_metrics": _records(pd.read_csv(run.output_dir / "test_metrics.csv")),
              "limitations": ["Synthetic data; reused internal temporal holdout", "Weighted score is not calibrated probability",
                  "Community label IDs are not fraud labels or features", "No prediction quality is assumed from software PASS",
                  "Snapshot features have declared lag; first warm-up block has no graph history"]}
    (run.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    excluded = {"system_state.json", "artifact_index.json", "run.json"}
    members = []
    for path in sorted(run.output_dir.rglob("*")):
        if not path.is_file() or path.name in excluded or any(part in (".work", "feature_blocks") for part in path.relative_to(run.output_dir).parts):
            continue
        members.append({"path": path.relative_to(run.output_dir).as_posix(), "bytes": path.stat().st_size,
                        "sha256": file_fingerprint(path)["sha256"]})
    (run.output_dir / "artifact_index.json").write_text(json.dumps(members, indent=2)+"\n", encoding="utf-8")
    write_run_evidence(run.output_dir / "run.json", run.spark, task="Full system "+run.dataset,
        inputs=[run.input_dir], outputs=[run.output_dir / name for name in ("report.json", "artifact_index.json")],
        sources=system_sources(), parameters=run.config.as_dict(), metrics={"scope": run.record["scope"],
            "transactions": run.record["support"]["n"], "test_transactions": run.record["phases"]["frozen_test"]["test_transactions"]})
    from src.common.project_audit import verify_full_system_artifacts
    result = verify_full_system_artifacts(run.output_dir, require_full=run.record["scope"]=="full")
    run.record["status"] = "completed"
    run.record["verification"] = result
    run.save()
    if run.record["scope"] == "full":
        pointer = REPO_ROOT / "results/full_system" / run.dataset / "latest.json"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(json.dumps({"directory": str(run.output_dir), "status": "completed",
                                      "report_sha256": file_fingerprint(run.output_dir / "report.json")["sha256"]}, indent=2)+"\n", encoding="utf-8")
    return pd.DataFrame([{"check": key, "result": value} for key, value in result.items()])



def full_system_main(argv=None):
    from src.motif.presentation import start_system_session, plot_system_centrality, plot_system_communities, plot_system_validation, plot_system_results, system_case_evidence
    parser = argparse.ArgumentParser(description="Guarded full-data transaction system and eight ablations")
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    session = start_system_session(args.dataset)
    try:
        run = start_full_system(session.spark, args.dataset, args.output_dir)
        full_system_raw_reconciliation(run)
        full_system_centrality(run)
        plot_system_centrality(run)
        full_system_communities(run)
        plot_system_communities(run)
        full_system_baseline(run)
        full_system_motif_features(run)
        full_system_feature_table(run)
        full_system_validation(run)
        plot_system_validation(run)
        print(full_system_test(run).to_string(index=False))
        plot_system_results(run)
        system_case_evidence(run)
        print(finalize_full_system(run).to_string(index=False))
    finally:
        print(session.close().to_string(index=False))



def full_system_raw_reconciliation(run):
    """Full duplicate-preserving raw/Parquet comparison, not a spot check."""
    from pyspark import StorageLevel
    started = time.perf_counter()
    if run.record["scope"] != "full":
        raise ValueError("Raw reconciliation requires the declared real full dataset")
    if run.dataset == "ibm_aml":
        from src.motif.reviews import review_ibm_etl
        previous = run.spark.conf.get("spark.sql.session.timeZone")
        try:
            # Match the timezone explicitly used to produce the delivered IBM Parquet.
            run.spark.conf.set("spark.sql.session.timeZone", "Asia/Saigon")
            review = review_ibm_etl(run.spark, REPO_ROOT)
        finally:
            run.spark.conf.set("spark.sql.session.timeZone", previous)
        details = {"tables": review.comparison.to_dict("records"), "timezone": "Asia/Saigon for raw timestamp mapping", "vertex_balance": "full raw contract"}
        raw_files = [REPO_ROOT / "data/raw/ibm_aml" / name for name in ("HI-Small_Trans.csv", "HI-Small_accounts.csv")]
    else:
        from src.paysim.etl_mapping import build_edges_df, build_vertices_df
        raw_file = REPO_ROOT / "data/raw/paysim/PS_20174392719_1491204439457_log.csv"
        raw = run.spark.read.option("header", True).csv(str(raw_file))
        expected_edges = build_edges_df(raw).persist(StorageLevel.DISK_ONLY)
        expected_vertices = build_vertices_df(raw).select("id", "account_type").persist(StorageLevel.DISK_ONLY)
        try:
            graph = load_graph(run.spark, str(run.input_dir))
            tables = []
            for name, expected, saved in (("edges", expected_edges, graph.edges), ("vertices_id_type", expected_vertices, graph.vertices)):
                columns = sorted(expected.columns)
                missing = expected.select(columns).exceptAll(saved.select(columns)).limit(1).count()
                extra = saved.select(columns).exceptAll(expected.select(columns)).limit(1).count()
                if missing or extra:
                    raise ValueError("Full raw/Parquet multiset differs: "+name)
                tables.append({"table": name, "raw_minus_parquet": missing, "parquet_minus_raw": extra, "status": "PASS"})
            details = {"tables": tables, "vertex_balance": "not compared: equal-hour max_by is ambiguous; never a detector feature"}
        finally:
            expected_edges.unpersist(blocking=True)
            expected_vertices.unpersist(blocking=True)
        raw_files = [raw_file]
    details["raw_files"] = [file_fingerprint(path) for path in raw_files]
    return _finish_system_phase(run, "raw_reconciliation", started, details)

if __name__ == "__main__":
    main()
