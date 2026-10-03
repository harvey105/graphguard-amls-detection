r"""Task 3 IBM AML HI-Small: directed three-account cycles on GraphFrames.

Run from the repository root in Windows PowerShell:
    & .\.venv\Scripts\python.exe -m src.ibm_aml.motif_finding
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from graphframes import GraphFrame
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.common.graph_utils import load_graph
from src.common.spark_session import get_graph_session
from src.motif.toy_cycle import find_three_node_cycles


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
) -> dict:
    if minimum_usd_amount < 0 or max_csv_rows <= 0:
        raise ValueError("minimum_usd_amount >= 0 and max_csv_rows > 0 required")
    source = Path("data/processed/sample/ibm_aml" if sample else "data/processed/ibm_aml")
    output_dir = output_dir or Path("results/ibm_aml/sample" if sample else "results/ibm_aml")
    spark = get_graph_session("GraphGuard-IBM-Task3")
    try:
        graph = load_graph(spark, str(source))
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
        usd_edges = graph.edges.where(
            (F.col("payment_currency") == "US Dollar")
            & (F.col("amount") > minimum_usd_amount)
        )
        usd_matches = find_three_node_cycles(GraphFrame(graph.vertices, usd_edges))
        usd_raw_rows = usd_matches.count()

        summary = {
            "dataset": "IBM AML HI-Small",
            "scope": "sample" if sample else "full",
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
        print(f"[PASS] IBM {summary['scope']}: {summary}")
        return summary
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Use the sample graph")
    parser.add_argument("--output-dir", type=Path,
                        help="CSV directory; defaults to results/ibm_aml[/sample]")
    parser.add_argument("--minimum-usd-amount", type=float, default=10_000.0)
    parser.add_argument("--max-csv-rows", type=int, default=5_000)
    args = parser.parse_args()
    run(args.sample, args.output_dir, args.minimum_usd_amount, args.max_csv_rows)


if __name__ == "__main__":
    main()
