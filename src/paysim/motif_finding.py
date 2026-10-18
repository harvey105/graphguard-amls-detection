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
            sources=[Path(__file__), REPO_ROOT / "src/motif/toy_cycle.py",
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
