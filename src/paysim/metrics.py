"""Task 2 - Degree Distribution & PageRank (PaySim).

Người phụ trách: N6. Deadline: 4/10/2026.

Input:
    data/processed/sample/paysim/

Output:
    results/paysim/top10_pagerank.csv
    results/paysim/degree_distribution.png

Interpretation:
    PageRank cao phản ánh mức độ quan trọng về mặt cấu trúc mạng lưới,
    không đồng nghĩa với tài khoản gian lận.
"""

from pathlib import Path

import matplotlib

# The Agg backend writes PNG files without opening a GUI window in PowerShell.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, StrMethodFormatter #
from graphframes import GraphFrame
from pyspark.sql import functions as F

from src.common.spark_session import get_graph_session


# ============================================================
# Paths
# ============================================================

INPUT_DIR = Path("data/processed/sample/paysim")
OUTPUT_DIR = Path("results/paysim")

VERTICES_PATH = INPUT_DIR / "vertices.parquet"
EDGES_PATH = INPUT_DIR / "edges.parquet"

TOP10_OUTPUT = OUTPUT_DIR / "top10_pagerank.csv"
DEGREE_FIGURE = OUTPUT_DIR / "degree_distribution.png"


# ============================================================
# Load Graph
# ============================================================

def load_graph(spark, input_dir=INPUT_DIR) -> GraphFrame:
    """Load PaySim vertices/edges from Parquet and create GraphFrame."""

    # Read existing Task 1 data, preserving its schema without regenerating Parquet.
    # GraphFrame uses id for accounts and src/dst for directed edge endpoints.
    vertices = spark.read.parquet(str(Path(input_dir) / "vertices.parquet"))
    edges = spark.read.parquet(str(Path(input_dir) / "edges.parquet"))

    print("\n=== PaySim Graph ===")
    print(f"Vertices: {vertices.count():,}")
    print(f"Edges:    {edges.count():,}")

    print("\nVertex schema:")
    vertices.printSchema()

    print("\nEdge schema:")
    edges.printSchema()

    return GraphFrame(vertices, edges)


# ============================================================
# Degree Metrics
# ============================================================

def calculate_degree_metrics(graph: GraphFrame):
    """Calculate In-Degree, Out-Degree and Total Degree."""

    # Each edge is a transaction: inDegree counts incoming edges, outDegree outgoing ones.
    # degree = inDegree + outDegree; it does not count unique counterparties.
    # GraphFrames degree tables omit vertices with no edges of the corresponding kind.
    in_degrees = graph.inDegrees
    out_degrees = graph.outDegrees
    degrees = graph.degrees

    # Sort by descending metric, breaking ties by ascending account ID.
    # show is a Spark action: it triggers computation and prints results to the terminal.
    print("\n=== Top 10 In-Degree ===")
    (
        in_degrees
        .orderBy(F.desc("inDegree"), F.asc("id"))
        .show(10, truncate=False)
    )

    print("\n=== Top 10 Out-Degree ===")
    (
        out_degrees
        .orderBy(F.desc("outDegree"), F.asc("id"))
        .show(10, truncate=False)
    )

    print("\n=== Top 10 Total Degree ===")
    (
        degrees
        .orderBy(F.desc("degree"), F.asc("id"))
        .show(10, truncate=False)
    )

    return in_degrees, out_degrees, degrees


# ============================================================
# Degree Distribution
# ============================================================

def calculate_degree_distribution(degrees):
    """Count how many accounts occur at each total-degree value."""

    # Each degrees row represents one account; count(*) counts accounts at each degree.
    # For example, degree=2 and account_count=5700 means 5,700 accounts have total degree 2.
    # This distribution uses graph.degrees, which excludes isolated vertices (degree=0).
    return (
        degrees
        .groupBy("degree")
        .agg(F.count("*").alias("account_count"))
        .orderBy("degree")
    )


