r"""Draw one documented IBM HI-Small cycle and export its transaction evidence.

Run from the repository root in Windows PowerShell:
    & .\.venv\Scripts\python.exe -m src.ibm_aml.visualize

Uses the tracked Patterns file and motif CSV; no Spark job or new detection rule.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
TIME_FORMAT = "%Y/%m/%d %H:%M"


def read_three_account_cycles(path: Path) -> list[list[dict]]:
    """Read source rows, normalizing bank IDs exactly as the IBM ETL does."""
    cycles = []
    current = None
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if line.startswith("BEGIN LAUNDERING ATTEMPT"):
            current = [] if line == "BEGIN LAUNDERING ATTEMPT - CYCLE:  Max 3 hops" else None
        elif line.startswith("END LAUNDERING ATTEMPT"):
            if current is not None:
                if len(current) != 3:
                    raise ValueError(f"Expected three payments before source line {line_number}")
                cycles.append(current)
            current = None
        elif current is not None and line[:4].isdigit():
            values = next(csv.reader([line]))
            if len(values) != 11:
                raise ValueError(f"Invalid transaction at source line {line_number}")
            current.append({
                "src": f"{int(values[1])}_{values[2]}",
                "dst": f"{int(values[3])}_{values[4]}",
                "timestamp": datetime.strptime(values[0], TIME_FORMAT),
                "amount": Decimal(values[7]),
                "payment_currency": values[8],
                "amount_received": Decimal(values[5]),
                "receiving_currency": values[6],
                "payment_format": values[9],
                "isFraud": int(values[10]),
                "source_line": line_number,
            })
    return cycles


def select_example(cycles: list[list[dict]], cycle_csv: Path) -> list[dict]:
    """Choose the first chronological, same-currency >10k labeled source cycle.

    Require its directed account cycle to appear in the existing motif output.
    The threshold is in the original currency, not a converted USD threshold.
    """
    with cycle_csv.open(newline="", encoding="utf-8-sig") as stream:
        account_cycles = {(r["a"], r["b"], r["c"]) for r in csv.DictReader(stream)}
    for payments in cycles:
        accounts = tuple(payment["src"] for payment in payments)
        if len(set(accounts)) != 3:
            continue
        if any(payments[i]["dst"] != payments[(i + 1) % 3]["src"] for i in range(3)):
            continue
        if not (payments[0]["timestamp"] < payments[1]["timestamp"] < payments[2]["timestamp"]):
            continue
        if not all(p["isFraud"] == 1 and p["amount"] > Decimal("10000") for p in payments):
            continue
        if len({p["payment_currency"] for p in payments}) != 1:
            continue
        rotations = [accounts[i:] + accounts[:i] for i in range(3)]
        if min(rotations) in account_cycles:
            return payments
    raise ValueError("No suitable documented cycle also present in the motif CSV")


def draw_cycle(payments: list[dict], output_path: Path) -> None:
    """Render graph, numbered payments and source/scope notes in one PNG."""
    currency = payments[0]["payment_currency"]
    currency_label = "Saudi Riyal (SAR)" if currency == "Saudi Riyal" else currency
    short_currency = "SAR" if currency == "Saudi Riyal" else currency
    colors = ["#2563eb", "#7c3aed", "#0f766e"]
    positions = [(0.50, 0.85), (0.85, 0.23), (0.15, 0.23)]
    labels = "ABC"
    edge_label_positions = [(0.79, 0.60), (0.50, 0.32), (0.21, 0.60)]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig = plt.figure(figsize=(14, 8.5), facecolor="white")
    try:
        fig.text(0.055, 0.93, "IBM AML: a directed three-account cycle",
                 fontsize=23, weight="bold", color="#0f172a")
        fig.text(0.055, 0.885, "HI-Small  |  One documented synthetic laundering scenario",
                 fontsize=12, color="#475569")
        graph_ax = fig.add_axes((0.055, 0.23, 0.59, 0.60))
        graph_ax.set(xlim=(0, 1), ylim=(0, 1))
        graph_ax.axis("off")
        for i, payment in enumerate(payments):
            graph_ax.add_patch(FancyArrowPatch(
                positions[i], positions[(i + 1) % 3], arrowstyle="-|>",
                mutation_scale=25, linewidth=2.8, color=colors[i],
                shrinkA=45, shrinkB=45, zorder=1,
            ))
            x, y = edge_label_positions[i]
            graph_ax.text(
                x, y, f"{i + 1}  |  {payment['amount']:,.2f} {short_currency}\n"
                f"{payment['timestamp']:%d %b, %H:%M}",
                ha="center", va="center", fontsize=10.5, color=colors[i],
                linespacing=1.6, bbox={"facecolor": "white", "edgecolor": "none", "pad": 5},
            )
        for label, position, payment in zip(labels, positions, payments):
            bank, account = payment["src"].split("_", 1)
            graph_ax.text(
                *position, f"{label}\nBank {bank}\n{account}", ha="center", va="center",
                fontsize=11, weight="bold", color="#0f172a", linespacing=1.65,
                bbox={"boxstyle": "round,pad=0.75", "facecolor": "#f1f5f9",
                      "edgecolor": "#94a3b8", "linewidth": 1.2}, zorder=3,
            )
        graph_ax.text(0.5, 0.50, "A → B → C → A\n3 accounts · 3 payments",
                      ha="center", va="center", color="#475569", fontsize=12,
                      linespacing=1.8)

        detail_ax = fig.add_axes((0.70, 0.245, 0.25, 0.585))
        detail_ax.set(xlim=(0, 1), ylim=(0, 1))
        detail_ax.axis("off")
        detail_ax.text(0.02, 0.98, "PAYMENT SEQUENCE", fontsize=11,
                       color="#475569", weight="bold", va="top")
        for i, payment in enumerate(payments):
            top = 0.89 - i * 0.27
            detail_ax.add_patch(FancyBboxPatch(
                (0.01, top - 0.225), 0.96, 0.22,
                boxstyle="round,pad=0.008", facecolor="#f8fafc", edgecolor="#e2e8f0",
            ))
            detail_ax.text(0.065, top - 0.045,
                           f"{i + 1:02d}   {labels[i]} → {labels[(i + 1) % 3]}",
                           color=colors[i], weight="bold", fontsize=12, va="top")
            detail_ax.text(0.065, top - 0.105,
                           f"{payment['amount']:,.2f} {short_currency}",
                           color="#0f172a", weight="bold", fontsize=15, va="top")
            detail_ax.text(0.065, top - 0.17,
                           f"{payment['timestamp']:%Y-%m-%d %H:%M}  ·  {payment['payment_format']}",
                           color="#475569", fontsize=10, va="top")

        fig.text(0.055, 0.19,
                 f"All three payments: amount > 10,000 in {currency_label}; Is Laundering = 1.",
                 fontsize=11, color="#0f172a")
        fig.text(0.055, 0.15,
                 "Amounts retain their source currency. This is not the USD-only threshold result.",
                 fontsize=10.5, color="#475569")
        fig.text(0.055, 0.095,
                 f"Source: HI-Small_Patterns.txt, transaction lines "
                 f"{payments[0]['source_line']}–{payments[-1]['source_line']}. "
                 "Account IDs use normalized bank_account keys.",
                 fontsize=9, color="#64748b")
        fig.text(0.055, 0.060,
                 "The account cycle also appears in fraud_directed_cycles.csv. "
                 "A labeled scenario is not an independent fraud finding.",
                 fontsize=9, color="#64748b")
        fig.savefig(output_path, dpi=300, facecolor="white")
    finally:
        plt.close(fig)


def run(patterns_path: Path, cycle_csv: Path, output_dir: Path) -> Path:
    payments = select_example(read_three_account_cycles(patterns_path), cycle_csv)
    # Select and validate before creating outputs; missing evidence fails explicitly.
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_rows = []
    for i, payment in enumerate(payments, 1):
        evidence_rows.append({
            "edge_order": i, **payment,
            "timestamp": payment["timestamp"].strftime("%Y-%m-%d %H:%M"),
            "source_file": patterns_path.name,
        })
    evidence_path = output_dir / "cycle_example_edges.csv"
    with evidence_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, list(evidence_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(evidence_rows)
    image_path = output_dir / "cycle_examples.png"
    draw_cycle(payments, image_path)
    print(f"[PASS] Documented cycle: {' -> '.join(p['src'] for p in payments)} -> {payments[0]['src']}")
    print(f"[PASS] Figure: {image_path}")
    print(f"[PASS] Transaction evidence: {evidence_path}")
    return image_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patterns", type=Path,
                        default=ROOT / "data/raw/ibm_aml/HI-Small_Patterns.txt")
    parser.add_argument("--cycles", type=Path,
                        default=ROOT / "results/ibm_aml/fraud_directed_cycles.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/ibm_aml")
    args = parser.parse_args()
    run(args.patterns.resolve(), args.cycles.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
