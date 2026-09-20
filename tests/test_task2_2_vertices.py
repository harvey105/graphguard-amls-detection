"""
File: tests/test_task2_2_vertices.py
Task: 2.2 Validation Runner (Person 2)
Run from the project root: python tests/test_task2_2_vertices.py
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
from src.paysim.etl_mapping import build_vertices_df


def main():
    spark = (
        SparkSession.builder
        .appName("GraphGuard-Task2.2-VerticesValidation")
        .master("local[*]")
        .config("spark.driver.memory", "6g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw_path = "data/raw/paysim/PS_20174392719_1491204439457_log.csv"
    if not os.path.exists(raw_path):
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

    print("[*] Loading raw data...")
    raw_df = spark.read.csv(raw_path, header=True, schema=schema)

    print("[*] Running build_vertices_df()...")
    vertices_df = build_vertices_df(raw_df)
    vertices_df.cache()

    print("\n" + "=" * 60)
    print("TASK 2.2: VERTICES VALIDATION REPORT")
    print("=" * 60)

    print("1. Schema:")
    vertices_df.printSchema()

    v_count = vertices_df.count()
    print(f"2. Total Vertex Count: {v_count:,} (Expected: 9,073,900)")

    print("\n3. Account Type Breakdown:")
    vertices_df.groupBy("account_type").count().show()

    null_counts = vertices_df.select(
        [F.count(F.when(F.col(c).isNull(), c)).alias(c) for c in vertices_df.columns]
    )
    print("4. Null Value Counts (Must all be 0):")
    null_counts.show()

    print("5. Sample Customer & Merchant Records:")
    vertices_df.filter(F.col("account_type") == "Customer").show(5, truncate=False)
    vertices_df.filter(F.col("account_type") == "Merchant").show(5, truncate=False)

    print("6. Overlapping Account Balance Verification (Sample):")
    sample_overlap = raw_df.select("nameOrig").intersect(raw_df.select("nameDest")).limit(1).collect()
    if sample_overlap:
        overlap_id = sample_overlap[0][0]
        print(f"Sample Overlap Account ID: {overlap_id}")
        print("Raw transaction history for this account (most recent first):")
        raw_df.filter((F.col("nameOrig") == overlap_id) | (F.col("nameDest") == overlap_id)) \
              .select("step", "type", "amount", "nameOrig", "newbalanceOrig", "nameDest", "newbalanceDest") \
              .orderBy(F.col("step").desc()) \
              .show(truncate=False)
        print("Resolved record in vertices_df:")
        vertices_df.filter(F.col("id") == overlap_id).show(truncate=False)

    print("\n[+] Task 2.2 Validation Completed.")
    spark.stop()


if __name__ == "__main__":
    main()
