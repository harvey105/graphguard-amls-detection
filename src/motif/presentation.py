"""Notebook views only; algorithms and experiment control live in Python modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import warnings

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
import numpy as np
import pandas as pd
from graphframes import GraphFrame
from pyspark.sql import functions as F

from src.common.graph_utils import load_graph
from src.common.hardware_guard import protection_snapshot
from src.common.run_evidence import REPO_ROOT, file_fingerprint
from src.common.spark_session import get_graph_session
from src.motif.config import DATASETS


@dataclass
class NotebookSession:
    dataset: str
    spark: object
    temporary: object
    runtime: pd.DataFrame
    started_clock: float

    @property
    def repo(self):
        return REPO_ROOT

    @property
    def checkpoint(self):
        return Path(self.temporary.name) / "lpa"

    @classmethod
    def start(cls, dataset: str, driver_memory: str = "5g"):
        if dataset not in DATASETS:
            raise ValueError("Unknown dataset")
        if os.name != "nt" or sys.version_info[:2] != (3, 12):
            raise RuntimeError("Select native Windows .venv Python 3.12")
        if not os.path.samefile(sys.executable, REPO_ROOT / ".venv/Scripts/python.exe"):
            raise RuntimeError("Select the repository's Windows .venv kernel")
        dependencies = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
        if dependencies.returncode:
            raise RuntimeError(dependencies.stdout + dependencies.stderr)
        if metadata.version("pyspark") != "3.5.1" or metadata.version("graphframes-py") != "0.12.2":
            raise RuntimeError("Use pinned requirements.txt")
        temporary = tempfile.TemporaryDirectory(prefix="graphguard-motif-v2-", ignore_cleanup_errors=True)
        started = time.perf_counter()
        spark = get_graph_session("GraphGuard-Motif-v2-" + dataset, driver_memory=driver_memory, shuffle_partitions=32,
            extra_configs={"spark.master": "local[*]",
                "spark.ui.enabled": "false", "spark.ui.showConsoleProgress": "false",
                "spark.sql.session.timeZone": "UTC",
                # Twenty writers must not each reserve a 128 MiB row group.
                "spark.hadoop.parquet.block.size": "33554432",
                "spark.sql.parquet.columnarReaderBatchSize": "1024",
                "spark.sql.inMemoryColumnarStorage.batchSize": "1000",
                "spark.ui.retainedJobs": "20", "spark.ui.retainedStages": "40", "spark.sql.ui.retainedExecutions": "20",
                "spark.sql.warehouse.dir": (Path(temporary.name) / "warehouse").as_uri()})
        spark.sparkContext.setLogLevel("ERROR")
        java = spark.sparkContext._jvm.java.lang.System.getProperty("java.version")
        if not java.startswith("17."):
            spark.stop()
            temporary.cleanup()
            raise RuntimeError("JDK 17 is required")
        plt.rcParams.update({"figure.dpi": 110, "font.family": "DejaVu Sans", "font.size": 10,
                             "axes.spines.top": False, "axes.spines.right": False})
        # Known compatibility deprecations from pinned Spark 3.5 + pandas 3;
        # keep presentation outputs readable without suppressing runtime errors.
        warnings.filterwarnings("ignore", message="distutils Version classes are deprecated.*",
                                category=DeprecationWarning, module=r"pyspark\.sql\.pandas\.utils")
        warnings.filterwarnings("ignore", message="The copy keyword is deprecated.*",
                                module=r"pyspark\.sql\.pandas\.types")
        runtime = pd.DataFrame([{"dataset": dataset, "system": platform.system(),
            "python": platform.python_version(), "spark": spark.version, "graphframes": metadata.version("graphframes-py"),
            "java": java, "master": spark.sparkContext.master,
            "driver_memory": spark.sparkContext.getConf().get("spark.driver.memory"),
            "pip_check": "PASS", **protection_snapshot()}])
        runtime = runtime.T.rename(columns={0: "value"}).rename_axis("setting").reset_index()
        return cls(dataset, spark, temporary, runtime, started)

    def close(self) -> pd.DataFrame:
        record = {"dataset": self.dataset, "finished_utc": datetime.now(timezone.utc).isoformat(),
                  "elapsed_seconds": round(time.perf_counter() - self.started_clock, 1),
                  "execution": "Completed; performance is reported separately", **protection_snapshot()}
        self.spark.catalog.clearCache()
        self.spark.stop()
        self.temporary.cleanup()
        return pd.DataFrame(record.items(), columns=["setting", "value"])


@dataclass
class BaselineAudit:
    summary: pd.DataFrame
    examples: pd.DataFrame
    currencies: pd.DataFrame


def baseline_audit(spark, dataset: str, input_dir: Path | None = None, *, kernels=None) -> BaselineAudit:
    """Execute original coursework queries, without overwriting baseline CSVs."""
    from src.ibm_aml.motif_finding import directed_account_cycles, find_usd_cycles
    from src.motif.toy_cycle import find_three_node_cycles
    from src.paysim.motif_finding import find_relays, relay_rows
    find_three_node_cycles = (kernels or {}).get("find_three_node_cycles", find_three_node_cycles)
    find_relays = (kernels or {}).get("find_relays", find_relays)

    source = input_dir or REPO_ROOT / DATASETS[dataset].input_dir
    loaded = load_graph(spark, str(source))
    vertices = loaded.vertices.select("id").cache()
    owned = [vertices]
    try:
        if dataset == "paysim":
            edges = loaded.edges.select("src", "dst", "type", "amount", "step", "isFraud").cache()
            owned.append(edges)
            graph = GraphFrame(vertices, edges)
            cycles = find_three_node_cycles(graph).count()
            matches = find_relays(graph, 10_000., 24).cache()
            owned.append(matches)
            count = matches.count()
            same_hour = matches.where(F.col("e1.step") == F.col("e2.step")).count()
            examples = relay_rows(matches).orderBy("transfer_step", "source_account").limit(1000).toPandas()
            if input_dir is None:
                saved = pd.read_csv(REPO_ROOT / "results/paysim/relay_candidates.csv")
                keys = list(examples.columns)
                pd.testing.assert_frame_equal(examples.sort_values(keys).reset_index(drop=True),
                    saved[keys].sort_values(keys).reset_index(drop=True), check_dtype=False, check_exact=True)
            summary = {"dataset": dataset, "raw_cycles": cycles, "relay_pairs": count, "same_hour": same_hour,
                       "fraud_transfer_edges": int(examples.transfer_isFraud.sum()),
                       "fraud_cashout_edges": int(examples.cashout_isFraud.sum())}
            currencies = pd.DataFrame()
        else:
            edges = loaded.edges.select("src", "dst", "isFraud", "amount", "payment_currency").cache()
            owned.append(edges)
            graph = GraphFrame(vertices, edges)
            fraud = edges.where(F.col("isFraud") == 1)
            matches = find_three_node_cycles(GraphFrame(vertices, fraud)).cache()
            owned.append(matches)
            directed = directed_account_cycles(matches)
            examples = directed.orderBy(F.desc("transaction_combinations"), "a", "b", "c").limit(5000).toPandas()
            if input_dir is None:
                saved = pd.read_csv(REPO_ROOT / "results/ibm_aml/fraud_directed_cycles.csv")
                keys = list(examples.columns)
                pd.testing.assert_frame_equal(examples.sort_values(keys).reset_index(drop=True),
                    saved[keys].sort_values(keys).reset_index(drop=True), check_dtype=False, check_exact=True)
            currencies = fraud.groupBy("payment_currency").count().orderBy(F.desc("count")).toPandas()
            summary = {"dataset": dataset, "fraud_edges": fraud.count(), "label_audit_raw_cycles": matches.count(),
                "directed_account_cycles": directed.count(), "transaction_combinations": int(examples.transaction_combinations.sum()),
                "USD_above_10000_cycles": find_usd_cycles(graph, 10_000.).count()}
        return BaselineAudit(pd.DataFrame([summary]), examples, currencies)
    finally:
        for frame in owned:
            frame.unpersist(blocking=True)


def plot_walk_forward(experiment):
    """Use each family's frozen threshold in every validation period."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for family, rule in experiment.family_rules.items():
        rows = experiment.folds[(experiment.folds.family == family) & (experiment.folds.threshold == rule["threshold"])]
        axes[0].plot(rows.fold, rows.F1, marker="o", label=family)
    axes[0].set(xlabel="Validation period", ylabel="F1", title="Expanding-prefix validation", xticks=[1, 2, 3])
    axes[0].legend()
    for family in experiment.family_rules:
        rows = experiment.leaderboard[experiment.leaderboard.family == family].sort_values("threshold")
        axes[1].plot(rows.threshold, rows.mean_F1, marker=".", label=family)
    axes[1].set(xlabel="Weighted tree score threshold", ylabel="Mean validation F1", title="Threshold choice before test")
    axes[1].legend()
    plt.tight_layout()
    plt.show()


