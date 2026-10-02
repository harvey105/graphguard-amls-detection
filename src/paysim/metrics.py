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

def load_graph(spark) -> GraphFrame:
    """Load PaySim vertices/edges from Parquet and create GraphFrame."""

    # Read existing Task 1 data, preserving its schema without regenerating Parquet.
    # GraphFrame uses id for accounts and src/dst for directed edge endpoints.
    vertices = spark.read.parquet(str(VERTICES_PATH))
    edges = spark.read.parquet(str(EDGES_PATH))

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


def plot_degree_distribution(degree_distribution):
    """Plot discrete degrees with readable counts and a logarithmic Y axis."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    ax.set_xlabel("Total degree (in-degree + out-degree; log scale)", fontsize=12, labelpad=10)
    ax.set_ylabel("Number of accounts (log scale)", fontsize=12, labelpad=10)
    ax.set_title(
        "PaySim Degree Distribution\n"
        f"Sample: {pdf['account_count'].sum():,} accounts | "
        "Log scale used for visualization only",
        fontsize=14, pad=18,
    )

    fig.savefig(DEGREE_FIGURE, dpi=300)
    plt.close(fig)

    print("\nSaved degree distribution figure:")
    print(f"  {DEGREE_FIGURE}")


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

def export_top10_csv(top10):
    """Export Top 10 PageRank results as a single CSV file."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect at most 10 rows; pandas writes one CSV file instead of a Spark part-* directory.
    pdf = top10.toPandas()

    # rank is only the display order, not a new feature or risk score.
    pdf.insert(0, "rank", range(1, len(pdf) + 1))

    # Omit the pandas index; the UTF-8 BOM helps Windows Excel read Vietnamese correctly.
    pdf.to_csv(
        TOP10_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nSaved Top 10 PageRank CSV:")
    print(f"  {TOP10_OUTPUT}")


# ============================================================
# Main
# ============================================================

def main():
    # Reuse the shared session for the repository's Windows, Java and GraphFrames setup.
    spark = get_graph_session(
        app_name="PaySim-Task2-Degree-PageRank",
        driver_memory="4g",
        shuffle_partitions=8,
    )

    try:
        # 1. Build GraphFrame from processed PaySim sample.
        graph = load_graph(spark)

        # 2. Structural degree metrics.
        in_degrees, out_degrees, degrees = calculate_degree_metrics(graph)

        # 3. Degree distribution.
        degree_distribution = calculate_degree_distribution(degrees)

        print("\n=== Degree Distribution Sample ===")
        degree_distribution.show(20, truncate=False)

        plot_degree_distribution(degree_distribution)

        # 4. PageRank.
        pagerank_vertices = calculate_pagerank(graph)

        # 5. Top 10 influential structural hubs.
        top10 = get_top10_pagerank(
            pagerank_vertices,
            in_degrees,
            out_degrees,
            degrees,
        )

        print("\n=== Top 10 PageRank Hubs ===")
        top10.show(10, truncate=False)

        # 6. Export deliverable.
        export_top10_csv(top10)

        print(
            "\nInterpretation caveat:\n"
            "High PageRank indicates structural importance in the "
            "transaction network. High PageRank does not imply fraud."
        )

    finally:
        # Always release Spark resources, including when computation or export fails.
        spark.stop()


if __name__ == "__main__":
    main()
