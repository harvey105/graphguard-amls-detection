"""Verify full PaySim Task 3 CSVs and compare a rerun to the delivered artifacts."""

import argparse
import csv
import math
from pathlib import Path

from src.common.run_evidence import verify_run_evidence


EXPECTED = {
    "dataset": "PaySim", "scope": "full", "vertices": 9_073_900, "edges": 6_362_620,
    "cycle_raw_rows": 0, "cycle_directed_account_cycles": 0,
    "relay_raw_rows": 30, "relay_same_hour_rows": 2, "relay_strict_later_rows": 28,
    "relay_csv_rows": 30, "relay_amount_gt": 10_000.0, "relay_max_gap_hours": 24,
    "relay_time_rule": "transfer_step <= cashout_step; same-hour order unknown",
}
RELAY_FIELDS = ["source_account", "middle_account", "cashout_account", "transfer_step", "cashout_step",
                "transfer_amount", "cashout_amount", "transfer_isFraud", "cashout_isFraud"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path, fields):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == fields, f"{path.name}: unexpected columns")
        rows = list(reader)
    require(all(set(row) == set(fields) and all(row.values()) for row in rows), "Malformed CSV rows")
    return rows


def verify_outputs(directory: Path) -> dict:
    summaries = read_csv(directory / "motif_summary.csv", list(EXPECTED))
    require(len(summaries) == 1, "Expected one full PaySim summary")
    summary = summaries[0]
    for name, expected in EXPECTED.items():
        require(type(expected)(summary[name]) == expected, f"Unexpected {name}")
    rows = read_csv(directory / "relay_candidates.csv", RELAY_FIELDS)
    require(len(rows) == EXPECTED["relay_csv_rows"], "Incomplete relay CSV")
    same_hour = 0
    for row in rows:
        require(len({row[field] for field in RELAY_FIELDS[:3]}) == 3, "Relay requires three distinct accounts")
        transfer, cashout = int(row["transfer_step"]), int(row["cashout_step"])
        require(0 <= cashout - transfer <= EXPECTED["relay_max_gap_hours"], "Invalid relay time window")
        same_hour += transfer == cashout
        for field in ("transfer_amount", "cashout_amount"):
            amount = float(row[field])
            require(math.isfinite(amount) and amount > EXPECTED["relay_amount_gt"], "Invalid relay amount")
        require(int(row["transfer_isFraud"]) in (0, 1) and int(row["cashout_isFraud"]) in (0, 1),
                "Invalid fraud labels")
    require(same_hour == EXPECTED["relay_same_hour_rows"], "Same-hour counts differ")
    return {"motif_summary.csv": summaries, "relay_candidates.csv": rows}


def compare_outputs(directory: Path, baseline: Path):
    actual, expected = verify_outputs(directory), verify_outputs(baseline)
    for name, fields in (("motif_summary.csv", list(EXPECTED)), ("relay_candidates.csv", RELAY_FIELDS)):
        actual_rows = sorted(tuple(row[field] for field in fields) for row in actual[name])
        expected_rows = sorted(tuple(row[field] for field in fields) for row in expected[name])
        require(actual_rows == expected_rows, f"{name}: rerun differs from delivered CSV")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results/paysim"))
    parser.add_argument("--compare-dir", type=Path)
    parser.add_argument("--require-evidence", action="store_true")
    args = parser.parse_args()
    if args.compare_dir:
        compare_outputs(args.output_dir, args.compare_dir)
    else:
        verify_outputs(args.output_dir)
    if args.require_evidence:
        verify_run_evidence(args.output_dir / "motif_run.json", task="Task 3 PaySim")
    print("[PASS] Full PaySim cycle=0; 30 complete relay rows; amount/time rules reconciled"
          + ("; rerun matches delivered CSVs" if args.compare_dir else ""))


if __name__ == "__main__":
    main()
