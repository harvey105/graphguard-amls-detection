r"""Task 3 IBM AML HI-Small: directed three-account cycles on GraphFrames.

Run from the repository root in Windows PowerShell:
    & .\.venv\Scripts\python.exe -m src.ibm_aml.motif_finding
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


def directed_account_cycles(matches: DataFrame) -> DataFrame:
    """Keep one rotation per directed account cycle, retaining edge multiplicity."""
    return matches.where(
        (F.col("a.id") < F.col("b.id")) & (F.col("a.id") < F.col("c.id"))
    ).select(
        F.col("a.id").alias("a"),
        F.col("b.id").alias("b"),
        F.col("c.id").alias("c"),
    ).groupBy("a", "b", "c").agg(
        F.count("*").alias("transaction_combinations")
    )


def find_usd_cycles(graph: GraphFrame, minimum_amount: float) -> DataFrame:
    """Find label-blind cycles with all three payments strictly above a USD threshold."""
    if not math.isfinite(minimum_amount) or minimum_amount < 0:
        raise ValueError("minimum USD amount must be finite and >= 0")
    edges = graph.edges.where(
        (F.col("payment_currency") == "US Dollar")
        & (F.col("amount") > minimum_amount)
    )
    return find_three_node_cycles(GraphFrame(graph.vertices, edges))


def find_topological_cycles(vertices: DataFrame, features: DataFrame) -> DataFrame:
    """Enumerate directed account triples once, without labels or amounts.

    Collapsing parallel edges *before* motif matching avoids multiplying every
    historical transaction combination during the topology discovery stage.
    """
    require_unlabelled(features)
    topology = features.where(F.col("src") != F.col("dst")).select("src", "dst").distinct()
    matches = find_three_node_cycles(GraphFrame(vertices.select("id"), topology))
    return matches.where(
        (F.col("a.id") < F.col("b.id")) & (F.col("a.id") < F.col("c.id"))
    ).selectExpr("a.id a", "b.id b", "c.id c")


def build_temporal_cycle_features(topology: DataFrame, features: DataFrame) -> DataFrame:
    """All three rotations, but only strictly chronological same-currency cycles.

    The last edge is the decision event; the other two are already observable.
    No currency conversion is inferred. FX edges and equal timestamps are
    excluded explicitly. Each returned row is evidence, not an independent TP.
    """
    require_unlabelled(features)
    edges = features.where(
        (F.col("src") != F.col("dst")) & (F.col("amount") > 0)
        & (F.col("payment_currency") == F.col("receiving_currency"))
    ).select("event_id", "src", "dst", "step", "amount", "payment_currency")
    result = None
    for rotation in range(3):
        names = ["a", "b", "c"]
        order = names[rotation:] + names[:rotation]
        query = topology.select(*(F.col(old).alias(new) for old, new in zip(order, names)))
        query = query.join(edges.alias("x"), (F.col("a") == F.col("x.src")) & (F.col("b") == F.col("x.dst")))
        query = query.join(edges.alias("y"),
            (F.col("b") == F.col("y.src")) & (F.col("c") == F.col("y.dst"))
            & (F.col("x.payment_currency") == F.col("y.payment_currency"))
            & (F.col("x.step") < F.col("y.step")))
        query = query.join(edges.alias("z"),
            (F.col("c") == F.col("z.src")) & (F.col("a") == F.col("z.dst"))
            & (F.col("x.payment_currency") == F.col("z.payment_currency"))
            & (F.col("y.step") < F.col("z.step")))
        flat = query.select(
            "a", "b", "c", F.col("z.event_id").alias("event_id"),
            F.col("x.event_id").alias("first_event_id"), F.col("y.event_id").alias("second_event_id"),
            F.col("x.step").alias("first_step"), F.col("y.step").alias("second_step"),
            F.col("z.step").alias("step"), F.col("x.payment_currency").alias("payment_currency"),
            F.col("x.amount").alias("first_amount"), F.col("y.amount").alias("second_amount"),
            F.col("z.amount").alias("amount"),
            (F.col("z.step") - F.col("x.step")).alias("gap_seconds"),
            F.least("x.amount", "y.amount", "z.amount").alias("minimum_cycle_amount"),
            (F.least("x.amount", "y.amount", "z.amount") / F.greatest(
                "x.amount", "y.amount", "z.amount")).alias("amount_ratio"),
        )
        result = flat if result is None else result.unionByName(flat)
    return result


def cycle_training_thresholds(features: DataFrame, train_end: int) -> DataFrame:
    """Per-currency training quantiles, without comparing nominal currency units."""
    require_unlabelled(features)
    return features.where((F.col("step") <= train_end) & (F.col("amount") > 0)).groupBy(
        "payment_currency"
    ).agg(F.percentile_approx("amount", [0.5, 0.9], 10_000).alias("_quantiles"),
          F.count("*").alias("training_transactions")).select(
        "payment_currency", "training_transactions",
        F.col("_quantiles")[0].alias("q50_amount"), F.col("_quantiles")[1].alias("q90_amount"),
    )


def temporal_cycle_alerts(candidates: DataFrame, rule: dict) -> DataFrame:
    """Return evidence rows; callers deduplicate event_id before counting alerts."""
    require_unlabelled(candidates)
    if rule["rule_id"] == "abstain":
        return candidates.where(F.lit(False))
    quantile = float(rule["quantile"])
    floor = F.lit(0.0) if quantile == 0 else F.col("q50_amount" if quantile == 0.5 else "q90_amount")
    return candidates.where(
        (F.col("gap_seconds") <= float(rule["window_hours"]) * 3600)
        & (F.col("amount_ratio") >= float(rule["minimum_ratio"]))
        & (F.col("minimum_cycle_amount") > floor)
    )


def score_cycle_validation(candidates: DataFrame, truth: DataFrame):
    """Fixed 72-rule grid; score unique closing transactions on validation only."""
    import pandas as pd

    require_unlabelled(candidates)
    validation = truth.where(F.col("split") == "validation")
    support = validation.agg(F.count("*").alias("n"), F.sum("isFraud").alias("p")).first()
    if not support.n:
        raise ValueError("Empty validation split")
    evidence = candidates.where(F.col("split") == "validation").join(
        validation.select("event_id", "isFraud"), "event_id"
    ).toPandas()
    records = []
    for hours in (1, 6, 24, 72, 168, 504):
        for ratio in (0.0, 0.5, 0.8, 0.95):
            for quantile in (0.0, 0.5, 0.9):
                floor = 0.0 if quantile == 0 else evidence["q50_amount" if quantile == 0.5 else "q90_amount"]
                mask = (evidence.gap_seconds <= hours * 3600) & (evidence.amount_ratio >= ratio) & (
                    evidence.minimum_cycle_amount > floor
                )
                selected = evidence.loc[mask].drop_duplicates("event_id")
                tp, n = int(selected.isFraud.sum()), len(selected)
                records.append({
                    "rule_id": f"cycle_h{hours:03d}_r{ratio:.2f}_q{quantile:.1f}",
                    "window_hours": hours, "minimum_ratio": ratio, "quantile": quantile,
                    **binary_metrics(support.n, support.p, tp, n - tp),
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
    minimum_usd_amount: float = 10_000.0,
    max_csv_rows: int = 5_000,
    input_dir: Path | None = None,
) -> dict:
    if not math.isfinite(minimum_usd_amount) or minimum_usd_amount < 0 or max_csv_rows <= 0:
        raise ValueError("finite minimum_usd_amount >= 0 and max_csv_rows > 0 required")
    source = (input_dir or Path("data/processed/sample/ibm_aml" if sample else "data/processed/ibm_aml")).resolve()
    default_output = "results/ibm_aml/custom" if input_dir else ("results/ibm_aml/sample" if sample else "results/ibm_aml")
    output_dir = (output_dir or Path(default_output)).resolve()
    spark = get_graph_session("GraphGuard-IBM-Task3")
    try:
        loaded = load_graph(spark, str(source))
        # Motif joins retain each named vertex/edge as a struct. Project before
        # caching/joining so unused ETL attributes do not multiply across matches.
        graph = GraphFrame(
            loaded.vertices.select("id"),
            loaded.edges.select("src", "dst", "isFraud", "payment_currency", "amount"),
        )
        graph.vertices.cache()
        graph.edges.cache()
        vertex_count = graph.vertices.count()
        edge_count = graph.edges.count()

        fraud_edges = graph.edges.where(F.col("isFraud") == 1).cache()
        fraud_edge_count = fraud_edges.count()
        fraud_graph = GraphFrame(graph.vertices, fraud_edges)
        fraud_matches = find_three_node_cycles(fraud_graph).cache()
        fraud_raw_rows = fraud_matches.count()
        ordered_triples = fraud_matches.select(
            F.col("a.id").alias("a"), F.col("b.id").alias("b"),
            F.col("c.id").alias("c"),
        ).distinct().count()
        unordered_sets = fraud_matches.select(
            F.array_sort(F.array("a.id", "b.id", "c.id")).alias("accounts")
        ).distinct().count()
        directed = directed_account_cycles(fraud_matches).cache()
        directed_count = directed.count()
        edge_combinations = directed.agg(
            F.sum("transaction_combinations").alias("n")
        ).first()["n"] or 0
        if fraud_raw_rows != 3 * edge_combinations or ordered_triples != 3 * directed_count:
            raise AssertionError("Cycle rotations did not reconcile with directed counts")

        directed_rows = [row.asDict() for row in directed.orderBy(
            F.desc("transaction_combinations"), "a", "b", "c"
        ).limit(max_csv_rows).collect()]
        write_csv(output_dir / "fraud_directed_cycles.csv",
                  ["a", "b", "c", "transaction_combinations"], directed_rows)

        currency_rows = [row.asDict() for row in fraud_edges.groupBy(
            "payment_currency"
        ).agg(F.count("*").alias("fraud_edges")).orderBy(
            F.desc("fraud_edges"), "payment_currency"
        ).collect()]
        write_csv(output_dir / "fraud_currency_counts.csv",
                  ["payment_currency", "fraud_edges"], currency_rows)

        # Separate label-blind query. USD is required because amount is not
        # comparable across currencies; the rule applies to all three edges.
        usd_matches = find_usd_cycles(graph, minimum_usd_amount)
        usd_raw_rows = usd_matches.count()

        summary = {
            "dataset": "IBM AML HI-Small",
            "scope": "custom" if input_dir else ("sample" if sample else "full"),
            "vertices": vertex_count,
            "edges": edge_count,
            "fraud_edges": fraud_edge_count,
            "fraud_cycle_raw_rows": fraud_raw_rows,
            "fraud_ordered_account_triples": ordered_triples,
            "fraud_directed_account_cycles": directed_count,
            "fraud_unordered_account_sets": unordered_sets,
            "fraud_transaction_combinations": edge_combinations,
            "fraud_cycle_csv_rows": len(directed_rows),
            "usd_amount_gt": minimum_usd_amount,
            "usd_cycle_raw_rows": usd_raw_rows,
        }
        write_csv(output_dir / "motif_summary.csv", list(summary), [summary])
        write_run_evidence(
            output_dir / "motif_run.json", spark, task="Task 3 IBM",
            inputs=[source], outputs=[output_dir / name for name in (
                "motif_summary.csv", "fraud_directed_cycles.csv", "fraud_currency_counts.csv")],
            sources=[Path(__file__), REPO_ROOT / "src/motif/toy_cycle.py", REPO_ROOT / "src/motif/evaluation.py",
                     REPO_ROOT / "src/common/spark_session.py", REPO_ROOT / "src/common/graph_utils.py",
                     REPO_ROOT / "src/common/windows_runtime.py", REPO_ROOT / "src/common/run_evidence.py"],
            parameters={"minimum_usd_amount": minimum_usd_amount, "max_csv_rows": max_csv_rows,
                        "label_audit": "isFraud=1; not a label-blind detector evaluation"},
            metrics=summary,
        )
        print(f"[PASS] IBM {summary['scope']}: {summary}")
        return summary
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Use the sample graph")
    parser.add_argument("--input-dir", type=Path, help="Custom graph Parquet directory")
    parser.add_argument("--output-dir", type=Path,
                        help="CSV directory; defaults to results/ibm_aml[/sample]")
    parser.add_argument("--minimum-usd-amount", type=float, default=10_000.0)
    parser.add_argument("--max-csv-rows", type=int, default=5_000)
    args = parser.parse_args()
    if args.sample and args.input_dir:
        parser.error("Choose --sample or --input-dir")
    run(args.sample, args.output_dir, args.minimum_usd_amount, args.max_csv_rows, args.input_dir)


if __name__ == "__main__":
    main()
