r"""Task 3 PaySim: 3-cycle audit and TRANSFER -> CASH_OUT relays.

Run from the repository root in Windows PowerShell:
    & .\.venv\Scripts\python.exe -m src.paysim.motif_finding
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from graphframes import GraphFrame
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.common.graph_utils import load_graph
from src.common.run_evidence import REPO_ROOT, write_run_evidence
from src.common.spark_session import get_graph_session
from src.motif.toy_cycle import find_three_node_cycles
from src.motif.evaluation import binary_metrics, require_unlabelled

RELAY_PATTERN = "(a)-[e1]->(b);(b)-[e2]->(c)"


def find_relays(
    graph: GraphFrame, minimum_amount: float, max_gap_hours: int,
    strict_time: bool = False,
) -> DataFrame:
    """Find three-account relays; same-hour order is unknown in PaySim."""
    if not math.isfinite(minimum_amount) or minimum_amount < 0 or max_gap_hours <= 0:
        raise ValueError("finite minimum_amount >= 0 and max_gap_hours > 0 required")
    eligible_edges = graph.edges.where(
        F.col("type").isin("TRANSFER", "CASH_OUT")
        & (F.col("amount") > minimum_amount)
    )
    eligible_graph = GraphFrame(graph.vertices, eligible_edges)
    time_order = (F.col("e1.step") < F.col("e2.step")) if strict_time else (
        F.col("e1.step") <= F.col("e2.step")
    )
    return eligible_graph.find(RELAY_PATTERN).where(
        (F.col("e1.type") == "TRANSFER")
        & (F.col("e2.type") == "CASH_OUT")
        & (F.col("a.id") != F.col("b.id"))
        & (F.col("b.id") != F.col("c.id"))
        & (F.col("a.id") != F.col("c.id"))
        & time_order
        & ((F.col("e2.step") - F.col("e1.step")) <= max_gap_hours)
    )


def relay_rows(matches: DataFrame) -> DataFrame:
    """Flat columns for a CSV of transaction-pair candidates."""
    return matches.select(
        F.col("a.id").alias("source_account"),
        F.col("b.id").alias("middle_account"),
        F.col("c.id").alias("cashout_account"),
        F.col("e1.step").alias("transfer_step"),
        F.col("e2.step").alias("cashout_step"),
        F.col("e1.amount").alias("transfer_amount"),
        F.col("e2.amount").alias("cashout_amount"),
        F.col("e1.isFraud").alias("transfer_isFraud"),
        F.col("e2.isFraud").alias("cashout_isFraud"),
    )


def build_fanin_features(
    features: DataFrame, windows: tuple[int, ...] = (1, 6, 24, 72),
) -> DataFrame:
    """Causal CASH_OUT fan-in A -> B <- C with two different senders.

    Each current transaction is the decision event. Only earlier *hours* may
    supply a witness; within-hour order is unknown. A range window computes
    motif existence without enumerating the quadratic number of edge pairs.
    prior_count is transaction volume, not a count of distinct people.
    """
    from pyspark.sql.window import Window

    require_unlabelled(features)
    if not windows or any(isinstance(h, bool) or not isinstance(h, int) or h <= 0 for h in windows):
        raise ValueError("windows must contain positive integer hours")
    result = features.where((F.col("type") == "CASH_OUT") & (F.col("src") != F.col("dst")))
    for hours in windows:
        history = Window.partitionBy("dst").orderBy("step").rangeBetween(-hours, -1)
        # min/max by source guarantees a different-source witness if one exists.
        record = F.struct("src", "step", "amount", "event_id")
        result = result.withColumn("_first", F.min(record).over(history)).withColumn(
            "_last", F.max(record).over(history)
        ).withColumn(f"prior_count_{hours}", F.count("*").over(history))
        witness = F.when(F.col("_first.src") != F.col("src"), F.col("_first")).when(
            F.col("_last.src") != F.col("src"), F.col("_last")
        )
        result = result.withColumn(f"witness_{hours}", witness).drop("_first", "_last")
    return result


def fanin_training_thresholds(features: DataFrame, train_end: int) -> list[dict]:
    """Amount scale is learned only from unlabelled training CASH_OUT rows."""
    require_unlabelled(features)
    quantiles = [0.9, 0.95, 0.99, 0.995, 0.999]
    amounts = features.where(
        (F.col("step") <= train_end) & (F.col("type") == "CASH_OUT") & (F.col("amount") > 0)
    ).approxQuantile("amount", quantiles, 0.0001)
    if len(amounts) != len(quantiles):
        raise ValueError("No training CASH_OUT amount distribution")
    return [{"quantile": q, "minimum_amount": float(a)}
            for q, a in zip([0.0, *quantiles], [0.0, *amounts])]


def fanin_alerts(fan: DataFrame, rule: dict) -> DataFrame:
    """Label-blind decision predicate, also used after freezing the rule."""
    require_unlabelled(fan)
    if rule["rule_id"] == "abstain":
        return fan.where(F.lit(False))
    predicate = F.col("amount") > float(rule["minimum_amount"])
    if rule["family"] == "fanin":
        hours = int(rule["window_hours"])
        predicate = predicate & F.col(f"witness_{hours}").isNotNull() & (
            F.col(f"prior_count_{hours}") >= int(rule["minimum_priors"])
        )
    return fan.where(predicate)


def score_fanin_validation(
    fan: DataFrame, truth: DataFrame, thresholds: list[dict],
    windows: tuple[int, ...] = (1, 6, 24, 72),
    minimum_priors: tuple[int, ...] = (1, 2, 5),
):
    """Score a fixed grid from a small histogram of validation rows only.

    Returns separate motif and amount-only families for a structural ablation.
    Test labels are never joined or returned by this function.
    """
    import pandas as pd

    require_unlabelled(fan)
    validation = truth.where(F.col("split") == "validation")
    support = validation.agg(F.count("*").alias("n"), F.sum("isFraud").alias("p")).first()
    if not support.n:
        raise ValueError("Empty validation split")
    labelled = fan.where(F.col("split") == "validation").join(
        validation.select("event_id", "isFraud"), "event_id"
    )
    band = sum((F.when(F.col("amount") > t["minimum_amount"], 1).otherwise(0)
                for t in thresholds), F.lit(0))
    buckets = [F.struct(
        F.lit(h).alias("hours"),
        F.least(F.col(f"prior_count_{h}"), F.lit(max(minimum_priors))).alias("prior_count"),
        F.col(f"witness_{h}").isNotNull().alias("other_source"),
    ) for h in windows]
    histogram = labelled.select(
        "isFraud", band.alias("band"), F.explode(F.array(*buckets)).alias("bucket")
    ).select("isFraud", "band", "bucket.*").groupBy(
        "band", "hours", "prior_count", "other_source"
    ).agg(F.count("*").alias("n"), F.sum("isFraud").alias("p")).toPandas()
    records = []
    for rank, threshold in enumerate(thresholds):
        amount_mask = histogram["band"] >= rank + 1
        for hours in windows:
            for count in minimum_priors:
                mask = amount_mask & (histogram.hours == hours) & histogram.other_source & (
                    histogram.prior_count >= count
                )
                n, p = histogram.loc[mask, ["n", "p"]].sum()
                records.append({
                    "rule_id": f"fanin_h{hours:03d}_n{count}_q{rank}", "family": "fanin",
                    "window_hours": hours, "minimum_priors": count, **threshold,
                    **binary_metrics(support.n, support.p, int(p), int(n - p)),
                })
        # Each current row appears once per window; choose one window for baseline.
        n, p = histogram.loc[amount_mask & (histogram.hours == windows[0]), ["n", "p"]].sum()
        records.append({
            "rule_id": f"amount_q{rank}", "family": "amount_only",
            "window_hours": 0, "minimum_priors": 0, **threshold,
            **binary_metrics(support.n, support.p, int(p), int(n - p)),
        })
    return pd.DataFrame(records)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(
    sample: bool = False,
    output_dir: Path | None = None,
    minimum_amount: float = 10_000.0,
    max_gap_hours: int = 24,
    max_csv_rows: int = 1_000,
    strict_time: bool = False,
    input_dir: Path | None = None,
) -> dict:
    if not math.isfinite(minimum_amount) or minimum_amount < 0 or max_gap_hours <= 0 or max_csv_rows <= 0:
        raise ValueError("finite minimum_amount >= 0, max_gap_hours > 0, max_csv_rows > 0 required")
    source = (input_dir or Path("data/processed/sample/paysim" if sample else "data/processed/paysim")).resolve()
    default_output = "results/paysim/custom" if input_dir else ("results/paysim/sample" if sample else "results/paysim")
    output_dir = (output_dir or Path(default_output)).resolve()
    spark = get_graph_session("GraphGuard-PaySim-Task3")
    try:
        loaded = load_graph(spark, str(source))
        graph = GraphFrame(loaded.vertices.select("id"), loaded.edges.select(
            "src", "dst", "type", "amount", "step", "isFraud"))
        graph.vertices.cache()
        graph.edges.cache()
        vertex_count = graph.vertices.count()
        edge_count = graph.edges.count()

        cycles = find_three_node_cycles(graph)
        cycle_raw_rows = cycles.count()
        cycle_directed_accounts = cycles.where(
            (F.col("a.id") < F.col("b.id")) & (F.col("a.id") < F.col("c.id"))
        ).select("a.id", "b.id", "c.id").distinct().count()

        matches = find_relays(graph, minimum_amount, max_gap_hours, strict_time).cache()
        relay_raw_rows = matches.count()
        same_hour_rows = matches.where(F.col("e1.step") == F.col("e2.step")).count()
        flat = relay_rows(matches)
        columns = flat.columns
        examples = [row.asDict() for row in flat.orderBy(
            "transfer_step", "cashout_step", "source_account", "middle_account",
            "cashout_account", "transfer_amount", "cashout_amount",
        ).limit(max_csv_rows).collect()]

        summary = {
            "dataset": "PaySim",
            "scope": "custom" if input_dir else ("sample" if sample else "full"),
            "vertices": vertex_count,
            "edges": edge_count,
            "cycle_raw_rows": cycle_raw_rows,
            "cycle_directed_account_cycles": cycle_directed_accounts,
            "relay_raw_rows": relay_raw_rows,
            "relay_same_hour_rows": same_hour_rows,
            "relay_strict_later_rows": relay_raw_rows - same_hour_rows,
            "relay_csv_rows": len(examples),
            "relay_amount_gt": minimum_amount,
            "relay_max_gap_hours": max_gap_hours,
            "relay_time_rule": (
                "transfer_step < cashout_step" if strict_time
                else "transfer_step <= cashout_step; same-hour order unknown"
            ),
        }
        write_csv(output_dir / "motif_summary.csv", list(summary), [summary])
        write_csv(output_dir / "relay_candidates.csv", columns, examples)
        write_run_evidence(
            output_dir / "motif_run.json", spark, task="Task 3 PaySim",
            inputs=[source], outputs=[output_dir / name for name in ("motif_summary.csv", "relay_candidates.csv")],
            sources=[Path(__file__), REPO_ROOT / "src/motif/toy_cycle.py", REPO_ROOT / "src/motif/evaluation.py",
                     REPO_ROOT / "src/common/spark_session.py", REPO_ROOT / "src/common/graph_utils.py",
                     REPO_ROOT / "src/common/windows_runtime.py", REPO_ROOT / "src/common/run_evidence.py"],
            parameters={"minimum_amount": minimum_amount, "max_gap_hours": max_gap_hours,
                        "strict_time": strict_time, "max_csv_rows": max_csv_rows}, metrics=summary,
        )
        print(f"[PASS] PaySim {summary['scope']}: {summary}")
        return summary
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Use the sample graph")
    parser.add_argument("--input-dir", type=Path, help="Custom graph Parquet directory")
    parser.add_argument("--output-dir", type=Path,
                        help="CSV directory; defaults to results/paysim[/sample]")
    parser.add_argument("--minimum-amount", type=float, default=10_000.0)
    parser.add_argument("--max-gap-hours", type=int, default=24)
    parser.add_argument("--max-csv-rows", type=int, default=1_000)
    parser.add_argument("--strict-time", action="store_true",
                        help="Exclude same-hour pairs whose internal order is unknown")
    args = parser.parse_args()
    if args.sample and args.input_dir:
        parser.error("Choose --sample or --input-dir")
    run(args.sample, args.output_dir, args.minimum_amount, args.max_gap_hours,
        args.max_csv_rows, args.strict_time, args.input_dir)


if __name__ == "__main__":
    main()
