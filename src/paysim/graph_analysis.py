"""
File: src/graph_analysis.py
Task: Task 1 -- Graph Construction & Network Metrics Initialization (15 points)
Role: Person 2 (Data Engineering Lead) & Person 1 (Co-owner / Reviewer)

Execution Options:
  python src/graph_analysis.py                    # Fast mode: loads data/processed/*.parquet
  python src/graph_analysis.py --sample            # Prototype mode: ~100k-edge sample graph
  python src/graph_analysis.py --from-raw          # Full ETL mode: builds end-to-end from raw CSV
  python src/graph_analysis.py --from-raw --sample # Build from CSV, but keep only a ~100k sample

Dependency, verified live against PyPI on 2026-09-15 (not from memory -- exact
package/version facts like this go stale or get misremembered easily):
  pip install graphframes-py==0.12.2
  https://pypi.org/project/graphframes-py/  <- confirmed real, latest release,
    uploaded 2026-08-28. Requires Python >= 3.10 -- check `python --version`
    in your venv before installing.
  The JVM side is resolved automatically below via spark.jars.packages using
  the io.graphframes Maven Central coordinate (this is the package's own
  documented install method, not a spark-packages.org artifact -- no extra
  .config("spark.jars.repositories", ...) needed).
  Do NOT fall back to `pip install graphframes` (no -py suffix) if this
  install fails for some other reason -- that's a dead, pre-Spark-3
  package last published in 2018 and will not work here.
"""

import os
import sys
import argparse
import pyspark
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, ShortType
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.paysim.etl_mapping import build_vertices_df, build_edges_df
from src.common.spark_session import get_graph_session

try:
    from graphframes import GraphFrame
except ImportError:
    print("[ERROR] graphframes Python module not found.")
    print("        Run: pip install graphframes-py==0.12.2")
    print("        (Confirmed current on PyPI as of 2026-09-15: https://pypi.org/project/graphframes-py/)")
    print("        Requires Python >= 3.10 -- check `python --version` in your venv.")
    print("        Do NOT install plain 'graphframes' (no -py) as a fallback --")
    print("        that package is dead, last published in 2018.")
    sys.exit(1)

# Known-good reference values for the FULL graph, confirmed exhaustively in
# Task 2.1 and re-verified in 2.2/2.3/2.4. Used below for pass/fail checks
# instead of just printing counts with nothing to compare them to.
EXPECTED_VERTEX_COUNT = 9_073_900
EXPECTED_EDGE_COUNT = 6_362_620

# Verified against https://pypi.org/project/graphframes-py/ on 2026-09-15.
# Bump this if a newer release ships and re-verify before changing.
GRAPHFRAMES_VERSION = "0.12.2"


def resolve_graphframes_coordinate() -> str:
    """
    Picks the Maven Central coordinate matching the installed PySpark's major
    version: graphframes-spark3_2.12 for Spark 3.x, graphframes-spark4_2.13
    for Spark 4.x (GraphFrames only ships a Scala 2.13 build for Spark 4.x).
    This matches the install pattern documented on the package's own PyPI
    page. Detecting the version instead of hardcoding it means this keeps
    working whichever Spark major version `pip install pyspark` resolves to.
    """
    major = pyspark.__version__.split(".")[0]
    scala_suffix = "2.13" if major == "4" else "2.12"
    return f"io.graphframes:graphframes-spark{major}_{scala_suffix}:{GRAPHFRAMES_VERSION}"


def create_graph_spark_session(app_name: str = "GraphGuard-GraphConstruction", driver_memory="6g") -> SparkSession:
    return get_graph_session(app_name, driver_memory=driver_memory)


def load_from_parquet(spark: SparkSession, sample: bool = False):
    preferred_dir = "data/processed/sample/paysim" if sample else "data/processed/paysim"
    legacy_dir = "data/processed/sample" if sample else "data/processed"
    preferred_v_path = os.path.join(preferred_dir, "vertices.parquet")
    preferred_e_path = os.path.join(preferred_dir, "edges.parquet")
    if os.path.exists(preferred_v_path) and os.path.exists(preferred_e_path):
        base_dir = preferred_dir
    else:
        base_dir = legacy_dir
        print(f"[WARN] Preferred path not found: {preferred_dir}; using {legacy_dir}.")
    v_path = os.path.join(base_dir, "vertices.parquet")
    e_path = os.path.join(base_dir, "edges.parquet")

    if not os.path.exists(v_path) or not os.path.exists(e_path):
        print(f"[ERROR] Cannot find Parquet files at {base_dir}.")
        print("        Run 'python -m src.paysim.export_parquet' first or use '--from-raw'.")
        sys.exit(1)

    print(f"[*] Loading Graph Data from Parquet [{base_dir}]...")
    vertices_df = spark.read.parquet(v_path)
    edges_df = spark.read.parquet(e_path)
    return vertices_df, edges_df


def load_from_raw_csv(spark: SparkSession, raw_path: str):
    """Build vertices and edges on-the-fly from raw CSV. Returns raw_df too
    (cached), since it's reused below for the raw-transaction spot-check."""
    if not os.path.exists(raw_path):
        print(f"[ERROR] Cannot find raw CSV at {raw_path}")
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

    print(f"[*] Running End-to-End ETL from raw CSV [{raw_path}]...")
    raw_df = spark.read.csv(raw_path, header=True, schema=schema).cache()
    vertices_df = build_vertices_df(raw_df)
    edges_df = build_edges_df(raw_df)
    return raw_df, vertices_df, edges_df