def plot_test_results(experiment):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    experiment.metrics.set_index("model")[["precision", "recall", "F1"]].plot.bar(
        ax=axes[0], rot=12, color=["#2563eb", "#f59e0b", "#0f766e"])
    axes[0].set(title="Reused internal test: frozen models", ylabel="Score", ylim=(0, 1))
    for family, curve in experiment.curves.items():
        ap = experiment.metrics.set_index("model").loc[family, "average_precision"]
        axes[1].step(curve.recall, curve.precision, where="pre", label=f"{family}; AP={ap:.3f}")
    prevalence = experiment.metrics.iloc[0].prevalence
    axes[1].axhline(prevalence, linestyle="--", color="#64748b", label=f"Prevalence={prevalence:.4f}")
    axes[1].set(xlabel="Recall", ylabel="Precision", title="Exact discrete-score PR curves", xlim=(0, 1), ylim=(0, 1.03))
    axes[1].legend(fontsize=8)
    plt.tight_layout()
    plt.show()


def plot_feature_importance(experiment):
    importance = experiment.models["motif_assisted"].importance().head(10)
    if importance.empty:
        print("Training had one class; no fitted tree importance.")
        return
    fig, ax = plt.subplots(figsize=(9, 4))
    importance.iloc[::-1].plot.barh(x="feature", y="importance", ax=ax, legend=False, color="#0f766e")
    ax.set(title="Motif-assisted tree: training feature importance", xlabel="Impurity-based importance", ylabel="")
    plt.tight_layout()
    plt.show()


