"""Verify the three full HI-Small Task 3 CSV deliverables and an optional rerun."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.common.run_evidence import verify_run_evidence


EXPECTED_SUMMARY = {
    "dataset": "IBM AML HI-Small", "scope": "full",
    "vertices": 518_581, "edges": 5_078_345, "fraud_edges": 5_177,
    "fraud_cycle_raw_rows": 7_473, "fraud_ordered_account_triples": 162,
    "fraud_directed_account_cycles": 54, "fraud_unordered_account_sets": 45,
    "fraud_transaction_combinations": 2_491, "fraud_cycle_csv_rows": 54,
    "usd_amount_gt": 10_000.0, "usd_cycle_raw_rows": 0,
}
HEADERS = {
    "motif_summary.csv": list(EXPECTED_SUMMARY),
    "fraud_directed_cycles.csv": ["a", "b", "c", "transaction_combinations"],
    "fraud_currency_counts.csv": ["payment_currency", "fraud_edges"],
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_outputs(directory: Path) -> dict[str, list[dict[str, str]]]:
    tables = {}
    for filename, header in HEADERS.items():
        with (directory / filename).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames == header, f"{filename}: unexpected header")
            tables[filename] = list(reader)
        require(all(set(row) == set(header) and all(row.values())
                    for row in tables[filename]), f"{filename}: malformed CSV row")

    summaries = tables["motif_summary.csv"]
    require(len(summaries) == 1, "Expected exactly one full summary")
    summary = summaries[0]
    for name, expected in EXPECTED_SUMMARY.items():
        actual = type(expected)(summary[name])
        require(actual == expected, f"{name}: expected {expected}, got {actual}")

    cycles = tables["fraud_directed_cycles.csv"]
    triples = [(row["a"], row["b"], row["c"]) for row in cycles]
    require(len(triples) == len(set(triples)) == int(summary["fraud_directed_account_cycles"]),
            "Cycle CSV is truncated or contains duplicates")
    require(all(len(set(triple)) == 3 and triple[0] == min(triple) for triple in triples),
            "Cycles require three distinct accounts and the smallest ID first")
    require(len({tuple(sorted(triple)) for triple in triples})
            == int(summary["fraud_unordered_account_sets"]), "Unordered account sets differ")
    combinations = [int(row["transaction_combinations"]) for row in cycles]
    require(all(count > 0 for count in combinations), "Nonpositive edge multiplicity")
    require(sum(combinations) == int(summary["fraud_transaction_combinations"]),
            "Edge combinations differ from summary")
    require(3 * sum(combinations) == int(summary["fraud_cycle_raw_rows"]),
            "Raw motif rows do not reconcile with rotations")
    require(3 * len(triples) == int(summary["fraud_ordered_account_triples"]),
            "Ordered triples do not reconcile with rotations")

    currencies = tables["fraud_currency_counts.csv"]
    require(len(currencies) == len({row["payment_currency"] for row in currencies}) == 15,
            "Expected 15 unique payment currencies")
    counts = [int(row["fraud_edges"]) for row in currencies]
    require(all(count > 0 for count in counts) and sum(counts) == int(summary["fraud_edges"]),
            "Currency counts do not reconcile with fraud edges")
    return tables


def compare_outputs(directory: Path, baseline: Path) -> None:
    actual, expected = verify_outputs(directory), verify_outputs(baseline)
    for filename, header in HEADERS.items():
        actual_rows = sorted(tuple(row[field] for field in header) for row in actual[filename])
        expected_rows = sorted(tuple(row[field] for field in header) for row in expected[filename])
        require(actual_rows == expected_rows,
                f"{filename}: rerun differs from delivered CSV")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results/ibm_aml"))
    parser.add_argument("--compare-dir", type=Path)
    parser.add_argument("--require-evidence", action="store_true")
    args = parser.parse_args()
    if args.compare_dir:
        compare_outputs(args.output_dir, args.compare_dir)
    else:
        verify_outputs(args.output_dir)
    if args.require_evidence:
        verify_run_evidence(args.output_dir / "motif_run.json", task="Task 3 IBM")
    print("[PASS] Full IBM Task 3 CSV counts, rotations, multiplicities and currencies"
          + ("; rerun matches all delivered rows" if args.compare_dir else ""))


if __name__ == "__main__":
    main()