def plot_degree_distribution(degree_distribution, output_path=None, dataset="paysim", scope="sample"):
    """Plot discrete degrees with readable counts and a logarithmic Y axis."""

    output_path = Path(output_path or DEGREE_FIGURE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect only the aggregated distribution into Python memory for plotting.
    pdf = degree_distribution.toPandas()

    fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
    fig.set_facecolor("white")
    ax.set_facecolor("#f8fafc")

    # Stems start at 1 because log(0) is undefined; markers show the actual counts.
    ax.vlines(pdf["degree"], 1, pdf["account_count"],
              color="#93c5fd", linewidth=3, zorder=2)
    ax.scatter(pdf["degree"], pdf["account_count"], s=90,
               color="#1d4ed8", edgecolors="white", linewidths=1.5, zorder=3)

    # Degrees are integers, so keep a linear X axis with integer ticks.
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    # Label individual points only for small distributions to avoid overlapping text.
    if len(pdf) <= 20:
        ax.set_xticks(pdf["degree"])
        for degree, count in pdf.itertuples(index=False, name=None):
            ax.annotate(f"{count:,}", (degree, count),
                        xytext=(0, 12), textcoords="offset points",
                        ha="center", fontsize=11, fontweight="bold",
                        color="#0f172a")

    # Log scale is for visualization only: each decade on Y represents a tenfold increase.
    # Degrees, counts, PageRank and CSV values are unchanged; labels show actual counts.
    if dataset == "ibm_aml":
        ax.set_xscale("log")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.minorticks_off()
    ax.set_ylim(bottom=0.7, top=max(10, pdf["account_count"].max() * 4))
    ax.margins(x=0.1)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#cbd5e1", linestyle="--", alpha=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cbd5e1")
    ax.tick_params(axis="both", labelsize=11)
    ax.set_xlabel("Total degree (log scale)" if dataset == "ibm_aml" else "Total degree (linear scale)", fontsize=12, labelpad=10)
    ax.set_ylabel("Number of accounts (log scale)", fontsize=12, labelpad=10)
    ax.set_title(
        f"{dataset} Degree Distribution\n"
        f"{scope}: {pdf['account_count'].sum():,} accounts | "
        "Log scale used for visualization only",
        fontsize=14, pad=18,
    )

    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print("\nSaved degree distribution figure:")
    print(f"  {output_path}")


# ============================================================
# PageRank
# ============================================================

def calculate_pagerank(graph: GraphFrame):
    """Run PageRank with the parameters required by the assignment."""

    print("\n=== Running PageRank ===")
    print("resetProbability = 0.15")
    print("maxIter           = 10")

    # PageRank measures structural importance based on directed links.
    # resetProbability=0.15 is the probability of restarting the random walk.
    # maxIter=10 runs exactly 10 iterations as required, without tolerance-based stopping.
    # High PageRank does not imply fraud: do not use this score to label accounts as fraud.
    pagerank_graph = graph.pageRank(
        resetProbability=0.15,
        maxIter=10,
    )

    return pagerank_graph.vertices


def get_top10_pagerank(
    pagerank_vertices,
    in_degrees,
    out_degrees,
    degrees,
):
    """Return Top 10 PageRank hubs together with degree metrics."""

    # Left joins preserve accounts and their original attributes in the PageRank results.
    # Missing degree entries mean no corresponding edges; fill with 0 to retain the account.
    top10 = (
        pagerank_vertices
        .join(in_degrees, on="id", how="left")
        .join(out_degrees, on="id", how="left")
        .join(degrees, on="id", how="left")
        .fillna({
            "inDegree": 0,
            "outDegree": 0,
            "degree": 0,
        })
        # Break ties by ID so the terminal and CSV use the same Top 10 ordering.
        .orderBy(F.desc("pagerank"), F.asc("id"))
        .limit(10)
    )

    return top10


# ============================================================
# Export
# ============================================================

def export_top10_csv(top10, output_path=None):
    """Export Top 10 PageRank results as a single CSV file."""

    output_path = Path(output_path or TOP10_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect at most 10 rows; pandas writes one CSV file instead of a Spark part-* directory.
    pdf = top10.limit(10).toPandas()
    if len(pdf) != 10:
        raise ValueError("Expected ten PageRank accounts")

    # rank is only the display order, not a new feature or risk score.
    pdf.insert(0, "rank", range(1, len(pdf) + 1))

    # Omit the pandas index; the UTF-8 BOM helps Windows Excel read Vietnamese correctly.
    pdf.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nSaved Top 10 PageRank CSV:")
    print(f"  {output_path}")


# ============================================================
# Main
# ============================================================

def snapshot_features(edges, as_of_step):
    """Label-blind account features from transactions observed by the cutoff."""
    from src.motif.evaluation import require_unlabelled
    require_unlabelled(edges)
    past = edges.where(F.col("step") <= as_of_step).select("src", "dst")
    ids = past.select(F.col("src").alias("id")).union(past.select(F.col("dst").alias("id"))).distinct()
    graph = GraphFrame(ids, past)
    pagerank = calculate_pagerank(graph)
    try:
        return (ids.join(graph.inDegrees, "id", "left").join(graph.outDegrees, "id", "left")
            .fillna(0, subset=["inDegree", "outDegree"])
            .withColumn("degree", F.col("inDegree") + F.col("outDegree"))
            .join(pagerank.select("id", "pagerank"), "id")
            .withColumn("as_of_step", F.lit(int(as_of_step))).localCheckpoint(eager=True))
    finally:
        pagerank.unpersist()


def main_for(dataset="paysim"):
    """Shared runner; dataset adapters only choose paths and presentation names."""
    import argparse
    from src.common.graph_utils import load_graph as read_graph, write_spark_csv
    from src.common.run_evidence import REPO_ROOT, write_run_evidence

    parser = argparse.ArgumentParser(description="Task 2: degree and PageRank")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--full", action="store_true", help="Full is the default; retained for compatibility")
    parser.add_argument("--sample", action="store_true", help="Explicit development sample only")
    parser.add_argument("--driver-memory", default="5g")
    parser.add_argument("--as-of-step", type=int)
    parser.add_argument("--export-features", action="store_true")
    args = parser.parse_args()
    if args.full and (args.input_dir or args.sample):
        parser.error("Choose full, sample or custom input")
    default_input = REPO_ROOT / "data/processed" / ("sample/" + dataset if args.sample else dataset)
    source = (args.input_dir or default_input).resolve()
    scope = "sample" if "sample" in source.parts else ("full" if source == REPO_ROOT / "data/processed" / dataset else "custom")
    output = (args.output_dir or REPO_ROOT / "results" / dataset / ("full" if scope == "full" else "")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    spark = get_graph_session("Task2-" + dataset, driver_memory=args.driver_memory)
    owned = []
    try:
        graph = read_graph(spark, str(source))
        if args.as_of_step is not None:
            past = graph.edges.where(F.col("step") <= args.as_of_step)
            ids = past.select(F.col("src").alias("id")).union(past.select(F.col("dst").alias("id"))).distinct()
            graph = GraphFrame(graph.vertices.join(ids, "id"), past)
        graph.vertices.cache()
        graph.edges.cache()
        owned.extend([graph.vertices, graph.edges])
        vertices, edge_count = graph.vertices.count(), graph.edges.count()
        if vertices < 10 or edge_count == 0:
            raise ValueError("Task 2 needs at least ten accounts and one transaction")
        incoming, outgoing, _ = calculate_degree_metrics(graph)
        degrees = graph.vertices.select("id").join(graph.degrees, "id", "left").fillna(0, subset=["degree"])
        totals = degrees.agg(F.sum("degree").alias("total")).first()
        if totals.total != 2 * edge_count:
            raise ValueError("Degree sum must equal twice the transaction count")
        distribution = calculate_degree_distribution(degrees)
        plot_degree_distribution(distribution.where("degree>0"), output / "degree_distribution.png", dataset, scope)
        if scope == "sample":
            ranks = calculate_pagerank(graph).localCheckpoint(eager=True)
        else:
            import uuid
            ranks = dataframe_pagerank(graph.vertices.select("id"), graph.edges.select("src", "dst"),
                output / ".work" / ("pagerank_"+uuid.uuid4().hex))
        owned.append(ranks)
        top10 = get_top10_pagerank(ranks, incoming, outgoing, degrees)
        # Audit labels only after the structural top ten has already been chosen.
        fraud_out = graph.edges.groupBy("src").agg(F.sum("isFraud").alias("outgoing_fraud_tx")).withColumnRenamed("src", "id")
        fraud_in = graph.edges.groupBy("dst").agg(F.sum("isFraud").alias("incoming_fraud_tx")).withColumnRenamed("dst", "id")
        top10 = top10.join(fraud_out, "id", "left").join(fraud_in, "id", "left").fillna(
            0, subset=["outgoing_fraud_tx", "incoming_fraud_tx"]).orderBy(F.desc("pagerank"), "id")
        export_top10_csv(top10, output / "top10_pagerank.csv")
        write_spark_csv(distribution, output / "degree_distribution.csv")
        outputs = [output / name for name in ("top10_pagerank.csv", "degree_distribution.csv", "degree_distribution.png")]
        if args.export_features:
            features = ranks.select("id", "pagerank").join(incoming, "id", "left").join(outgoing, "id", "left")
            features = features.fillna(0, subset=["inDegree", "outDegree"]).withColumn("degree", F.col("inDegree") + F.col("outDegree"))
            as_of = args.as_of_step if args.as_of_step is not None else graph.edges.agg(F.max("step")).first()[0]
            features = features.withColumn("as_of_step", F.lit(as_of))
            write_spark_csv(features.repartition(64), output / "account_metrics.csv")
            outputs.append(output / "account_metrics.csv")
        write_run_evidence(output / "task2_run.json", spark, task="Task 2 " + dataset,
            inputs=[source], outputs=outputs,
            sources=[Path(__file__), REPO_ROOT / "src/ibm_aml/metrics.py", REPO_ROOT / "src/common/graph_utils.py"],
            parameters={"scope": scope, "max_iter": 10, "reset_probability": 0.15,
                        "as_of_step": args.as_of_step, "export_features": args.export_features},
            metrics={"vertices": vertices, "edges": edge_count, "degree_sum": totals.total,
                     "interpretation": "Structural centrality; fraud evaluation is a separate temporal protocol"})
        print("[PASS] Task 2:", dataset, scope, vertices, edge_count)
    finally:
        for frame in owned:
            frame.unpersist()
        spark.stop()


def main():
    main_for("paysim")




def dataframe_pagerank(vertices, edges, checkpoint_dir, iterations=10, reset_probability=0.15):
    """Fixed-iteration GraphX-equivalent PageRank using disk-backed SQL joins.

    Preserve parallel edges and self-loops; start at one, use alpha per vertex,
    and apply the GraphX final normalization to sum=N. No dangling redistribution
    is inserted between iterations. Checkpoints bound lineage and JVM heap.
    """
    from src.motif.evaluation import require_unlabelled
    require_unlabelled(edges)
    if iterations <= 0 or not 0 < reset_probability < 1:
        raise ValueError("Invalid PageRank iteration/reset parameters")
    root = Path(checkpoint_dir)
    root.mkdir(parents=True, exist_ok=True)
    spark = vertices.sparkSession
    ids = vertices.select("id")
    links = edges.groupBy("src", "dst").agg(F.count("*").cast("double").alias("multiplicity"))
    outgoing = links.groupBy("src").agg(F.sum("multiplicity").alias("outgoing"))
    weights = links.join(outgoing, "src").select("src", "dst", (F.col("multiplicity") / F.col("outgoing")).alias("weight"))
    weights.write.parquet(str(root / "weights"))
    weights = spark.read.parquet(str(root / "weights"))
    ranks = ids.withColumn("pagerank", F.lit(1.0))
    for index in range(iterations):
        incoming = (weights.join(ranks.select(F.col("id").alias("src"), "pagerank"), "src")
            .groupBy("dst").agg(F.sum(F.col("pagerank") * F.col("weight")).alias("incoming")))
        updated = (ids.join(incoming.withColumnRenamed("dst", "id"), "id", "left")
            .select("id", (F.lit(reset_probability) + (1-reset_probability) * F.coalesce(F.col("incoming"), F.lit(0.0))).alias("pagerank")))
        path = root / f"iteration_{index+1:02d}"
        updated.write.parquet(str(path))
        ranks = spark.read.parquet(str(path))
        print(f"[SYSTEM] PageRank iteration {index+1}/{iterations} persisted", flush=True)
        if index:
            import shutil
            shutil.rmtree(root / f"iteration_{index:02d}", ignore_errors=True)
    totals = ranks.agg(F.count("*").alias("n"), F.sum("pagerank").alias("rank_sum")).first()
    if not totals.n or not totals.rank_sum:
        raise ValueError("PageRank requires nonempty vertex support")
    return ranks.withColumn("pagerank", F.col("pagerank") * F.lit(totals.n / totals.rank_sum))

if __name__ == "__main__":
    main()