def show_examples(experiment):
    from IPython.display import display
    from src.motif.pipeline import example_transactions

    for case in ("TP", "FP", "FN"):
        print(case + " — selected model, test period")
        rows = example_transactions(experiment, case)
        display(rows[["event_id", "src", "dst", "type", "amount", "payment_currency", "risk_score", "isFraud"]])


def motif_evidence(experiment) -> pd.DataFrame:
    """Illustrative TP chosen after evaluation; labels never generate a path."""
    from src.motif.pipeline import selected_test_predictions

    predictions = selected_test_predictions(experiment)
    positive = predictions.where("alert=1 AND isFraud=1")
    # Prefer a cycle example for IBM, but never substitute a label-filtered query
    # for the actual selected model's output.
    candidates = positive.orderBy(F.desc("cycle3_count"), F.desc("risk_score"), "step", "event_key").limit(1).collect()
    if not candidates:
        print("No test TP from the selected model; no fabricated example.")
        return pd.DataFrame()
    row = candidates[0]
    witness = row.cycle3_witness
    ids = [row.event_id]
    if witness:
        ids += [witness.first_event_id, witness.second_event_id]
    else:
        # Select one interpretable motif, not a cluttered union of every witness.
        from src.motif.features import resolve_star_witness
        for family in ("reciprocal", "relay", "fanin", "fanout"):
            for hours in experiment.config.windows_hours:
                if row[f"{family}_{hours}h"] <= 0:
                    continue
                if family == "reciprocal":
                    found = row[f"reciprocal_witness_{hours}h"]
                else:
                    observed = resolve_star_witness(experiment.features, row.event_id, experiment.spec, family, hours)
                    candidates = observed.orderBy(F.desc("step"), "event_id").select("event_id").limit(1).collect()
                    found = candidates[0].event_id if candidates else None
                if found is not None:
                    ids.append(found)
                    break
            if len(ids) > 1:
                break
    evidence = experiment.features.where(F.col("event_id").isin(ids)).join(
        experiment.truth.select("event_id", "isFraud"), "event_id"
    ).select("event_id", "src", "dst", "step", "amount", "payment_currency", "isFraud").orderBy("step").toPandas()
    evidence["role"] = np.where(evidence.event_id == row.event_id, "current alert", "past witness")
    return evidence


def plot_evidence(evidence: pd.DataFrame, dataset: str):
    if evidence.empty:
        return
    accounts = list(dict.fromkeys([*evidence.src, *evidence.dst]))
    names = {account: f"{chr(65+i)}\n{account}" for i, account in enumerate(accounts)}
    edges, colors = [], []
    for row in evidence.itertuples():
        label = f"{row.amount:,.2f}\nlabel {int(row.isFraud)} · {row.role}"
        edges.append((row.src, row.dst, label))
        colors.append("#dc2626" if row.role == "current alert" else "#64748b")
    draw_graph(names, edges, f"{dataset}: actual selected-model TP and observed evidence", colors=colors)
    if len(evidence) == 1:
        print("No positive multi-edge motif for this TP: transaction/context features produced the alert.")


def plot_pagerank(review):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(review["raw_chain"].sum(axis=1), label="Unrepaired sink", color="#dc2626")
    axes[0].plot(review["fixed_chain"].sum(axis=1), label="Repair + damping", color="#2563eb")
    axes[0].set(xlabel="Iteration", ylabel="Total probability", title="Dangling repair preserves probability")
    axes[0].legend()
    axes[1].bar(np.arange(3)-0.18, review["trapped"][-1], width=0.36, label="d=1", color="#94a3b8")
    axes[1].bar(np.arange(3)+0.18, review["escapable"][-1], width=0.36, label="d=0.85", color="#2563eb")
    axes[1].set(xticks=np.arange(3), xticklabels=["A", "B", "T"], ylabel="Probability", title="Teleportation escapes a trap")
    axes[1].legend()
    plt.tight_layout()
    plt.show()


