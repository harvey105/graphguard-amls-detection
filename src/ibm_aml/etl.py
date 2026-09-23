r"""Build the IBM AML HI-Small graph and persist it as Parquet.

Week-1 owner: N2. Run from the repository root with Windows Python:

    & .\.venv\Scripts\python.exe -m src.ibm_aml.etl

The raw CSV contains two columns both named ``Account``. Spark therefore
receives an explicit positional schema with distinct internal names instead
of relying on automatic header de-duplication (``Account.1`` is a pandas
convention, not the literal CSV header).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    ShortType,
    StringType,
    StructField,
    StructType,
)

from src.common.spark_session import get_graph_session


EXPECTED_EDGE_COUNT = 5_078_345
TIMESTAMP_FORMAT = "yyyy/MM/dd HH:mm"

# Names are deliberately different from the duplicate raw Account headers.
# With enforceSchema=true Spark applies these fields by CSV position. Spark
# logs a header-name warning, which is expected and does not change the map.
IBM_RAW_SCHEMA = StructType(
    [
        StructField("timestamp_raw", StringType(), True),
        StructField("from_bank", StringType(), True),
        StructField("from_account", StringType(), True),
        StructField("to_bank", StringType(), True),
        StructField("to_account", StringType(), True),
        StructField("amount_received", DoubleType(), True),
        StructField("receiving_currency", StringType(), True),
        StructField("amount_paid", DoubleType(), True),
        StructField("payment_currency", StringType(), True),
        StructField("payment_format", StringType(), True),
        StructField("is_laundering", ShortType(), True),
    ]
)


def _clean_text(column_name: str):
    """Trim a required string column without changing leading zeroes."""
    return F.trim(F.col(column_name))


def _account_id(bank_column: str, account_column: str):
    """Create an unambiguous cross-bank account identifier."""
    return F.concat_ws(
        "::",
        _clean_text(bank_column),
        _clean_text(account_column),
    )


def read_raw_transactions(spark: SparkSession, input_path: str) -> DataFrame:
    """Read HI-Small with a positional schema to handle duplicate headers."""
    return (
        spark.read.option("header", "true")
        .option("enforceSchema", "true")
        .option("mode", "FAILFAST")
        .schema(IBM_RAW_SCHEMA)
        .csv(input_path)
    )


def build_vertices_df(raw_df: DataFrame) -> DataFrame:
    """Return unique ``id, bank_id, account_id`` IBM AML vertices."""
    senders = raw_df.select(
        _account_id("from_bank", "from_account").alias("id"),
        _clean_text("from_bank").alias("bank_id"),
        _clean_text("from_account").alias("account_id"),
    )
    receivers = raw_df.select(
        _account_id("to_bank", "to_account").alias("id"),
        _clean_text("to_bank").alias("bank_id"),
        _clean_text("to_account").alias("account_id"),
    )
    return senders.unionByName(receivers).dropDuplicates(["id"])


def build_edges_df(raw_df: DataFrame) -> DataFrame:
    """Map each raw transaction to the shared GraphFrame edge contract.

    ``amount`` and ``currency`` use the receiving side, matching the week-1
    assignment's explicit ``Amount Received`` field. The paid-side values are
    retained because cross-currency transactions need both sides for later
    analysis; the ETL does not perform an unsafe currency conversion.
    """
    return raw_df.select(
        _account_id("from_bank", "from_account").alias("src"),
        _account_id("to_bank", "to_account").alias("dst"),
        F.to_timestamp("timestamp_raw", TIMESTAMP_FORMAT).alias("timestamp"),
        F.col("amount_received").cast("double").alias("amount"),
        F.col("amount_received").cast("double").alias("amount_received"),
        F.col("receiving_currency").alias("currency"),
        F.col("receiving_currency"),
        F.col("amount_paid").cast("double").alias("amount_paid"),
        F.col("payment_currency"),
        F.col("payment_format"),
        F.col("is_laundering").cast("short").alias("isLaundering"),
    )


def validate_graph(
    raw_df: DataFrame,
    vertices_df: DataFrame,
    edges_df: DataFrame,
) -> dict[str, Any]:
    """Run week-1 schema and referential-integrity checks."""
    raw_count = raw_df.count()
    vertex_count = vertices_df.count()
    edge_count = edges_df.count()

    null_vertices = vertices_df.filter(
        F.col("id").isNull()
        | (F.length("id") == 0)
        | F.col("bank_id").isNull()
        | (F.length("bank_id") == 0)
        | F.col("account_id").isNull()
        | (F.length("account_id") == 0)
    ).count()
    duplicate_vertex_ids = vertex_count - vertices_df.select("id").distinct().count()
    null_edges = edges_df.filter(
        F.col("src").isNull()
        | F.col("dst").isNull()
        | F.col("timestamp").isNull()
        | F.col("amount").isNull()
        | F.col("isLaundering").isNull()
    ).count()

    vertex_ids = vertices_df.select("id")
    dangling_src = edges_df.select(F.col("src").alias("id")).join(
        vertex_ids, on="id", how="left_anti"
    ).count()
    dangling_dst = edges_df.select(F.col("dst").alias("id")).join(
        vertex_ids, on="id", how="left_anti"
    ).count()

    laundering_edges = edges_df.filter(F.col("isLaundering") == 1).count()
    self_loops = edges_df.filter(F.col("src") == F.col("dst")).count()
    cross_bank_edges = raw_df.filter(
        _clean_text("from_bank") != _clean_text("to_bank")
    ).count()

    checks = {
        "raw_count_matches_expected": raw_count == EXPECTED_EDGE_COUNT,
        "edge_count_matches_raw": edge_count == raw_count,
        "no_null_vertices": null_vertices == 0,
        "unique_vertex_ids": duplicate_vertex_ids == 0,
        "no_null_required_edge_fields": null_edges == 0,
        "zero_dangling_src": dangling_src == 0,
        "zero_dangling_dst": dangling_dst == 0,
    }
    metrics: dict[str, Any] = {
        "dataset": "IBM AML HI-Small",
        "raw_transactions": raw_count,
        "vertices": vertex_count,
        "edges": edge_count,
        "laundering_edges": laundering_edges,
        "self_loops": self_loops,
        "cross_bank_edges": cross_bank_edges,
        "null_vertices": null_vertices,
        "duplicate_vertex_ids": duplicate_vertex_ids,
        "null_required_edge_fields": null_edges,
        "dangling_src": dangling_src,
        "dangling_dst": dangling_dst,
        "checks": checks,
        "all_passed": all(checks.values()),
    }
    return metrics


def _print_validation(metrics: dict[str, Any]) -> None:
    print("\n" + "=" * 68)
    print("IBM AML HI-SMALL — WEEK 1 ETL VALIDATION")
    print("=" * 68)
    for name, passed in metrics["checks"].items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print("-" * 68)
    for name in (
        "raw_transactions",
        "vertices",
        "edges",
        "laundering_edges",
        "self_loops",
        "cross_bank_edges",
        "dangling_src",
        "dangling_dst",
    ):
        print(f"  {name:28s}: {metrics[name]:,}")
    print("=" * 68)


def _write_manifest(path: str, metrics: dict[str, Any]) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IBM AML HI-Small week-1 ETL")
    parser.add_argument(
        "--input",
        default="data/raw/ibm_aml/HI-Small_Trans.csv",
        help="Raw HI-Small CSV path relative to the repository root.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/ibm_aml",
        help="Output folder for vertices.parquet and edges.parquet.",
    )
    parser.add_argument(
        "--manifest",
        default="report_week1/ibm_aml_etl_manifest.json",
        help="JSON validation manifest path.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run all validation checks without writing Parquet.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not Path(args.input).is_file():
        raise FileNotFoundError(
            f"Không tìm thấy {args.input}. Chạy scripts\\download_datasets.ps1 trước."
        )

    spark = get_graph_session(
        app_name="GraphGuard-IBM-AML-Week1-ETL",
        driver_memory="6g",
        shuffle_partitions=8,
    )
    spark.sparkContext.setLogLevel("WARN")

    try:
        print(f"[*] Reading {args.input}")
        raw_df = read_raw_transactions(spark, args.input).cache()
        vertices_df = build_vertices_df(raw_df).cache()
        edges_df = build_edges_df(raw_df).cache()

        metrics = validate_graph(raw_df, vertices_df, edges_df)
        _print_validation(metrics)
        _write_manifest(args.manifest, metrics)
        print(f"[OK] Validation manifest: {args.manifest}")

        if not metrics["all_passed"]:
            print("[ERROR] ETL validation failed; Parquet was not written.")
            return 1

        if not args.validate_only:
            output_path = Path(args.output)
            vertices_path = output_path / "vertices.parquet"
            edges_path = output_path / "edges.parquet"
            print(f"[*] Writing {vertices_path}")
            vertices_df.write.mode("overwrite").parquet(str(vertices_path))
            print(f"[*] Writing {edges_path}")
            edges_df.write.mode("overwrite").parquet(str(edges_path))

            disk_vertex_count = spark.read.parquet(str(vertices_path)).count()
            disk_edge_count = spark.read.parquet(str(edges_path)).count()
            persisted_ok = (
                disk_vertex_count == metrics["vertices"]
                and disk_edge_count == metrics["edges"]
            )
            metrics["persisted_vertices"] = disk_vertex_count
            metrics["persisted_edges"] = disk_edge_count
            metrics["checks"]["parquet_round_trip"] = persisted_ok
            metrics["all_passed"] = metrics["all_passed"] and persisted_ok
            _write_manifest(args.manifest, metrics)
            print(
                f"[{'PASS' if persisted_ok else 'FAIL'}] Parquet round-trip: "
                f"vertices={disk_vertex_count:,}, edges={disk_edge_count:,}"
            )
            if not persisted_ok:
                return 1

        print("[PASS] IBM AML week-1 ETL completed.")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
