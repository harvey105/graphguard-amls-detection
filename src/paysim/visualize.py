"""
Visualization module - ve hinh cho report Part B cua PaySim.

Usage:
    python -m src.paysim.visualize --task degree --input data/processed/sample/paysim
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["degree", "pagerank", "all"], default="all")
    parser.add_argument("--input", default="data/processed/sample/paysim")
    parser.add_argument("--output-dir", default="results/paysim/figures")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    spark = get_graph_session("Viz-PaySim")
    graph = load_graph(spark, args.input)

    if args.task in ("degree", "all"):
        print("[*] Computing degrees...")
        degrees = graph.degrees
        plot_degree_distribution(
            degrees,
            f"{args.output_dir}/degree_distribution.png",
        )

    if args.task in ("pagerank", "all"):
        print("[*] Running PageRank (reset=0.15, maxIter=10)...")
        pr = graph.pageRank(resetProbability=0.15, maxIter=10)
        pr.vertices.select("id", "pagerank").orderBy(
            "pagerank", ascending=False
        ).limit(10).write.mode("overwrite").csv(
            f"{args.output_dir}/top10_pagerank.csv", header=True
        )
        top10 = pr.vertices.select("id", "pagerank").orderBy(
            "pagerank", ascending=False
        )
        plot_top_pagerank(top10, f"{args.output_dir}/top10_pagerank.png")

    print("[+] Done")


if __name__ == "__main__":
    main()
