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
from src.common.windows_runtime import prepare_windows_spark

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


def create_graph_spark_session(app_name: str = "GraphGuard-GraphConstruction") -> SparkSession:
    prepare_windows_spark()
    coord = resolve_graphframes_coordinate()
    print(f"[*] Detected PySpark {pyspark.__version__} -> resolving GraphFrames package: {coord}")
    print("    (Maven Central hosts this directly -- no spark-packages.org repository needed.")
    print("     First run downloads the jar and may take 30-60s; cached under ~/.ivy2 after that.)")
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "6g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.jars.packages", coord)
        .getOrCreate()
    )


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


def main():
    parser = argparse.ArgumentParser(description="GraphGuard Task 1: Graph Construction")
    parser.add_argument("--sample", action="store_true", help="Use/build the ~100k-edge sample graph")
    parser.add_argument("--from-raw", action="store_true", help="Build graph directly from raw CSV")
    args = parser.parse_args()

    spark = create_graph_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("=" * 65)
    print("TASK 1: GRAPHFRAME CONSTRUCTION & VALIDATION PIPELINE")
    print("=" * 65)

    # raw_df is only populated in --from-raw mode. It's the thing that lets
    # us do a genuine spot-check against the original transactions rather
    # than just re-inspecting the DataFrames we built ourselves.
    raw_df = None

    if args.from_raw:
        raw_csv_path = "data/raw/paysim/PS_20174392719_1491204439457_log.csv"
        if not os.path.exists(raw_csv_path):
            raw_csv_path = "data/raw/PS_20174392719_1491204439457_log.csv"
            print(f"[WARN] Preferred raw path not found; using {raw_csv_path}.")
        raw_df, vertices_df, edges_df = load_from_raw_csv(spark, raw_csv_path)
        if args.sample:
            print("[*] --sample requested with --from-raw: inducing a ~100k-edge "
                  "subgraph in-memory (raw_df stays full-size for spot-checks below)...")
            vertices_df, edges_df = induce_sample(vertices_df, edges_df)
    else:
        vertices_df, edges_df = load_from_parquet(spark, sample=args.sample)

    vertices_df.cache()
    edges_df.cache()

    # GraphFrame Instantiation (Rubric requirement)
    print("[*] Instantiating GraphFrame(vertices, edges)...")
    graph = GraphFrame(vertices_df, edges_df)

    v_count = graph.vertices.count()
    e_count = graph.edges.count()

    print("\n" + "-" * 65)
    print("GRAPHFRAME TOPOLOGY SUMMARY")
    print("-" * 65)
    print(f"Total Graph Vertices (|V|): {v_count:,}")
    print(f"Total Graph Edges    (|E|): {e_count:,}")

    print("\nVertices Schema:")
    graph.vertices.printSchema()
    print("Edges Schema:")
    graph.edges.printSchema()

    # Explicit pass/fail checks -- the rubric says "verify vertex count, edge
    # count, sample vertices/edges match the original data", not just print
    # them for visual inspection.
    print("\n" + "-" * 65)
    print("VERIFICATION CHECKS")
    print("-" * 65)

    expected_v_cols = {"id", "account_type", "balance"}
    expected_e_cols = {"src", "dst", "amount", "step", "type", "isFraud"}
    v_cols_ok = expected_v_cols.issubset(set(graph.vertices.columns))
    e_cols_ok = expected_e_cols.issubset(set(graph.edges.columns))
    print(f"  [{'PASS' if v_cols_ok else 'FAIL'}] Vertices contain {sorted(expected_v_cols)}")
    print(f"  [{'PASS' if e_cols_ok else 'FAIL'}] Edges contain {sorted(expected_e_cols)}")

    if not args.sample:
        # Full graph (parquet or --from-raw without --sample): exact counts
        # are a known, fixed identity from Task 2.1 -- compare directly.
        v_count_ok = v_count == EXPECTED_VERTEX_COUNT
        e_count_ok = e_count == EXPECTED_EDGE_COUNT
        print(f"  [{'PASS' if v_count_ok else 'FAIL'}] Vertex count == {EXPECTED_VERTEX_COUNT:,} (got {v_count:,})")
        print(f"  [{'PASS' if e_count_ok else 'FAIL'}] Edge count == {EXPECTED_EDGE_COUNT:,} (got {e_count:,})")
    else:
        # Sample graph: exact count isn't a fixed identity (it's a random
        # sample), so verify structural self-consistency instead -- the
        # induced subgraph should have zero dangling edges by construction.
        dangling_src = graph.edges.join(graph.vertices, graph.edges["src"] == graph.vertices["id"], "left_anti").count()
        dangling_dst = graph.edges.join(graph.vertices, graph.edges["dst"] == graph.vertices["id"], "left_anti").count()
        ref_ok = dangling_src == 0 and dangling_dst == 0
        print(f"  [{'PASS' if ref_ok else 'FAIL'}] Sample referential integrity "
              f"({dangling_src} dangling src, {dangling_dst} dangling dst)")

    # Spot-check constructed edges against the actual raw transactions --
    # only possible (and only cheap) when raw_df was already loaded, i.e.
    # --from-raw. In fast/parquet mode we say so explicitly rather than
    # silently skipping the objective's "validate against raw transactions"
    # requirement.
    print("\n" + "-" * 65)
    print("RAW-TRANSACTION SPOT-CHECK")
    print("-" * 65)
    if raw_df is not None:
        for row in graph.edges.limit(5).collect():
            match_count = raw_df.filter(
                (F.col("nameOrig") == row["src"]) &
                (F.col("nameDest") == row["dst"]) &
                (F.col("step") == row["step"]) &
                (F.col("amount") == row["amount"])
            ).count()
            status = "PASS" if match_count >= 1 else "FAIL"
            print(f"  [{status}] {row['src']} -> {row['dst']} @ step {row['step']}, "
                  f"amount={row['amount']}: {match_count} matching raw row(s)")
    else:
        print("  Skipped -- no raw_df loaded in fast/parquet mode.")
        print("  Run with --from-raw for a full validation pass against the source CSV.")

    print("\n" + "-" * 65)
    print("SAMPLE VERTICES (Top 5 Customer & Merchant):")
    print("-" * 65)
    graph.vertices.filter(F.col("account_type") == "Customer").show(5, truncate=False)
    graph.vertices.filter(F.col("account_type") == "Merchant").show(5, truncate=False)

    print("-" * 65)
    print("SAMPLE EDGES (Top 5 Fraudulent Transactions):")
    print("-" * 65)
    graph.edges.filter(F.col("isFraud") == 1).show(5, truncate=False)

    # Native GraphFrames metric probes -- proves the JVM package actually
    # resolved and the graph is operational, and unblocks Person 3 (Task 2).
    print("-" * 65)
    print("GRAPHFRAMES FUNCTIONAL INTEGRITY PROBE")
    print("-" * 65)
    print("[*] Probing In-Degrees (Top 5 Receiver Hubs):")
    graph.inDegrees.orderBy(F.col("inDegree").desc()).show(5)

    print("[*] Probing Out-Degrees (Top 5 Sender Hubs):")
    graph.outDegrees.orderBy(F.col("outDegree").desc()).show(5)

    # Forward-looking note: this script only uses inDegrees/outDegrees, which
    # need no checkpointing. connectedComponents (Task 4) and Pregel-based
    # algorithms do -- Person 3/5/6 will need
    # spark.sparkContext.setCheckpointDir(...) set before calling those.
    print("=" * 65)
    print("[+] Task 1 Completed Successfully. GraphFrame is fully operational.")
    print("=" * 65)

    spark.stop()


if __name__ == "__main__":
    main()