def plot_lpa(review):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].loglog(review.size_distribution.member_count, review.size_distribution["count"], ".", color="#2563eb")
    axes[0].set(xlabel="Community size", ylabel="Communities", title="Full IBM LPA size distribution")
    overview = review.overview
    axes[1].bar(range(len(overview)), overview.member_count, color="#0f766e")
    axes[1].set(xlabel="Rank by size", ylabel="Accounts", title="Largest communities; not fraud labels")
    plt.tight_layout()
    plt.show()


def source_provenance() -> pd.DataFrame:
    from src.motif.pipeline import source_paths
    paths = source_paths() + [REPO_ROOT / name for name in (
        "src/ibm_aml/etl.py", "src/ibm_aml/community_detection.py", "src/ibm_aml/verify_communities.py",
        "tests/test_ibm_aml_etl.py")]
    return pd.DataFrame([{"source": path.relative_to(REPO_ROOT).as_posix(),
                          "sha256": file_fingerprint(path)["sha256"]} for path in paths])


def _display_figure(figure, output_path=None):
    """Embed a PNG explicitly even when a CLI module selected the Agg backend."""
    from io import BytesIO
    from IPython import get_ipython
    from IPython.display import Image, display

    stream = BytesIO()
    figure.savefig(stream, format="png", dpi=130, bbox_inches="tight")
    png = stream.getvalue()
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(png)
    if get_ipython() is not None:
        display(Image(data=png))
    plt.close(figure)


def draw_graph(nodes, edges, title, positions=None, colors=None, output_path=None):
    if positions is None:
        angles = np.linspace(np.pi / 2, np.pi / 2 - 2 * np.pi, len(nodes), endpoint=False)
        positions = {node: (np.cos(angle), np.sin(angle)) for node, angle in zip(nodes, angles)}
    colors = colors or ['#2563eb'] * len(edges)
    fig, ax = plt.subplots(figsize=(10, 5))
    for index, (source, target, label) in enumerate(edges):
        start, end = np.array(positions[source]), np.array(positions[target])
        direction = end - start
        normal = np.array([-direction[1], direction[0]]) / np.linalg.norm(direction)
        label_position = (start + end) / 2 + 0.22 * normal
        source_padding = 55 if max(map(len, nodes[source].splitlines())) > 10 else 35
        target_padding = 55 if max(map(len, nodes[target].splitlines())) > 10 else 35
        ax.add_patch(FancyArrowPatch(
            start, end, arrowstyle='-|>', mutation_scale=19, linewidth=2,
            shrinkA=source_padding, shrinkB=target_padding,
            color=colors[index % len(colors)], connectionstyle='arc3,rad=0.04',
        ))
        ax.text(
            *label_position, label, ha='center', va='center', fontsize=9,
            bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': 0.95},
        )
    for node, label in nodes.items():
        ax.text(
            *positions[node], label, ha='center', va='center', color='#0f172a',
            bbox={'boxstyle': 'round,pad=0.7', 'facecolor': '#eff6ff', 'edgecolor': '#93c5fd'},
        )
    ax.set(xlim=(-1.6, 1.6), ylim=(-1.4, 1.5), title=title)
    ax.axis('off')
    _display_figure(fig, output_path)


def start_system_session(dataset):
    """Native guarded full-system session; no concurrent notebooks/CLIs."""
    session = NotebookSession.start(dataset, driver_memory="5g")
    session.spark.conf.set("spark.sql.shuffle.partitions", "64")
    return session


def system_protocol_table(run):
    tx = run.table("transactions")
    phase = F.lit(len(run.record["snapshot_cutoffs"]))
    for index, cutoff in reversed(list(enumerate(run.record["snapshot_cutoffs"]))):
        phase = F.when(F.col("step") <= cutoff, index).otherwise(phase)
    table = tx.withColumn("time_block", phase).groupBy("time_block").agg(F.count("*").alias("transactions"),
        F.sum("isFraud").alias("positives"), F.min("step").alias("first_step"), F.max("step").alias("last_step")).orderBy("time_block").toPandas()
    table["positive_rate"] = table.positives/table.transactions
    if run.dataset == "ibm_aml":
        for side in ("first", "last"):
            table[side+"_time_UTC"] = pd.to_datetime(table[side+"_step"], unit="s", utc=True).astype(str)
    return table


def _save_system_figure(run, name, figure):
    directory = run.output_dir / "figures"
    directory.mkdir(exist_ok=True)
    _display_figure(figure, directory / (name+".png"))