def induce_sample(vertices_df, edges_df, target_edges: int = 100_000, seed: int = 42):
    """Same induced-subgraph logic as export_parquet.py's sample export, so
    `--from-raw --sample` behaves the same way as loading the on-disk sample
    instead of silently ignoring --sample and building the full graph."""
    total_edges = edges_df.count()
    fraction = min(1.0, target_edges / total_edges)
    sample_edges = edges_df.sample(withReplacement=False, fraction=fraction, seed=seed).cache()
    sample_node_ids = (
        sample_edges.select(F.col("src").alias("id"))
        .union(sample_edges.select(F.col("dst").alias("id")))
        .distinct()
    )
    sample_vertices = vertices_df.join(sample_node_ids, on="id", how="inner").cache()
    return sample_vertices, sample_edges


def verify_graph(graph, *, sample=False, raw_df=None):
    """Return verified counts or raise; a printed FAIL can never be success."""
    from functools import reduce
    from src.common.graph_utils import check_integrity

    required_v = {"id", "account_type", "balance"}
    required_e = {"src", "dst", "amount", "step", "type", "isFraud"}
    if not required_v <= set(graph.vertices.columns) or not required_e <= set(graph.edges.columns):
        raise ValueError("Missing required graph schema")
    counts = check_integrity(graph)
    if counts["num_vertices"] <= 0 or counts["num_edges"] <= 0:
        raise ValueError("Empty graph")
    if counts["null_vertices"] or counts["null_edges"] or counts["dangling_edges"]:
        raise ValueError("Null keys or dangling edges")
    if graph.vertices.select("id").distinct().count() != counts["num_vertices"]:
        raise ValueError("Duplicate vertex ID")
    if not sample and (counts["num_vertices"], counts["num_edges"]) != (EXPECTED_VERTEX_COUNT, EXPECTED_EDGE_COUNT):
        raise ValueError("Full graph cardinality differs from the PaySim contract")
    nulls = [F.col(name).isNull() for name in required_e]
    bad_edges = reduce(lambda a, b: a | b, nulls)
    bad_edges = bad_edges | F.isnan("amount") | (F.abs("amount") == float("inf")) | (F.col("amount") < 0)
    bad_edges = bad_edges | (F.trim("src") == "") | (F.trim("dst") == "")
    bad_edges = bad_edges | ~F.col("isFraud").isin(0, 1) | ~F.col("type").isin("CASH_IN", "CASH_OUT", "PAYMENT", "DEBIT", "TRANSFER")
    bad_edges = bad_edges | ~F.col("step").between(1, 744) | (F.col("step") != F.col("step").cast("long"))
    bad_vertices = ((F.trim("id") == "") | F.col("account_type").isNull() | F.col("balance").isNull() | F.isnan("balance") | (F.abs("balance") == float("inf"))
                    | ~F.col("account_type").isin("Customer", "Merchant"))
    if graph.edges.where(bad_edges).limit(1).count() or graph.vertices.where(bad_vertices).limit(1).count():
        raise ValueError("Invalid transaction value or account metadata")
    raw_checked = 0
    if raw_df is not None:
        for row in graph.edges.limit(5).collect():
            matches = raw_df.where((F.col("nameOrig") == row.src) & (F.col("nameDest") == row.dst)
                & (F.col("step") == row.step) & (F.col("amount") == row.amount)
                & (F.col("type") == row.type) & (F.col("isFraud") == row.isFraud)).limit(1).count()
            if not matches:
                raise ValueError("Constructed edge absent from raw spot-check")
            raw_checked += 1
    return {**counts, "raw_spot_checked_rows": raw_checked, "scope": "sample" if sample else "full"}


def main():
    from pathlib import Path
    from src.common.graph_utils import load_graph
    from src.common.run_evidence import REPO_ROOT, write_run_evidence

    parser = argparse.ArgumentParser(description="Task 1: construct and strictly verify PaySim graph")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--from-raw", action="store_true")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--driver-memory")
    args = parser.parse_args()
    if args.from_raw and args.input_dir:
        parser.error("Choose --from-raw or --input-dir")
    input_dir = (args.input_dir or REPO_ROOT / ("data/processed/sample/paysim" if args.sample else "data/processed/paysim")).resolve()
    report_path = (args.report or REPO_ROOT / "results/paysim/task1_run.json").resolve()
    raw_path = REPO_ROOT / "data/raw/paysim/PS_20174392719_1491204439457_log.csv"
    spark = create_graph_spark_session(driver_memory=args.driver_memory or ("4g" if args.sample else "6g"))
    owned = []
    try:
        spark.sparkContext.setLogLevel("ERROR")
        raw = None
        if args.from_raw:
            raw, vertices, edges = load_from_raw_csv(spark, str(raw_path))
            owned.append(raw)
            if args.sample:
                vertices, edges = induce_sample(vertices, edges)
        else:
            graph = load_graph(spark, str(input_dir))
            vertices, edges = graph.vertices, graph.edges
        vertices, edges = vertices.cache(), edges.cache()
        owned.extend([vertices, edges])
        graph = GraphFrame(vertices, edges)
        metrics = verify_graph(graph, sample=args.sample, raw_df=raw)
        write_run_evidence(report_path, spark, task="Task 1 PaySim graph verification",
            inputs=[raw_path if args.from_raw else input_dir], outputs=[],
            sources=[Path(__file__), REPO_ROOT / "src/paysim/etl_mapping.py", REPO_ROOT / "src/common/graph_utils.py"],
            parameters={"sample": args.sample, "from_raw": args.from_raw}, metrics=metrics)
        print("[PASS] Task 1 verified:", metrics)
    finally:
        for frame in owned:
            frame.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
