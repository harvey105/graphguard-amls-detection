"""Notebook views only; algorithms and experiment control live in Python modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.metadata as metadata
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
            extra_configs={"spark.master": "local[2]", "spark.default.parallelism": "2",
                "spark.ui.enabled": "false", "spark.ui.showConsoleProgress": "false",
                "spark.sql.session.timeZone": "UTC",
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


def baseline_audit(spark, dataset: str, input_dir: Path | None = None) -> BaselineAudit:
    """Execute original coursework queries, without overwriting baseline CSVs."""
    from src.ibm_aml.motif_finding import directed_account_cycles, find_usd_cycles
    from src.motif.toy_cycle import find_three_node_cycles
    from src.paysim.motif_finding import find_relays, relay_rows

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


def draw_graph(nodes, edges, title, positions=None, colors=None):
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
    plt.show()