def plot_system_centrality(run):
    """Aggregate/full counts; only the top ten accounts enter pandas."""
    distribution = pd.read_csv(run.output_dir / "degree_distribution.csv")
    positive = distribution[distribution.degree > 0]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.scatter(positive.degree, positive.account_count, s=14)
    ax.set(xscale="log", yscale="log", xlabel="Transaction degree", ylabel="Accounts", title=f"{run.dataset}: full degree distribution (positive degrees on log axes)")
    _save_system_figure(run, "full_degree", fig)
    top = pd.read_csv(run.output_dir / "top10_pagerank.csv").sort_values("pagerank")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.barh(top.id.astype(str), top.pagerank, color="#2563eb")
    ax.set(xlabel="PageRank (sum over all accounts = N)", title="Full-data top 10 structural hubs; not fraud predictions")
    _save_system_figure(run, "full_pagerank", fig)
    return top.sort_values("pagerank", ascending=False)


def plot_system_communities(run):
    distribution = pd.read_csv(run.output_dir / "community_size_distribution.csv")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.scatter(distribution.member_count, distribution["count"], s=16, color="#0f766e")
    ax.set(xscale="log", yscale="log", xlabel="Members per community", ylabel="Communities", title=f"{run.dataset}: all full-data LPA communities")
    _save_system_figure(run, "full_communities", fig)
    return pd.read_csv(run.output_dir / "community_top50.csv").head(10)


def plot_system_validation(run):
    folds = pd.read_csv(run.output_dir / "walk_forward.csv")
    import json
    rules = json.loads((run.output_dir / "frozen_rules.json").read_text())
    fig, ax = plt.subplots(figsize=(10, 4))
    for name, rule in rules["family_rules"].items():
        rows = folds[(folds.family == name) & np.isclose(folds.threshold, rule["threshold"])]
        ax.plot(rows.fold, rows.F1, marker="o", label=name)
    ax.set(xlabel="Expanding validation fold", ylabel="F1 at frozen family threshold", title="Common full-data walk-forward benchmark", xticks=[1, 2, 3])
    ax.legend(fontsize=7, ncols=2)
    _save_system_figure(run, "validation", fig)
    return pd.DataFrame(rules["family_rules"]).T[["threshold", "mean_F1", "worst_F1", "FP"]]


