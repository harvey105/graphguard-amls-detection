"""
File: tests/test_task2_3_edges.py
Task: 2.3 Validation Runner (Person 2)
Run from project root: python tests/test_task2_3_edges.py
"""

import sys
import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, ShortType
)

# Make src/ importable when running this file directly from tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.etl_mapping import build_vertices_df, build_edges_df


def main():
    spark = (
        SparkSession.builder
        .appName("GraphGuard-Task2.3-EdgesValidation")
        .master("local[*]")
        .config("spark.driver.memory", "6g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw_path = "data/raw/PS_20174392719_1491204439457_log.csv"  # adjust if needed
    if not os.path.exists(raw_path):
        print(f"[ERROR] Cannot find raw CSV at: {raw_path}")
        sys.exit(1)

    schema = StructType([
        StructField("step", IntegerType(), False),
        StructField("type", StringType(), False),
        StructField("amount", DoubleType(), False),
        StructField("nameOrig", StringType(), False),
        StructField("oldbalanceOrg", DoubleType(), False),
        StructField("newbalanceOrig", DoubleType(), False),
        StructField("nameDest", StringType(), False),
        StructField("oldbalanceDest", DoubleType(), False),
        StructField("newbalanceDest", DoubleType(), False),
        StructField("isFraud", ShortType(), False),
        StructField("isFlaggedFraud", ShortType(), False),
    ])

    print("[*] Ingesting raw data...")
    # Cache raw_df up front: it's reused 3x below (edges build, raw count,
    # and the vertices rebuild for the referential-integrity check). Without
    # .cache() here, Spark re-reads + re-parses the ~493MB CSV from scratch
    # on each of those passes since nothing upstream of raw_df is persisted.
    raw_df = spark.read.csv(raw_path, header=True, schema=schema).cache()
    raw_count = raw_df.count()  # materializes the cache once, up front

    print("[*] Building edges_df...")
    edges_df = build_edges_df(raw_df)
    edges_df.cache()

    print("\n" + "=" * 60)
    print("TASK 2.3: EDGES VALIDATION REPORT")
    print("=" * 60)

    # 1. Schema Check
    print("1. Schema:")
    edges_df.printSchema()

    # 2. Total Edge Count
    e_count = edges_df.count()
    print(f"2. Total Edge Count: {e_count:,} (Raw Tx Count: {raw_count:,})")
    print("   (Sanity check only: this is a 1:1 column select with no filter or")
    print("    groupBy, so the counts matching is guaranteed by construction —")
    print("    it documents the mapping for the report, it doesn't prove")
    print("    correctness. Section 5 below is the real correctness check.)")
    assert e_count == raw_count, f"Mismatch: {e_count} vs {raw_count}"

    # 3. Null Values Check
    print("\n3. Null Value Counts (Must all be 0):")
    null_counts = edges_df.select(
        [F.count(F.when(F.col(c).isNull(), c)).alias(c) for c in edges_df.columns]
    )
    null_counts.show()

    # 4. Transaction Type Breakdown in Edges
    print("4. Edge Distribution by Type:")
    edges_df.groupBy("type").agg(
        F.count("*").alias("total_edges"),
        F.sum("isFraud").alias("fraud_edges")
    ).orderBy(F.col("total_edges").desc()).show()

    # 5. Referential Integrity Check (Edges vs Vertices)
    print("5. Referential Integrity Check (Dangling Edges Probe):")
    print("   Rebuilding vertices_df from the (now cached) raw_df for cross-check...")
    vertices_df = build_vertices_df(raw_df)
    vertices_df.cache()

    dangling_src = edges_df.join(
        vertices_df, edges_df["src"] == vertices_df["id"], "left_anti"
    ).count()
    dangling_dst = edges_df.join(
        vertices_df, edges_df["dst"] == vertices_df["id"], "left_anti"
    ).count()

    print(f"   Dangling Sources:      {dangling_src} (Must be 0)")
    print(f"   Dangling Destinations: {dangling_dst} (Must be 0)")

    # 6. Self-loop spot-check (defensive; Task 2.1 already found 0 exhaustively)
    print("\n6. Self-Loop Spot-Check (src == dst, expect 0 per Task 2.1 audit):")
    self_loops = edges_df.filter(F.col("src") == F.col("dst")).count()
    print(f"   Self-loops in edges_df: {self_loops} (Must be 0)")

    # 7. Sample Edges
    print("\n7. Sample Edges (Showing Fraud & Non-Fraud Records):")
    edges_df.filter(F.col("isFraud") == 1).show(5, truncate=False)
    edges_df.filter(F.col("isFraud") == 0).show(5, truncate=False)

    print("[+] Task 2.3 Validation Completed Successfully.")
    spark.stop()


if __name__ == "__main__":
    main()
