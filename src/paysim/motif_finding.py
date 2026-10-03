r"""Task 3 PaySim: 3-cycle audit and TRANSFER -> CASH_OUT relays.

Run from the repository root in Windows PowerShell:
    & .\.venv\Scripts\python.exe -m src.paysim.motif_finding
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

RELAY_PATTERN = "(a)-[e1]->(b);(b)-[e2]->(c)"


def find_relays(
    graph: GraphFrame, minimum_amount: float, max_gap_hours: int,
    strict_time: bool = False,
) -> DataFrame:
    """Find three-account relays; same-hour order is unknown in PaySim."""
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
) -> dict:
    if minimum_amount < 0 or max_gap_hours <= 0 or max_csv_rows <= 0:
        raise ValueError("minimum_amount >= 0, max_gap_hours > 0, max_csv_rows > 0 required")
    source = Path("data/processed/sample/paysim" if sample else "data/processed/paysim")
    output_dir = output_dir or Path("results/paysim/sample" if sample else "results/paysim")
    spark = get_graph_session("GraphGuard-PaySim-Task3")
    try:
        graph = load_graph(spark, str(source))
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
            "scope": "sample" if sample else "full",
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
        print(f"[PASS] PaySim {summary['scope']}: {summary}")
        return summary
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Use the sample graph")
    parser.add_argument("--output-dir", type=Path,
                        help="CSV directory; defaults to results/paysim[/sample]")
    parser.add_argument("--minimum-amount", type=float, default=10_000.0)
    parser.add_argument("--max-gap-hours", type=int, default=24)
    parser.add_argument("--max-csv-rows", type=int, default=1_000)
    parser.add_argument("--strict-time", action="store_true",
                        help="Exclude same-hour pairs whose internal order is unknown")
    args = parser.parse_args()
    run(args.sample, args.output_dir, args.minimum_amount, args.max_gap_hours,
        args.max_csv_rows, args.strict_time)


if __name__ == "__main__":
    main()
