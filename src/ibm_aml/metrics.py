"""IBM adapter for the shared degree/PageRank implementation and Windows CLI."""
from pathlib import Path

from src.paysim.metrics import (
    calculate_degree_metrics, calculate_degree_distribution, calculate_pagerank,
    get_top10_pagerank, snapshot_features, main_for,
)
from src.paysim import metrics as shared

INPUT_DIR = Path("data/processed/sample/ibm_aml")
OUTPUT_DIR = Path("results/ibm_aml")


def load_graph(spark, input_dir=INPUT_DIR):
    return shared.load_graph(spark, input_dir)


def plot_degree_distribution(distribution, output_path=None):
    return shared.plot_degree_distribution(distribution, output_path or OUTPUT_DIR / "degree_distribution.png", "ibm_aml")


def export_top10_csv(top10, output_path=None):
    return shared.export_top10_csv(top10, output_path or OUTPUT_DIR / "top10_pagerank.csv")


def main():
    main_for("ibm_aml")


if __name__ == "__main__":
    main()
