"""
File: src/export_parquet.py
Task: 2.4 — Data Quality Checks & Optimized Parquet Export (Person 2)
Run from project root: python src/export_parquet.py

Windows note: writing Parquet locally needs winutils.exe/hadoop.dll on PATH
(HADOOP_HOME set) or Spark will throw a FileOutputCommitter IOException.
See helper1_feedback.md Part 2 Section 2 for the one-time setup steps.
"""

import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, ShortType
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.etl_mapping import build_vertices_df, build_edges_df

# Known-good reference values, confirmed exhaustively in Task 2.1 / verified
# again in the 2.2 and 2.3 validation runs. Used for the quality-report
# cross-checks below instead of re-deriving them with an extra expensive
# distinct/union scan over raw_df.
EXPECTED_VERTEX_COUNT = 9_073_900
EXPECTED_EDGE_COUNT = 6_362_620


def create_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("GraphGuard-Task2.4-ParquetExport")
        .master("local[*]")
        .config("spark.driver.memory", "6g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def dir_size_mb(path: str) -> float:
    """Sum the byte size of a written Parquet directory's part-files."""
    total_bytes = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            total_bytes += os.path.getsize(os.path.join(dirpath, f))
    return total_bytes / (1024 * 1024)


def main():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    raw_path = "data/raw/PS_20174392719_1491204439457_log.csv"
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

    print("=" * 60)
    print("TASK 2.4: PARQUET EXPORT & PERSISTENCE PIPELINE")
    print("=" * 60)

    # 1. Ingest Raw Data
    print("[1/6] Ingesting raw CSV...")
    raw_df = spark.read.csv(raw_path, header=True, schema=schema).cache()
    total_raw = raw_df.count()
    print(f"      Loaded {total_raw:,} records.")

    # 2. Build Transformed DataFrames
    print("[2/6] Transforming Vertices and Edges DataFrames...")
    # vertices_df already comes out of build_vertices_df()'s groupBy/agg with
    # spark.sql.shuffle.partitions (=8) output partitions -- no need to
    # repartition(8) again, that would just force a second full shuffle over
    # all 9.07M rows for the same partition count.
    vertices_df = build_vertices_df(raw_df).cache()
    # edges_df is a narrow select straight off raw_df's file-split partitions
    # (not 8), so this repartition is the one that's actually doing work.
    edges_df = build_edges_df(raw_df).repartition(8).cache()

    v_count = vertices_df.count()
    e_count = edges_df.count()
    print(f"      Vertices ready: {v_count:,} rows")
    print(f"      Edges ready:    {e_count:,} rows")

    # raw_df isn't needed again after this point -- release it now rather
    # than holding it in memory alongside vertices_df/edges_df/sample caches.
    raw_df.unpersist()

    # 3. Data Quality Report (pass/fail per check, per the Work Plan's
    #    Task 2.4 "Expected Output"). Re-verifies the checks the plan lists,
    #    right before they become the official Task 1 deliverable.
    print("[3/6] Running data quality checks...")
    checks = {}

    null_v = vertices_df.filter(F.col("id").isNull()).count()
    checks["No null vertex ids"] = (null_v == 0, f"{null_v} nulls found")

    null_e = edges_df.filter(F.col("src").isNull() | F.col("dst").isNull()).count()
    checks["No null src/dst"] = (null_e == 0, f"{null_e} nulls found")

    dangling_src = edges_df.join(vertices_df, edges_df["src"] == vertices_df["id"], "left_anti").count()
    dangling_dst = edges_df.join(vertices_df, edges_df["dst"] == vertices_df["id"], "left_anti").count()
    checks["Referential integrity (0 dangling edges)"] = (
        dangling_src == 0 and dangling_dst == 0,
        f"{dangling_src} dangling src, {dangling_dst} dangling dst",
    )

    checks["Vertex count matches expected"] = (
        v_count == EXPECTED_VERTEX_COUNT,
        f"{v_count:,} vs expected {EXPECTED_VERTEX_COUNT:,}",
    )
    checks["Edge count matches raw row count"] = (
        e_count == total_raw == EXPECTED_EDGE_COUNT,
        f"edges={e_count:,}, raw={total_raw:,}, expected={EXPECTED_EDGE_COUNT:,}",
    )

    print("\n" + "-" * 60)
    print("DATA QUALITY REPORT")
    print("-" * 60)
    all_passed = True
    for name, (passed, detail) in checks.items():
        status = "PASS" if passed else "FAIL"
        all_passed = all_passed and passed
        print(f"  [{status}] {name}  ({detail})")
    print("-" * 60)

    if not all_passed:
        print("[ERROR] One or more quality checks failed. Aborting export "
              "before writing Parquet -- fix the issue above and re-run.")
        spark.stop()
        sys.exit(1)

    # 4. Export Full Parquet Datasets
    full_v_path = "data/processed/vertices.parquet"
    full_e_path = "data/processed/edges.parquet"

    print("\n[4/6] Writing full datasets to Parquet (Snappy compressed)...")
    vertices_df.write.mode("overwrite").parquet(full_v_path)
    edges_df.write.mode("overwrite").parquet(full_e_path)
    print(f"      [OK] {full_v_path}  ({dir_size_mb(full_v_path):.1f} MB on disk)")
    print(f"      [OK] {full_e_path}  ({dir_size_mb(full_e_path):.1f} MB on disk)")

    # 5. Induced Sample Graph (~100k edges) for Quick Team Prototyping
    print("\n[5/6] Generating induced sample graph (~100,000 edges)...")
    sample_fraction = 100000.0 / e_count
    sample_edges = edges_df.sample(withReplacement=False, fraction=sample_fraction, seed=42).cache()
    sample_e_count = sample_edges.count()
    sample_fraud_count = sample_edges.filter(F.col("isFraud") == 1).count()

    sample_node_ids = (
        sample_edges.select(F.col("src").alias("id"))
        .union(sample_edges.select(F.col("dst").alias("id")))
        .distinct()
        .cache()
    )
    sample_node_count = sample_node_ids.count()

    sample_vertices = vertices_df.join(sample_node_ids, on="id", how="inner").cache()
    sample_v_count = sample_vertices.count()

    # Defensive check: inner join should never drop a node here, since 2.3
    # already proved zero dangling edges on the full graph. If this ever
    # fires, something upstream changed and the sample is not self-contained.
    if sample_v_count != sample_node_count:
        print(f"      [WARNING] Induced sample has {sample_node_count - sample_v_count} "
              f"node id(s) missing from vertices_df -- sample subgraph would have "
              f"dangling edges. Investigate before sharing with the team.")
    else:
        print(f"      [OK] Sample is self-contained: all {sample_node_count:,} node ids resolved.")

    sample_v_path = "data/processed/sample/vertices.parquet"
    sample_e_path = "data/processed/sample/edges.parquet"

    sample_vertices.coalesce(1).write.mode("overwrite").parquet(sample_v_path)
    sample_edges.coalesce(1).write.mode("overwrite").parquet(sample_e_path)
    print(f"      Sample Vertices: {sample_v_count:,} rows -> {sample_v_path}")
    print(f"      Sample Edges:    {sample_e_count:,} rows -> {sample_e_path}  "
          f"({sample_fraud_count} fraud edges included)")

    # 6. Verification & Disk Inspection
    print("\n[6/6] Verifying written Parquet files by reading from disk...")
    disk_v = spark.read.parquet(full_v_path)
    disk_e = spark.read.parquet(full_e_path)

    read_v_count = disk_v.count()
    read_e_count = disk_e.count()

    print("\n" + "=" * 60)
    print("TASK 2.4: FINAL PERSISTENCE VALIDATION REPORT")
    print("=" * 60)
    print(f"Vertices Parquet Count: {read_v_count:,} (Expected: {v_count:,})")
    print(f"Edges Parquet Count:    {read_e_count:,} (Expected: {e_count:,})")
    assert read_v_count == v_count, "Disk Vertices count mismatch!"
    assert read_e_count == e_count, "Disk Edges count mismatch!"

    print("\nSchema Verification from Disk:")
    print("Vertices Schema:")
    disk_v.printSchema()
    print("Edges Schema:")
    disk_e.printSchema()

    print("[+] Task 2.4 Completed Successfully. Production Parquet files are locked.")
    print("\n[!] Reminder: data/processed/*.parquet (full) is not in the repo's")
    print("    top-level .gitignore yet -- only data/raw is. Add the full")
    print("    vertices.parquet/edges.parquet paths to .gitignore before")
    print("    committing, and keep only data/processed/sample/ tracked,")
    print("    per repo.txt's data/README.md policy.")
    spark.stop()


if __name__ == "__main__":
    main()