def plot_system_results(run):
    table = pd.read_csv(run.output_dir / "test_metrics.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    table.set_index("model")[["precision", "recall", "F1", "average_precision"]].plot.bar(ax=axes[0], rot=75)
    axes[0].set(title="Factorial ablations + novelty control: same test", ylabel="Score", ylim=(0, 1))
    focus = list(dict.fromkeys(["transaction_only", "motif_assisted", "full_fusion", *table.loc[table.selected_on_validation, "model"]]))
    for family in focus:
        curve = pd.read_csv(run.output_dir / ("pr_curve_"+family+".csv"))
        axes[1].step(curve.recall, curve.precision, where="pre", label=family)
    axes[1].axhline(table.prevalence.iloc[0], color="#64748b", linestyle="--", label="prevalence")
    axes[1].set(xlabel="Recall", ylabel="Precision", title="Exact PR curves, score ties grouped", xlim=(0, 1), ylim=(0, 1))
    axes[1].legend(fontsize=7)
    _save_system_figure(run, "ablation_and_pr", fig)
    budgets = pd.read_csv(run.output_dir / "review_budgets.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for family in focus:
        rows = budgets[budgets.model==family].sort_values("K")
        axes[0].plot(rows.K, rows.precision_at_K, marker="o", label=family)
        axes[1].plot(rows.K, rows.recall_at_K, marker="o", label=family)
    axes[0].set(xlabel="Exactly K reviewed transactions", ylabel="Precision@K", title="Review efficiency")
    axes[1].set(xlabel="Exactly K reviewed transactions", ylabel="Recall@K", title="Coverage at the same review budget")
    axes[1].legend(fontsize=7)
    _save_system_figure(run, "review_budgets", fig)
    selected = table[table.selected_on_validation]
    if not selected.empty:
        row = selected.iloc[0]
        matrix = np.array([[row.TN, row.FP], [row.FN, row.TP]], dtype=int)
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.imshow(matrix, cmap="Blues")
        for (i, j), value in np.ndenumerate(matrix):
            ax.text(j, i, f"{value:,}", ha="center", va="center")
        ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["no alert", "alert"], yticklabels=["negative", "positive"],
               xlabel="Frozen model prediction", ylabel="Ground truth", title=f"Validation selected: {row.model}")
        _save_system_figure(run, "confusion", fig)
    return table


def system_case_evidence(run):
    """Audit one real alert with a genuine motif witness, never invent a path."""
    import json
    from src.motif.features import resolve_star_witness
    from src.motif.config import DATASETS
    rules = json.loads((run.output_dir / "frozen_rules.json").read_text())
    family = rules["selection"]["family"]
    if family == "abstain":
        return pd.DataFrame([{"result": "ABSTAIN: no selected alert to illustrate"}])
    prediction = run.spark.read.parquet(str(run.output_dir / "predictions" / (family+".parquet")))
    features = run.table("features")
    window = max(run.config.analysis.windows_hours)
    candidates = prediction.where("alert AND isFraud=1").join(features, "event_id")
    row = candidates.orderBy(F.desc("cycle3_count"), F.desc(f"relay_{window}h"), F.desc("risk_score"), "event_key").first()
    if row is None:
        return pd.DataFrame([{"result": "Selected model has no test true positive; inspect exported FP/FN examples"}])
    event_ids = [row.event_id]
    kind = "transaction only; no eligible motif witness"
    if row.cycle3_count > 0 and row.cycle3_witness is not None:
        event_ids += [row.cycle3_witness.first_event_id, row.cycle3_witness.second_event_id]
        kind = "chronological 3-cycle witness"
    else:
        for candidate in ("relay", "fanin", "fanout"):
            if row[f"{candidate}_{window}h"] > 0:
                witnesses = resolve_star_witness(run.table("motif_features"), row.event_id, DATASETS[run.dataset], candidate, window)
                example = witnesses.orderBy(F.desc("step"), "event_id").first()
                if example is not None:
                    event_ids.append(example.event_id)
                    kind = candidate+" strict-past witness"
                    break
    evidence = run.table("transactions").where(F.col("event_id").isin(event_ids)).select(
        "event_id", "src", "dst", "step", "type", "amount", "payment_currency", "isFraud").orderBy("step").toPandas()
    evidence["example_model"] = family
    evidence["evidence_kind"] = kind
    evidence.to_csv(run.output_dir / "selected_case_evidence.csv", index=False, encoding="utf-8-sig")
    if len(evidence)>1:
        nodes = set(evidence.src) | set(evidence.dst)
        draw_graph({str(v): str(v) for v in nodes}, [(str(r.src), str(r.dst), f"{r.amount:g} {r.payment_currency}\nt={r.step}; truth={int(r.isFraud)}") for r in evidence.itertuples()],
                   title=f"Real {kind}; labels shown only for audit",
                   output_path=run.output_dir / "figures" / "selected_case.png")
    return evidence

def system_phase_table(run, phase):
    """Compact presentation of a measured phase, retaining detailed manifests."""
    record = run.record["phases"][phase]
    names = ["status", "elapsed_seconds", "average_job_cpu_percent"]
    rows = [{"check": name, "value": record.get(name)} for name in names]
    rows += [{"check": name, "value": value} for name, value in record.items()
             if name in ("accounts", "rows", "unique_ids", "future_snapshot_rows", "degree_sum",
                         "rank_sum", "communities", "internal_edges", "cross_edges", "positives",
                         "test_transactions", "test_positives", "full_test_model_reload")]
    rows += [{"check": name, "value": record["hardware"].get(name)} for name in
             ("peak_job_commit_gib", "minimum_available_ram_gib")]
    return pd.DataFrame(rows)


def plot_system_motif_coverage(run):
    table = pd.read_csv(run.output_dir / "motif_coverage.csv")
    view = table[table.scope == "test"].copy()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    axes[0].barh(view.motif, view.positive_coverage.fillna(0), color="#2563eb")
    axes[0].set(xlabel="Fraction of test positives covered", title="Structural coverage; overlapping motifs", xlim=(0, 1))
    axes[1].barh(view.motif, view.positive_fraction_when_present.fillna(0), color="#0f766e")
    axes[1].axvline(view.population_prevalence.iloc[0], linestyle="--", color="#dc2626", label="Test prevalence")
    axes[1].set(xlabel="Positive fraction among covered transactions", title="Posthoc label audit; no prediction rule")
    axes[1].legend()
    _save_system_figure(run, "motif_coverage", fig)
    return view[["motif", "covered_transactions", "covered_positives", "positive_coverage", "positive_fraction_when_present"]]


def plot_system_timeline(run):
    cuts = run.record["snapshot_cutoffs"]
    fig, ax = plt.subplots(figsize=(11, 3), layout="constrained")
    colors = ["#64748b", "#2563eb", "#0f766e", "#eab308", "#ef4444"]
    start = run.record["support"]["first_step"]
    end = run.record["support"]["last_step"]
    for index, (left, right) in enumerate(zip([start, *cuts], [*cuts, end])):
        ax.axvspan(left, right, color=colors[min(index,4)], alpha=.18)
    for cutoff in cuts:
        ax.axvline(cutoff, color="#64748b", linestyle="--", linewidth=.8)
    for index, (left, right) in enumerate(zip(cuts[1:-1], cuts[2:]),1):
        ax.plot([left,right],[index,index],linewidth=8,color="#2563eb")
        ax.text((left+right)/2,index+.15,f"Validation {index}",ha="center")
    ax.plot([cuts[-1],end],[0,0],linewidth=8,color="#dc2626")
    ax.text((cuts[-1]+end)/2,.2,"Frozen test",ha="center")
    ax.set(xlabel="Unix timestamp (seconds)" if run.dataset=="ibm_aml" else "Simulation hour",
           yticks=[], ylim=(-.4,3.6), title="Expanding-prefix validation; snapshot strictly before each decision")
    _save_system_figure(run,"temporal_protocol",fig)
    return system_protocol_table(run)


def plot_system_reliability(run):
    table = pd.read_csv(run.output_dir / "test_temporal_stability.csv")
    selected = run.record["selected_test_metrics"]["model"]
    focus = list(dict.fromkeys(["transaction_only", "motif_assisted", selected]))
    fig, axes = plt.subplots(1, 2, figsize=(12,4),layout="constrained")
    for family in focus:
        rows = table[table.model==family].sort_values("test_period")
        axes[0].plot(rows.test_period+1,rows.F1,marker="o",label=family)
        axes[1].plot(rows.test_period+1,rows.average_precision,marker="o",label=family)
    for ax, name in zip(axes,("F1", "Average precision")):
        ax.set(xlabel="Chronological test period",ylabel=name,xticks=sorted(table.test_period.unique()+1),
               title=f"Frozen rules: temporal {name}",ylim=(0,None))
        ax.legend(fontsize=8)
    _save_system_figure(run,"temporal_stability",fig)
    delta = pd.read_csv(run.output_dir/"graph_contributions.csv")
    fig, ax = plt.subplots(figsize=(10,4),layout="constrained")
    delta.set_index("contrast")[["delta_F1","delta_average_precision"]].plot.barh(ax=ax)
    ax.axvline(0,color="#334155",linewidth=.8)
    ax.set(xlabel="Absolute difference on the same test",title="Graph contributions: positive and negative findings")
    _save_system_figure(run,"graph_contributions",fig)
    importance = pd.read_csv(run.output_dir/"feature_importance.csv")
    importance = importance[importance.family==selected].sort_values("importance",ascending=False)
    if not importance.empty:
        fig, ax = plt.subplots(figsize=(10,4),layout="constrained")
        top = importance.head(12).sort_values("importance")
        ax.barh(top.feature,top.importance,color="#2563eb")
        ax.set(xlabel="Tree impurity importance (not causal attribution)",title=f"Actually used features: {selected}")
        _save_system_figure(run,"selected_importance",fig)
    return table[table.model==selected][["test_period","transactions","fraud","TP","FP","FN","precision","recall","F1","average_precision"]].rename(columns={"test_period":"period_zero_based"})


def system_execution_benchmark(run):
    """Separate algorithm cost, job CPU and host memory from predictive quality."""
    rows = []
    for name, values in run.record["phases"].items():
        elapsed = values["elapsed_seconds"]
        rows.append({"phase":name,"seconds":elapsed,"job_CPU_percent":values.get("average_job_cpu_percent"),
            "peak_commit_GiB":values["hardware"].get("peak_job_commit_gib"),
            "minimum_host_free_GiB":values["hardware"].get("minimum_available_ram_gib")})
    return pd.DataFrame(rows)


def write_designs_explanation(root=REPO_ROOT):
    """Write the requested speaker notes only from two completed verified runs."""
    from src.common.project_audit import verify_full_system_notebook, notebook_tables
    notes = ["# Hướng dẫn thuyết trình hai notebook full-system", "",
             "Tài liệu được tạo sau khi cả hai notebook có output thực thi hoàn chỉnh. Số liệu dưới đây gắn với run ID; không lấy kết quả IBM thay PaySim.", "",
             "## Cách trình bày", "",
             "Đi theo Raw → integrity/index → full analytics → historical features → fusion → validation → frozen test → evidence/reliability. Mỗi mục giải thích mục tiêu, code tính toán, output và giới hạn kết luận.", "",
             "Code kernel được chép đầy đủ vào notebook, kiểm tra AST khớp module Python trước execution và truyền trực tiếp vào pipeline. Các helper I/O/checkpoint/guard tiếp tục import từ module gốc.", ""]
    for dataset, filename in (("ibm_aml","IBM_full_system.ipynb"),("paysim","PaySIM_full_system.ipynb")):
        path = root/"notebooks"/filename
        notebook = json.loads(path.read_text(encoding="utf-8"))
        latest = json.loads((root/"results/full_system"/dataset/"latest.json").read_text(encoding="utf-8"))
        directory = Path(latest["directory"])
        verified = verify_full_system_notebook(path,directory,root)
        report = json.loads((directory/"report.json").read_text(encoding="utf-8"))
        selected = report["selected_test_metrics"]
        baseline = next(row for row in report["test_metrics"] if row["model"]=="transaction_only")
        notes += [f"## {filename}", "",f"- Run: `{directory.name}`; {verified['cells']} code cells, {verified['figures']} figures, {verified['source_copies']} definitions khớp Python.",
            f"- Full input: {report['support']['n']:,} giao dịch; {report['integrity']['num_vertices']:,} accounts; {int(report['support']['positives']):,} nhãn dương.",
            f"- Selected: `{selected['model']}`, threshold={selected['threshold']}; TP={selected['TP']:,}, FP={selected['FP']:,}, FN={selected['FN']:,}, TN={selected['TN']:,}.",
            f"- Precision={selected['precision']:.2%}; recall={selected['recall']:.2%}; F1={selected['F1']:.2%}; AP={selected['average_precision']:.2%}.",
            f"- Transaction-only: F1={baseline['F1']:.2%}, AP={baseline['average_precision']:.2%}. Chênh lệch selected: ΔF1={selected['F1']-baseline['F1']:+.4f}; ΔAP={selected['average_precision']-baseline['average_precision']:+.4f}.", "",
            "Các số liệu này là kết quả nội bộ theo thời gian trên dữ liệu tổng hợp. IBM target là laundering; PaySim target là fraud. Score cây có class weights không phải xác suất đã calibrated.", ""]
        for number,cell in enumerate((c for c in notebook["cells"] if c["cell_type"]=="code"),1):
            info = cell.get("metadata",{}).get("graphguard_presentation",{})
            source = "".join(cell["source"])
            imports = [line for line in source.splitlines() if line.startswith("from ")]
            copies = [x for x in notebook["metadata"].get("graphguard_source_copies",[]) if x["cell_id"]==cell["id"]]
            outputs = cell.get("outputs",[])
            images = sum("image/png" in output.get("data",{}) for output in outputs)
            tables = list(notebook_tables({"cells":[cell]}))
            notes += [f"### Cell {number:02d} — {info.get('title',cell['id'])}", "",
                "**Vai trò:** "+info.get("purpose","Thực hiện bước được ghi ngay trên cell trong notebook."), "",
                "**Code cần giải thích:** "+info.get("code_reading","Đọc các phép biến đổi và assertions; helper chi tiết được dẫn bằng from-import."), ""]
            if copies:
                notes += ["**Khớp Python:** "+"; ".join(f"`{x['name']}` → [{x['path']}](./{x['path']})" for x in copies)+".", ""]
            if imports:
                notes += ["**Imports:** "+"; ".join("`"+line+"`" for line in imports)+".", ""]
            notes += [f"**Output đã chạy:** execution_count={cell['execution_count']}; {len(tables)} bảng, {images} hình.", ""]
            if tables:
                rows = tables[0][:4]
                keys = list(rows[0])[:7] if rows else []
                if keys:
                    notes += ["| "+" | ".join(keys)+" |", "| "+" | ".join("---" for _ in keys)+" |"]
                    notes += ["| "+" | ".join(str(row.get(key,"")).replace("|","/") for key in keys)+" |" for row in rows]
                    notes += [""]
            else:
                streams = []
                for output in outputs:
                    text = output.get("text","")
                    text = "".join(text) if isinstance(text,list) else text
                    streams += [line for line in text.splitlines() if line and not line.startswith("[SYSTEM]")]
                if streams:
                    notes += ["```text", "\n".join(streams)[-700:], "```", ""]
            notes += ["**Cách đọc trước thầy:** "+info.get("readout","Đối chiếu mục tiêu của bước với bảng/hình thực tế; không suy luận vượt quá phép kiểm tra đã chạy."), ""]
    notes += ["## Reliability: được kiểm chứng tới đâu?", "",
        "- Coverage và chronology: đủ physical rows, không trùng event ID, snapshot luôn quá khứ.",
        "- Predictive stability: 3 validation folds, mean/worst/std F1; 5 khoảng test liên tiếp với rule đã khóa, không chọn lại trên test.",
        "- Uncertainty: khoảng Wilson 95% cho precision/recall mang giả định nhị thức theo dòng, chưa điều chỉnh account/time correlation.",
        "- Reproducibility: model reload replay toàn test; artifact/source/input hashes và metric độc lập từ predictions.",
        "- Runtime: từng phase có thời gian, CPU của job, peak commit và minimum free RAM. CPU 100% là quyền sử dụng, không khẳng định mọi bước I/O/serial đều đạt 100%.",
        "- Ablation và feature importance được báo cả khi đóng góp bằng 0 hoặc âm. Một witness graph không chứng minh model dự đoán nhờ motif đó.",
        "- Chưa có untouched external holdout hoặc kiểm chứng thực địa. Software PASS không phải chứng nhận phát hiện AML chính xác ngoài dữ liệu này.", ""]
    target = root/"designs_Explain.md"
    target.write_text("\n".join(notes)+"\n",encoding="utf-8")
    return target
