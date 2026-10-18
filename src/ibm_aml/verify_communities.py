"""Independently reconcile IBM LPA CSV deliverables with their input graph.

This checks assignments and statistics; it does not treat numeric labels as
stable between LPA runs or certify communities as money-laundering rings.
"""

from __future__ import annotations

import argparse
import csv
from functools import reduce
import json
from pathlib import Path

from pyspark.sql import functions as F

from src.common.graph_utils import load_graph
from src.common.run_evidence import REPO_ROOT, verify_run_evidence, write_run_evidence
from src.common.spark_session import get_graph_session


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_table(spark, path: Path, required: list[str]):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream), [])
    require(len(header) == len(set(header)) and set(required).issubset(header),
            f"{path.name}: missing or duplicate columns; required {required}")
    return spark.read.option("header", True).option("mode", "FAILFAST").csv(str(path))


def numeric(frame, names: list[str], integral: bool = True):
    invalid_fields = []
    for name in names:
        parsed = F.col(name).cast("long" if integral else "double")
        invalid = parsed.isNull()
        if integral:
            invalid = invalid | ~F.col(name).rlike(r"^-?[0-9]+$")
        else:
            invalid = invalid | F.isnan(parsed) | (F.abs(parsed) == float("inf"))
        invalid_fields.append(invalid)
    require(frame.where(reduce(lambda a, b: a | b, invalid_fields)).limit(1).count() == 0,
            f"Invalid numeric values in {names}")
    for name in names:
        parsed = F.col(name).cast("long" if integral else "double")
        frame = frame.withColumn(name, parsed)
    return frame


def unique_keys(frame, keys: list[str], name: str):
    require(frame.where(reduce(lambda a, b: a | b,
            [F.col(key).isNull() | (F.trim(F.col(key)) == "") for key in keys])).limit(1).count() == 0,
            f"{name}: null/blank keys")
    require(frame.groupBy(*keys).count().where(F.col("count") != 1).limit(1).count() == 0,
            f"{name}: duplicate keys")


def same_keys(actual, expected, keys: list[str], name: str):
    missing = expected.select(*keys).join(actual.select(*keys), keys, "left_anti").count()
    extra = actual.select(*keys).join(expected.select(*keys), keys, "left_anti").count()
    require(missing == 0 and extra == 0,
            f"{name}: incomplete or foreign keys (missing={missing}, extra={extra}); top-50 is not a full summary")


def compare_values(actual, expected, keys: list[str], counts: list[str], floats: list[str], name: str):
    unique_keys(actual, keys, name)
    same_keys(actual, expected, keys, name)
    actual = numeric(actual, counts)
    actual = numeric(actual, floats, integral=False)
    renamed = expected.select(*keys, *[F.col(col).alias("expected_" + col) for col in counts + floats])
    joined = actual.join(renamed, keys, "inner")
    errors = [F.col(col) != F.col("expected_" + col) for col in counts]
    for col in floats:
        tolerance = F.greatest(F.lit(1e-8), F.abs(F.col("expected_" + col)) * F.lit(1e-12))
        errors.append(F.abs(F.col(col) - F.col("expected_" + col)) > tolerance)
    require(joined.where(reduce(lambda a, b: a | b, errors)).limit(1).count() == 0,
            f"{name}: statistics differ from input graph and assignments")


