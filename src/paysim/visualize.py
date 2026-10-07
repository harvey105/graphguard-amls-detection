r"""
Visualization module - ve hinh cho report Part B cua PaySim.

Usage:
    & .\.venv\Scripts\python.exe -m src.paysim.visualize --task degree
    & .\.venv\Scripts\python.exe -m src.paysim.visualize --task relay
"""
import argparse
import csv
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from src.common.graph_utils import load_graph
from src.common.spark_session import get_graph_session

ROOT = Path(__file__).resolve().parents[2]
REPORT_ACCOUNTS = ("C1933517957", "C1939958280", "C232785081")


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


def read_example(path: Path) -> tuple[dict, int]:
    """Locate the report's account triple and validate the exported candidate."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for source_row, row in enumerate(csv.DictReader(stream), 2):
            accounts = tuple(row[k] for k in (
                "source_account", "middle_account", "cashout_account"
            ))
            if accounts != REPORT_ACCOUNTS:
                continue
            example = dict(row)
            for key in ("transfer_amount", "cashout_amount"):
                example[key] = Decimal(row[key])
                if not example[key].is_finite() or example[key] <= 10_000:
                    raise ValueError(f"Invalid relay amount in CSV row {source_row}")
            for key in ("transfer_step", "cashout_step", "transfer_isFraud", "cashout_isFraud"):
                example[key] = int(row[key])
            gap = example["cashout_step"] - example["transfer_step"]
            if len(set(accounts)) != 3 or not 0 <= gap <= 24:
                raise ValueError(f"Invalid accounts or time window in CSV row {source_row}")
            if any(example[k] not in (0, 1) for k in ("transfer_isFraud", "cashout_isFraud")):
                raise ValueError(f"Invalid fraud label in CSV row {source_row}")
            return example, source_row
    raise ValueError("The report's relay example is absent from the candidate CSV")


def plot_relay(example: dict, output_path: Path) -> None:
    """Show three accounts, two payments and their fraud labels."""
    accounts = [example[k] for k in ("source_account", "middle_account", "cashout_account")]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig = plt.figure(figsize=(12, 3.8), facecolor="white")
    try:
        fig.suptitle("PaySim: a two-hop relay", fontsize=20,
                     weight="bold", color="#0f172a", y=0.94)
        ax = fig.add_axes((0.04, 0.13, 0.92, 0.65))
        ax.set(xlim=(-0.025, 1.025), ylim=(0, 1))
        ax.axis("off")
        for i, (name, color) in enumerate((("TRANSFER", "#2563eb"), ("CASH_OUT", "#7c3aed"))):
            prefix = "transfer" if i == 0 else "cashout"
            center = 0.3 + i * 0.4
            ax.add_patch(FancyArrowPatch(
                (center - 0.09, 0.30), (center + 0.09, 0.30),
                arrowstyle="-|>", mutation_scale=25, linewidth=3,
                color=color, shrinkA=0, shrinkB=0,
            ))
            ax.text(center, 0.86, name, ha="center", color=color,
                    fontsize=12, weight="bold")
            ax.text(center, 0.69, f"{example[prefix + '_amount']:,.2f}",
                    ha="center", color="#0f172a", fontsize=14, weight="bold")
            ax.text(center, 0.53, f"step {example[prefix + '_step']}",
                    ha="center", color="#475569", fontsize=11)
        for label, account, x in zip("ABC", accounts, (0.1, 0.5, 0.9)):
            ax.add_patch(FancyBboxPatch(
                (x - 0.1, 0.15), 0.2, 0.30, boxstyle="round,pad=0.008",
                facecolor="#f1f5f9", edgecolor="#94a3b8", linewidth=1.2,
            ))
            ax.text(x, 0.34, label, ha="center", va="center", fontsize=14,
                    weight="bold", color="#0f172a")
            ax.text(x, 0.22, account, ha="center", va="center", fontsize=11,
                    weight="bold", color="#0f172a")
        transfer_fraud = example["transfer_isFraud"]
        cashout_fraud = example["cashout_isFraud"]
        fraud_note = (
            f"isFraud = {transfer_fraud} (both transactions)"
            if transfer_fraud == cashout_fraud
            else f"isFraud: TRANSFER = {transfer_fraud}, CASH_OUT = {cashout_fraud}"
        )
        fig.text(0.5, 0.10, fraud_note, ha="center", fontsize=11, color="#475569")
        fig.savefig(output_path, dpi=300, facecolor="white")
    finally:
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task", choices=["degree", "pagerank", "all", "relay"], default="all"
    )
    parser.add_argument("--input", default="data/processed/sample/paysim")
    parser.add_argument("--output-dir", type=Path,
                        help="Default: results/paysim for relay; results/paysim/figures otherwise")
    parser.add_argument("--relay-csv", type=Path,
                        default=ROOT / "results/paysim/relay_candidates.csv")
    args = parser.parse_args()

    # Resolve before the shared Windows runtime changes the working directory.
    paysim_input = Path(args.input).resolve()
    output_dir = (args.output_dir or ROOT / (
        "results/paysim" if args.task == "relay" else "results/paysim/figures"
    )).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.task == "relay":
        source_path = args.relay_csv.resolve()
        example, _ = read_example(source_path)
        plot_relay(example, output_dir / "relay_example.png")
        print(f"[PASS] Relay figure: {output_dir / 'relay_example.png'}")
        return
    spark = get_graph_session("Viz-PaySim")
    try:
        graph = load_graph(spark, str(paysim_input))
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
