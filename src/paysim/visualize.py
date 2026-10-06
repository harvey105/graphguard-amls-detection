r"""
Visualization module - ve hinh cho report Part B cua PaySim.

Usage:
    & .\.venv\Scripts\python.exe -m src.paysim.visualize --task degree
    & .\.venv\Scripts\python.exe -m src.paysim.visualize --task comparison
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyspark.sql import functions as F

from src.common.graph_utils import load_graph
from src.common.spark_session import get_graph_session


def plot_degree_distribution(degrees_df, output_path):
    """Ve histogram phan phoi bac (linear + log-log)."""
    pdf = degrees_df.toPandas()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.hist(pdf["degree"], bins=50, color="steelblue", edgecolor="black")
    ax1.set_xlabel("Degree")
    ax1.set_ylabel("Number of vertices")
    ax1.set_title("Degree Distribution (linear)")
    ax1.grid(alpha=0.3)

    counts = pdf["degree"].value_counts().sort_index()
    ax2.loglog(counts.index, counts.values, "o", markersize=5, color="coral")
    ax2.set_xlabel("Degree (log)")
    ax2.set_ylabel("Count (log)")
    ax2.set_title("Degree Distribution (log-log, power-law check)")
    ax2.grid(alpha=0.3, which="both")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[+] Saved: {output_path}")


def plot_top_pagerank(pagerank_df, output_path, top_n=10):
    """Ve bar chart top N PageRank."""
    pdf = pagerank_df.toPandas().head(top_n)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(range(len(pdf)), pdf["pagerank"], color="seagreen", edgecolor="black")
    ax.set_yticks(range(len(pdf)))
    ax.set_yticklabels(pdf["id"], fontsize=9)
    ax.set_xlabel("PageRank score")
    ax.set_title(f"Top {top_n} Accounts by PageRank")
    ax.invert_yaxis()
    ax.grid(alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[+] Saved: {output_path}")


def calculate_degree_distribution(graph):
    """Return the positive-degree PMF and the number of all graph vertices."""
    vertex_count = graph.vertices.count()
    if vertex_count == 0:
        raise ValueError("Cannot compare degree distributions of an empty graph.")

    # Aggregate in Spark; collect only one row per distinct degree.
    # Self-loops contribute twice and parallel transaction edges remain distinct.
    distribution = (
        graph.degrees
        .groupBy("degree")
        .agg(F.count("*").alias("account_count"))
        .withColumn("proportion", F.col("account_count") / F.lit(vertex_count))
        .orderBy("degree")
        .toPandas()
    )
    return distribution, vertex_count


def plot_degree_comparison(
    paysim_distribution,
    ibm_distribution,
    output_path,
    paysim_vertex_count,
    ibm_vertex_count,
    scope="Selected graphs",
):
    """Compare empirical Total Degree PMFs on the same log-log axes."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")

    try:
        for name, distribution, vertex_count, color, marker in (
            ("PaySim", paysim_distribution, paysim_vertex_count, "#2563eb", "o"),
            ("IBM AML", ibm_distribution, ibm_vertex_count, "#dc2626", "^"),
        ):
            positive = distribution.loc[distribution["degree"] > 0]
            if positive.empty:
                raise ValueError(f"{name} has no positive degrees to plot on log axes.")
            ax.scatter(
                positive["degree"], positive["proportion"],
                label=f"{name} (N={vertex_count:,})", color=color, marker=marker,
                s=48, alpha=0.85,
            )
            isolated = vertex_count - int(positive["account_count"].sum())
            print(
                f"[*] {name}: vertices={vertex_count:,}, "
                f"max_degree={int(positive['degree'].max()):,}, "
                f"isolated_vertices={isolated:,}"
            )

        # Degree zero cannot be shown on log axes; probabilities still use all vertices.
        # Scatter points avoid implying observations at unobserved degree values.
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Total degree k = in-degree + out-degree (log scale)")
        ax.set_ylabel("Proportion of accounts p(k) = count / N (log scale)")
        ax.set_title(
            "Degree Distribution: PaySim vs IBM AML\n"
            f"{scope}; parallel edges and self-loops retained"
        )
        ax.grid(which="major", linestyle="--", alpha=0.3)
        ax.legend()
        fig.savefig(output_path, dpi=200)
    finally:
        plt.close(fig)
    print(f"[+] Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task", choices=["degree", "pagerank", "all", "comparison"], default="all"
    )
    parser.add_argument("--input", default="data/processed/sample/paysim")
    parser.add_argument(
        "--ibm-input", default="data/processed/sample/ibm_aml",
        help="IBM Parquet directory for --task comparison",
    )
    parser.add_argument(
        "--output-dir",
        help="Default: results/comparison for comparison; results/paysim/figures otherwise",
    )
    args = parser.parse_args()

    # Resolve before the shared Windows runtime changes the working directory.
    paysim_input = Path(args.input).resolve()
    ibm_input = Path(args.ibm_input).resolve()
    output_dir = Path(args.output_dir or (
        "results/comparison" if args.task == "comparison" else "results/paysim/figures"
    )).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    spark = get_graph_session("Viz-PaySim")
    try:
        graph = load_graph(spark, str(paysim_input))
        if args.task == "comparison":
            ibm_graph = load_graph(spark, str(ibm_input))
            paysim_distribution, paysim_count = calculate_degree_distribution(graph)
            ibm_distribution, ibm_count = calculate_degree_distribution(ibm_graph)
            scope = "Sample graphs" if all(
                "sample" in path.parts for path in (paysim_input, ibm_input)
            ) else "Selected graphs"
            plot_degree_comparison(
                paysim_distribution, ibm_distribution,
                output_dir / "degree_distribution_paysim_vs_ibm.png",
                paysim_count, ibm_count, scope=scope,
            )

        if args.task in ("degree", "all"):
            print("[*] Computing degrees...")
            degrees = graph.degrees
            plot_degree_distribution(degrees, output_dir / "degree_distribution.png")

        if args.task in ("pagerank", "all"):
            print("[*] Running PageRank (reset=0.15, maxIter=10)...")
            pr = graph.pageRank(resetProbability=0.15, maxIter=10)
            pr.vertices.select("id", "pagerank").orderBy(
                "pagerank", ascending=False
            ).limit(10).write.mode("overwrite").csv(
                str(output_dir / "top10_pagerank.csv"), header=True
            )
            top10 = pr.vertices.select("id", "pagerank").orderBy(
                "pagerank", ascending=False
            )
            plot_top_pagerank(top10, output_dir / "top10_pagerank.png")

        print("[+] Done")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