def verify_community_frames(graph, assignments, summary, overview, amounts) -> dict:
    """Reconcile in-memory tables with the graph, without exporting files.

    Both the presentation notebook and the CSV delivery checker use these
    same checks. No labels or summary statistics are inferred from filenames.
    """
    cached = []
    try:
        vertices = graph.vertices.select("id", "bank_id", "balance").cache()
        edges = graph.edges.select("src", "dst", "isFraud", "amount", "payment_currency").cache()
        cached.extend([vertices, edges])
        unique_keys(vertices, ["id"], "input vertices")
        vertex_count, edge_count = vertices.count(), edges.count()
        require(vertex_count > 0 and edge_count > 0, "Empty input graph")
        require(vertices.where(F.col("bank_id").isNull() | (F.trim(F.col("bank_id")) == "")
                | F.col("balance").isNull() | F.isnan(F.col("balance"))
                | (F.abs(F.col("balance")) == float("inf"))).limit(1).count() == 0,
                "Input bank IDs/balances must be present and finite")
        require(edges.where(F.col("payment_currency").isNull() | (F.trim(F.col("payment_currency")) == "")
                | F.col("amount").isNull() | F.isnan(F.col("amount"))
                | (F.abs(F.col("amount")) == float("inf"))).limit(1).count() == 0,
                "Input amounts/currencies must be present and finite")
        require(edges.where(F.col("isFraud").isNull() | ~F.col("isFraud").isin(0, 1)).limit(1).count() == 0,
                "Input fraud labels must be 0/1")

        unique_keys(assignments, ["id"], "assignments")
        assignments = numeric(assignments, ["label"]).cache()
        cached.append(assignments)
        same_keys(assignments, vertices, ["id"], "assignments")
        print(f"[PASS] Exact account coverage and non-null integer labels: {vertex_count:,}")
        if "bank_id" in assignments.columns:
            require(assignments.join(vertices.select("id", F.col("bank_id").alias("expected_bank")), "id")
                    .where(~F.col("bank_id").eqNullSafe(F.col("expected_bank"))).limit(1).count() == 0,
                    "Exported bank_id does not match the input account")

        members = assignments.select("id", "label").join(vertices, "id")
        sizes = members.groupBy("label").agg(
            F.count("*").alias("member_count"), F.countDistinct("bank_id").alias("unique_banks_count"),
            F.round(F.avg("balance"), 2).alias("avg_balance"))
        source_labels = assignments.select(F.col("id").alias("src"), F.col("label").alias("src_label"))
        dest_labels = assignments.select(F.col("id").alias("dst"), F.col("label").alias("dst_label"))
        labeled = edges.join(source_labels, "src", "left").join(dest_labels, "dst", "left").cache()
        cached.append(labeled)
        require(labeled.where(F.col("src_label").isNull() | F.col("dst_label").isNull()).limit(1).count() == 0,
                "Input graph has dangling edges")
        internal = F.col("src_label") == F.col("dst_label")
        statistics = labeled.groupBy("src_label").agg(
            F.count("*").alias("total_tx_count"), F.sum("isFraud").alias("laundering_tx_count"),
            F.sum(F.when(internal, 1).otherwise(0)).alias("internal_tx_count"),
            F.sum(F.when(internal & (F.col("isFraud") == 1), 1).otherwise(0)).alias("internal_laundering_count"),
        ).withColumnRenamed("src_label", "label")
        counts = ["member_count", "unique_banks_count", "total_tx_count", "laundering_tx_count",
                  "internal_tx_count", "internal_laundering_count"]
        expected = sizes.join(statistics, "label", "left").fillna(0, subset=counts[2:])
        expected = expected.withColumn("laundering_rate", F.round(
            F.col("laundering_tx_count") / F.when(F.col("total_tx_count") == 0, 1)
            .otherwise(F.col("total_tx_count")), 4)).cache()
        cached.append(expected)
        summary = numeric(summary, ["label"])
        compare_values(summary, expected, ["label"], counts, ["avg_balance", "laundering_rate"], "summary")
        require("total_tx_amount" not in summary.columns,
                "Ambiguous total_tx_amount in community summary; amounts must be separated by payment_currency")
        print("[PASS] Complete community sizes, banks, balances, transaction/fraud/internal counts and rates")

        # The top-50 display file remains a view; verify every displayed row.
        overview = numeric(overview, ["label"])
        top_expected = expected.orderBy(F.desc("member_count"), F.asc("label")).limit(50)
        compare_values(overview, top_expected, ["label"], counts,
                       ["avg_balance", "laundering_rate"], "top-50 overview")

        amounts_expected = labeled.groupBy("src_label", "payment_currency").agg(
            F.count("*").alias("total_tx_count"), F.sum("amount").alias("total_tx_amount")
        ).withColumnRenamed("src_label", "label")
        amounts = numeric(amounts, ["label"])
        compare_values(amounts, amounts_expected, ["label", "payment_currency"], ["total_tx_count"],
                       ["total_tx_amount"], "amounts by currency")
        totals = labeled.agg(F.sum("isFraud").alias("fraud"),
                            F.sum(F.when(internal, 1).otherwise(0)).alias("internal")).first()
        return {"vertices": vertex_count, "assigned_vertices": assignments.count(),
                "edges": edge_count, "communities": expected.count(), "summary_rows": summary.count(),
                "internal_edges": totals["internal"], "cross_edges": edge_count - totals["internal"],
                "fraud_edges": totals["fraud"], "amount_currency_rows": amounts.count()}
    finally:
        for frame in reversed(cached):
            frame.unpersist()


def verify_communities(spark, input_dir: Path, output_dir: Path) -> dict:
    """Read CSV deliverables, then run the shared in-memory reconciliation."""
    graph = load_graph(spark, str(input_dir))
    summary_path = output_dir / "community_summary_all.csv"
    if not summary_path.is_file():
        summary_path = output_dir / "community_summary.csv"
    summary_columns = ["label", "member_count", "unique_banks_count", "avg_balance",
                       "total_tx_count", "laundering_tx_count", "internal_tx_count",
                       "internal_laundering_count", "laundering_rate"]
    return verify_community_frames(
        graph,
        read_table(spark, output_dir / "communities.csv", ["id", "label"]),
        read_table(spark, summary_path, summary_columns),
        read_table(spark, output_dir / "community_summary.csv", summary_columns),
        read_table(spark, output_dir / "community_amounts_by_currency.csv",
                   ["label", "payment_currency", "total_tx_count", "total_tx_amount"]),
    )


def compare_partition_frames(current, previous) -> dict:
    """Compare membership using each community's minimum account ID, ignoring label numbers."""
    frames = []
    for assignments in (current, previous):
        frame = numeric(assignments, ["label"])
        unique_keys(frame, ["id"], "partition")
        canonical = frame.groupBy("label").agg(F.min("id").alias("community_anchor"))
        frames.append(frame.join(canonical, "label").select("id", "community_anchor"))
    same_keys(frames[0], frames[1], ["id"], "partition account set")
    joined = frames[0].join(frames[1].withColumnRenamed("community_anchor", "previous_anchor"), "id")
    changed = joined.where(F.col("community_anchor") != F.col("previous_anchor")).count()
    return {"same_partition": changed == 0, "accounts_with_changed_canonical_community": changed,
            "accounts": joined.count(), "interpretation": "observed comparison; differences do not invalidate LPA"}


def compare_partitions(spark, directory: Path, previous: Path) -> dict:
    """CSV adapter for the same membership comparison used in notebooks."""
    return compare_partition_frames(
        read_table(spark, directory / "communities.csv", ["id", "label"]),
        read_table(spark, previous / "communities.csv", ["id", "label"]),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed/sample/ibm_aml"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/ibm_aml"))
    parser.add_argument("--compare-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--lpa-max-iter", type=int, help="Iteration count recorded by the runner; not inferred from CSV")
    parser.add_argument("--lpa-driver-memory")
    parser.add_argument("--lpa-parallelism", type=int)
    parser.add_argument("--require-run-evidence", action="store_true")
    args = parser.parse_args()
    input_dir, output_dir = args.input_dir.resolve(), args.output_dir.resolve()
    sample_source = (REPO_ROOT / "data/processed/sample/ibm_aml").resolve()
    full_source = (REPO_ROOT / "data/processed/ibm_aml").resolve()
    scope = "sample" if input_dir == sample_source else ("full" if input_dir == full_source else "custom")
    report = (args.report or output_dir / "task4_check.json").resolve()
    spark = get_graph_session("GraphGuard-IBM-Task4-Check", driver_memory="4g")
    try:
        metrics = verify_communities(spark, input_dir, output_dir)
        if args.require_run_evidence:
            execution = verify_run_evidence(output_dir / "task4_run.json", task="Task 4 IBM LPA execution")
            require(execution["parameters"]["max_iter"] == args.lpa_max_iter,
                    "Recorded iteration count does not match LPA execution")
            metrics["lpa_execution_runtime"] = execution["runtime"]
        if args.compare_dir:
            verify_communities(spark, input_dir, args.compare_dir.resolve())
            if args.require_run_evidence:
                verify_run_evidence(args.compare_dir.resolve() / "task4_run.json", task="Task 4 IBM LPA execution")
            metrics["repeat_comparison"] = compare_partitions(spark, output_dir, args.compare_dir.resolve())
        write_run_evidence(
            report, spark, task="Task 4 IBM independent output check", inputs=[input_dir],
            outputs=[output_dir / name for name in ("communities.csv", "community_summary.csv",
                     "community_summary_all.csv", "community_amounts_by_currency.csv")]
                    + ([output_dir / "task4_run.json"] if args.require_run_evidence else []),
            sources=[Path(__file__), REPO_ROOT / "src/ibm_aml/community_detection.py",
                     REPO_ROOT / "src/common/run_evidence.py", REPO_ROOT / "src/common/spark_session.py",
                     REPO_ROOT / "src/common/windows_runtime.py", REPO_ROOT / "src/common/graph_utils.py",
                     REPO_ROOT / "scripts/check_task4.ps1"],
            parameters={"input_dir": str(input_dir), "output_dir": str(output_dir),
                        "scope": scope,
                        "lpa_max_iter_reported_by_runner": args.lpa_max_iter,
                        "lpa_driver_memory_reported_by_runner": args.lpa_driver_memory,
                        "lpa_parallelism_reported_by_runner": args.lpa_parallelism}, metrics=metrics,
        )
        print(f"[PASS] Task 4 IBM checked against the input graph: {metrics}")
    except Exception as error:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"status": "FAIL", "error": str(error)}, indent=2) + "\n", encoding="utf-8")
        print(f"[FAIL] {error}")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
