"""Delivered-artifact verification and opt-in temporal component experiments.

The default audit is bounded and starts no Spark. --signals explicitly uses
the protected Windows Spark session and writes a new experiment directory.

Sample references are independent of production analytics. PageRank follows
Spark 3.5.1 PageRank.runWithOptions: ten updates, then rank-sum correction to N.
https://github.com/apache/spark/blob/v3.5.1/graphx/src/main/scala/org/apache/spark/graphx/lib/PageRank.scala
This checks existing evidence, not a new execution of every production module.
"""

from __future__ import annotations

import argparse
import ast
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[2]
MAX_VERTICES = 250_000
MAX_EDGES = 150_000
MAX_RSS = 512 * 1024**2
FULL_COUNTS = {"paysim": (9_073_900, 6_362_620), "ibm_aml": (518_581, 5_078_345)}


class AuditBlocked(RuntimeError):
    """A prerequisite or the bounded audit budget prevents verification."""


def configure_runtime():
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        raise AuditBlocked("Use native Windows repository .venv Python 3.12")
    if not os.path.samefile(sys.executable, ROOT / ".venv/Scripts/python.exe"):
        raise AuditBlocked("Use the repository .venv interpreter")
    import psutil
    import pyarrow as pa

    process = psutil.Process()
    process.cpu_affinity(process.cpu_affinity()[:1])
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)


def check_memory():
    import psutil

    if psutil.Process().memory_info().rss > MAX_RSS:
        raise AuditBlocked("Audit exceeded its 512 MiB RSS budget; no automatic retry")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def csv_rows(path):
    import csv

    if not path.is_file():
        raise AuditBlocked(f"Missing delivered file: {path}")
    if path.stat().st_size > 64 * 1024**2:
        raise AuditBlocked(f"CSV exceeds bounded audit size: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = []
        for index, row in enumerate(csv.DictReader(stream), 1):
            rows.append(row)
            if index % 4096 == 0:
                check_memory()
        return rows


def csv_iter_rows(path):
    import csv
    if not path.is_file():
        raise AuditBlocked(f"Missing delivered file: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream), 1):
            if index % 4096 == 0:
                check_memory()
            yield row


def parquet_info(directory):
    import pyarrow.parquet as pq

    files = sorted(directory.glob("*.parquet")) if directory.is_dir() else [directory]
    if not files or not all(p.is_file() for p in files):
        raise AuditBlocked(f"Missing Parquet input: {directory}")
    count, columns = 0, None
    for path in files:
        file = pq.ParquetFile(path)
        names = file.schema_arrow.names
        require(columns is None or columns == names, f"Inconsistent schemas: {directory}")
        columns = names
        count += file.metadata.num_rows
    return files, count, columns


def parquet_rows(directory, columns, limit):
    import pyarrow.parquet as pq

    files, count, available = parquet_info(directory)
    if count > limit:
        raise AuditBlocked(f"Refusing full-data collection: {count} rows > bounded limit {limit}")
    require(set(columns) <= set(available), f"Missing Parquet fields in {directory}")
    for path in files:
        file = pq.ParquetFile(path)
        for batch in file.iter_batches(batch_size=4096, columns=columns, use_threads=False):
            check_memory()
            yield from batch.to_pylist()


def load_sample(root, dataset):
    directory = root / "data/processed/sample" / dataset
    vertices = {}
    vertex_columns = ["id", "account_type", "balance"] + (["bank_id"] if dataset == "ibm_aml" else [])
    for row in parquet_rows(directory / "vertices.parquet", vertex_columns, MAX_VERTICES):
        require(row["id"] and row["id"] not in vertices, "Duplicate/null sample vertex ID")
        require(math.isfinite(row["balance"]), "Nonfinite vertex balance")
        if dataset == "paysim":
            require(row["account_type"] in {"Customer", "Merchant"}, "Invalid PaySim account_type")
        if dataset == "ibm_aml":
            require(row["bank_id"] and row["id"].startswith(row["bank_id"] + "_"), "Invalid composite bank/account ID")
        vertices[row["id"]] = row
    columns = ["src", "dst", "amount", "step", "isFraud"]
    if dataset == "ibm_aml":
        columns += ["payment_currency"]
    edges = list(parquet_rows(directory / "edges.parquet", columns, MAX_EDGES))
    require(vertices and edges, "Empty sample graph")
    incoming, outgoing = Counter(), Counter()
    for edge in edges:
        require(edge["src"] in vertices and edge["dst"] in vertices, "Dangling sample edge")
        require(math.isfinite(edge["amount"]) and edge["amount"] >= 0, "Invalid sample amount")
        require(edge["isFraud"] in (0, 1) and isinstance(edge["step"], int), "Invalid label/time")
        incoming[edge["dst"]] += 1
        outgoing[edge["src"]] += 1
    check_memory()
    return vertices, edges, incoming, outgoing


def reference_pagerank(vertices, edges, outgoing, iterations=10):
    """Preserve parallel edges/self-loops; use GraphX's final correction to N."""
    ranks = dict.fromkeys(vertices, 1.0)
    for _ in range(iterations):
        updated = dict.fromkeys(vertices, 0.15)
        for edge in edges:
            updated[edge["dst"]] += 0.85 * ranks[edge["src"]] / outgoing[edge["src"]]
        ranks = updated
        check_memory()
    factor = len(vertices) / math.fsum(ranks.values())
    return {key: value * factor for key, value in ranks.items()}


def verify_top10(rows, vertices, edges, incoming, outgoing):
    require(len(rows) == 10 and len({row["id"] for row in rows}) == 10, "Expected ten distinct PageRank accounts")
    ranks = reference_pagerank(vertices, edges, outgoing)
    fraud_in = Counter(edge["dst"] for edge in edges if edge["isFraud"] == 1)
    fraud_out = Counter(edge["src"] for edge in edges if edge["isFraud"] == 1)
    cutoff = sorted(ranks.values(), reverse=True)[9]
    previous = math.inf
    for row in rows:
        key, score = row["id"], float(row["pagerank"])
        require(key in vertices and math.isfinite(score), "Foreign account/nonfinite PageRank")
        require(math.isclose(score, ranks[key], rel_tol=1e-8, abs_tol=1e-8), f"PageRank differs: {key}")
        require(score + 1e-8 >= cutoff and score <= previous + 1e-8, "Top-ten cutoff/order differs")
        previous = score
        for field, expected in (("inDegree", incoming[key]), ("outDegree", outgoing[key]),
                                ("degree", incoming[key] + outgoing[key]),
                                ("outgoing_fraud_tx", fraud_out[key]), ("incoming_fraud_tx", fraud_in[key])):
            require(int(row[field]) == expected, f"{key}: incorrect {field}")
    return {"accounts": 10, "iterations": 10, "reset_probability": 0.15, "tie_policy": "tolerance at cutoff",
            "fraud_audit": "top-ten incident fraud counts reconciled; not a classifier"}


def verify_communities(assignments, summary, vertices, edges, dataset, full_summary=None, currency_amounts=None):
    require(len(assignments) == len(vertices), "Assignments do not cover sample vertices")
    labels, members, types, balances = {}, Counter(), defaultdict(Counter), defaultdict(list)
    banks = defaultdict(set)
    for row in assignments:
        key = row["id"]
        require(key in vertices and key not in labels, "Duplicate/foreign assigned account")
        label = int(row["label"])
        require(row["account_type"] == vertices[key]["account_type"], "Changed account metadata")
        labels[key] = label
        members[label] += 1
        types[label][vertices[key]["account_type"]] += 1
        balances[label].append(vertices[key]["balance"])
        if dataset == "ibm_aml" and "bank_id" in vertices[key]:
            require(row.get("bank_id") == vertices[key]["bank_id"], "Changed bank ID")
            banks[label].add(vertices[key]["bank_id"])
    require(summary and len({int(r["label"]) for r in summary}) == len(summary), "Empty/duplicate community summary")
    expected_labels = sorted(members, key=lambda label: (-members[label], label))[:50]
    require([int(row["label"]) for row in summary] == expected_labels, "Truncated/misordered top-community summary")
    currencies = {e.get("payment_currency") for e in edges}
    if dataset == "ibm_aml" and len(currencies) > 1:
        require(all("total_tx_amount" not in r for r in summary),
                f"Legacy IBM summary mixes {len(currencies)} currencies in total_tx_amount; regenerate with current exporter")
    totals = defaultdict(Counter)
    for edge in edges:
        counts = totals[labels[edge["src"]]]
        counts["total_tx_count"] += 1
        counts["fraud"] += edge["isFraud"]
        if labels[edge["src"]] == labels[edge["dst"]]:
            counts["internal_tx_count"] += 1
            counts["internal_fraud"] += edge["isFraud"]
    differences = []
    mismatch_count = 0

    def verify_rows(rows):
        nonlocal mismatch_count
        seen = set()
        for row in rows:
            label = int(row["label"])
            require(label not in seen, "Duplicate summary label")
            seen.add(label)
            require(label in members, "Summary contains a foreign community")
            expected = {"member_count": members[label], "total_tx_count": totals[label]["total_tx_count"],
                        "internal_tx_count": totals[label]["internal_tx_count"]}
            prefix = "fraud" if dataset == "paysim" else "laundering"
            expected[prefix + "_tx_count"] = totals[label]["fraud"]
            expected["internal_" + prefix + "_count"] = totals[label]["internal_fraud"]
            if dataset == "paysim":
                expected.update(customer_count=types[label]["Customer"], merchant_count=types[label]["Merchant"])
            if dataset == "ibm_aml" and banks:
                expected["unique_banks_count"] = len(banks[label])
            for field, value in expected.items():
                if int(row[field]) != value:
                    mismatch_count += 1
                    if len(differences) < 3:
                        differences.append(f"label={label}, {field}: saved={row[field]}, expected={value}")
            rate = totals[label]["fraud"] / max(1, totals[label]["total_tx_count"])
            require(math.isclose(float(row[prefix + "_rate"]), round(rate, 4), abs_tol=0.000051), "Incorrect community fraud rate")
            require(math.isclose(float(row["avg_balance"]), math.fsum(balances[label]) / members[label], abs_tol=0.011), "Incorrect mean balance")
        return seen
    verify_rows(summary)
    if full_summary is not None:
        seen = verify_rows(full_summary)
        require(seen == set(members), "All-community summary omits or adds communities")
    if currency_amounts is not None:
        expected_amounts = {}
        for edge in edges:
            key = (labels[edge["src"]], edge["payment_currency"])
            count, amount = expected_amounts.get(key, (0, 0.0))
            expected_amounts[key] = (count + 1, amount + edge["amount"])
        seen_amounts = set()
        for row in currency_amounts:
            key = (int(row["label"]), row["payment_currency"])
            require(key in expected_amounts and key not in seen_amounts, "Duplicate/foreign currency group")
            seen_amounts.add(key)
            count, amount = expected_amounts[key]
            require(int(row["total_tx_count"]) == count and math.isclose(float(row["total_tx_amount"]), amount,
                    rel_tol=1e-12, abs_tol=1e-6), "Incorrect currency amount/count")
        require(seen_amounts == set(expected_amounts), "Missing currency groups")
    require(mismatch_count == 0, f"{mismatch_count} community field mismatches; " + "; ".join(differences[:3]))
    return {"assigned_accounts": len(labels), "communities": len(members), "checked_summary_rows": len(summary),
            "summary_scope": "all communities reconciled" if full_summary is not None else "delivered rows only",
            "fraud_edges": sum(edge["isFraud"] for edge in edges)}


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def notebook_tables(notebook):
    for cell in notebook["cells"]:
        for output in cell.get("outputs", []):
            html = output.get("data", {}).get("text/html")
            if html:
                parser = _Tables()
                parser.feed("".join(html))
                if parser.rows:
                    yield [dict(zip(parser.rows[0][1:], row[1:])) for row in parser.rows[1:]]


def verify_notebook(path, root):
    notebook = json.loads(path.read_text(encoding="utf-8"))
    require(notebook["metadata"]["graphguard_execution"]["status"] == "completed", "Notebook execution incomplete")
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    require(notebook["metadata"]["graphguard_execution"]["completed_code_cells"] == len(cells), "Execution metadata/cell count differs")
    require([c["execution_count"] for c in cells] == list(range(1, len(cells) + 1)), "Incomplete execution counts")
    images = 0
    for cell in cells:
        ast.parse("".join(cell["source"]))
        for output in cell.get("outputs", []):
            require(output["output_type"] != "error", "Saved notebook error")
            if "image/png" in output.get("data", {}):
                require(base64.b64decode("".join(output["data"]["image/png"])).startswith(b"\x89PNG\r\n\x1a\n"), "Invalid embedded PNG")
                images += 1
    require(images >= 6, "Missing presentation figures")
    hashes = notebook["metadata"].get("graphguard_source_sha256", {})
    require(len(hashes) >= 20, "Missing executed-source hashes")
    for source, digest in hashes.items():
        content = (root / source).read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != digest:
            # Git autocrlf may change checkout bytes without changing Python.
            content = content.replace(b"\r\n", b"\n")
            actual = hashlib.sha256(content).hexdigest()
        if actual != digest:
            delta = notebook["metadata"].get("graphguard_post_execution_whitespace", {}).get(source, {})
            require(delta.get("working_tree_sha256") == actual and hashlib.sha256(content + b"\n").hexdigest() == digest,
                    f"Source changed since notebook execution: {source}")
    metric_tables = [rows for rows in notebook_tables(notebook) if rows and {"TP", "FP", "FN", "TN", "F1"} <= rows[0].keys()]
    require(len(metric_tables) == 1 and len(metric_tables[0]) == 2, "Missing ablation/confusion results")
    denominators = set()
    for row in metric_tables[0]:
        tp, fp, fn, tn = (int(row[k]) for k in ("TP", "FP", "FN", "TN"))
        require(min(tp, fp, fn, tn) >= 0, "Negative confusion count")
        denominators.add((tp + fp + fn + tn, tp + fn))
        for key, expected in (("precision", tp / (tp + fp)), ("recall", tp / (tp + fn)),
                              ("F1", 2 * tp / (2 * tp + fp + fn))):
            require(math.isclose(float(row[key]), expected, abs_tol=0.000001), f"Inconsistent notebook {key}")
    require(len(denominators) == 1, "Ablation uses different evaluation denominators")
    return {"executed_cells": len(cells), "figures": images, "source_hashes": len(hashes),
            "evidence": "saved Windows outputs; detector not rerun by this audit"}


def audit_project(root=ROOT, signal_root=None):
    """Collect every failure instead of hiding later tasks behind the first one."""
    configure_runtime()
    root = Path(root)
    signal_root = Path(signal_root or root / "results/project_check/signals")
    checks = []

    def check(name, function):
        try:
            evidence = function()
            checks.append({"check": name, "status": "PASS", "evidence": evidence})
            return evidence
        except (AuditBlocked, FileNotFoundError, ImportError) as error:
            checks.append({"check": name, "status": "BLOCKED", "evidence": str(error)})
        except Exception as error:
            checks.append({"check": name, "status": "FAIL", "evidence": f"{type(error).__name__}: {error}"})
        return None

    def compile_sources():
        paths = sorted((root / "src").rglob("*.py")) + sorted((root / "tests").rglob("*.py"))
        for path in paths:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        return {"files": len(paths), "scope": "syntax; not execution"}

    check("source.syntax", compile_sources)
    for dataset, expected in FULL_COUNTS.items():
        def full_metadata():
            counts = []
            for table in ("vertices", "edges"):
                _, count, _ = parquet_info(root / "data/processed" / dataset / (table + ".parquet"))
                counts.append(count)
            require(tuple(counts) == expected, f"Full cardinality differs: {counts} vs {expected}")
            return {"vertices": counts[0], "edges": counts[1], "scope": "Parquet footer counts, not full row integrity"}
        check(dataset + ".full_metadata", full_metadata)
        graph = check(dataset + ".sample_integrity", lambda: load_sample(root, dataset))
        if graph is None:
            for task in ("pagerank", "community", "degree_comparison"):
                checks.append({"check": dataset + "." + task, "status": "BLOCKED", "evidence": "Sample integrity unavailable"})
            continue
        # Keep graph objects in process only; JSON reports contain counts alone.
        vertices, edges, incoming, outgoing = graph
        checks[-1]["evidence"] = {"vertices": len(vertices), "edges": len(edges), "dangling": 0,
                                   "sum_in_degree": sum(incoming.values()), "sum_out_degree": sum(outgoing.values()),
                                   "fraud_edges": sum(edge["isFraud"] for edge in edges)}
        result_dir = root / "results" / dataset
        check(dataset + ".pagerank", lambda: verify_top10(csv_rows(result_dir / "top10_pagerank.csv"), *graph))
        check(dataset + ".community", lambda: verify_communities(csv_rows(result_dir / "communities.csv"),
              csv_rows(result_dir / "community_summary.csv"), vertices, edges, dataset,
              csv_iter_rows(result_dir / "community_summary_all.csv"),
              csv_iter_rows(result_dir / "community_amounts_by_currency.csv") if dataset == "ibm_aml" else None))
        required = ["community_summary_all.csv"]
        if dataset == "ibm_aml":
            required += ["community_amounts_by_currency.csv"]
        checks.append({"check": dataset + ".community_export_completeness", "status": "PASS" if all((result_dir / f).is_file() for f in required) else "FAIL",
                       "evidence": {"missing": [f for f in required if not (result_dir / f).is_file()],
                                    "scope": "complete exports required; values reconciled in community check"}})

        from src.common.run_evidence import verify_run_evidence
        if dataset == "paysim":
            def task1_evidence():
                run = verify_run_evidence(result_dir / "task1_run.json", task="Task 1 PaySim graph verification")
                require(run["metrics"]["num_vertices"] == len(vertices) and
                        run["metrics"]["num_edges"] == len(edges) and run["metrics"]["scope"] == "sample",
                        "Task 1 manifest does not describe the audited sample")
                return {"run_id": run["run_id"], "scope": run["metrics"]["scope"]}
            check("paysim.task1_manifest", task1_evidence)
        check(dataset + ".task2_manifest", lambda: {
            "run_id": verify_run_evidence(result_dir / "task2_run.json", task="Task 2 " + dataset)["run_id"]})
        task4_name = "Task 4 PaySim LPA execution" if dataset == "paysim" else "Task 4 IBM LPA execution"
        check(dataset + ".task4_manifest", lambda: {
            "run_id": verify_run_evidence(result_dir / "task4_run.json", task=task4_name)["run_id"]})

        def comparison():
            rows = [r for r in csv_rows(root / "results/comparison/degree_distribution_paysim_vs_ibm.csv")
                    if r["dataset"] == ("PaySim" if dataset == "paysim" else "IBM AML")]
            histogram = Counter(incoming[key] + outgoing[key] for key in vertices)
            require(len(rows) == len(histogram), "Incomplete degree distribution")
            require(len({int(r["degree"]) for r in rows}) == len(rows), "Duplicate degree bins")
            for row in rows:
                degree = int(row["degree"])
                require(int(row["account_count"]) == histogram.get(degree), "Incorrect degree frequency")
                require(math.isclose(float(row["proportion"]), histogram[degree] / len(vertices), abs_tol=1e-12), "Incorrect PMF denominator")
            return {"degree_bins": len(rows), "accounts": len(vertices), "scope": "sample"}
        check(dataset + ".degree_comparison", comparison)
        del graph, vertices, edges, incoming, outgoing
    for name in ("03_khanh_IBM_motif.ipynb", "03_khanh_PaySIM_motif.ipynb"):
        check("notebook." + name, lambda name=name: verify_notebook(root / "notebooks" / name, root))
    for dataset in FULL_COUNTS:
        for branch in ("centrality", "community"):
            check(dataset + ".temporal_" + branch, lambda dataset=dataset, branch=branch:
                  verify_component_report(signal_root / dataset / branch, dataset, branch))
    from src.ibm_aml.verify_motif_outputs import verify_outputs as verify_ibm
    from src.paysim.verify_motif_outputs import verify_outputs as verify_paysim

    check("ibm_aml.motif_csv", lambda: {name: len(rows) for name, rows in verify_ibm(root / "results/ibm_aml").items()})
    check("paysim.motif_csv", lambda: {name: len(rows) for name, rows in verify_paysim(root / "results/paysim").items()})
    import psutil

    return {"schema_version": "graphguard.project_audit.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL" if any(r["status"] in ("FAIL", "BLOCKED") for r in checks) else "PASS",
            "runtime": {"system": platform.system(), "python": platform.python_version(), "spark_started": False,
                        "logical_cpus": len(psutil.Process().cpu_affinity()), "rss_mib": round(psutil.Process().memory_info().rss / 1024**2, 1),
                        "peak_working_set_mib": round(psutil.Process().memory_info().peak_wset / 1024**2, 1),
                        "rss_budget_mib": MAX_RSS / 1024**2},
            "scope": "Bounded sample references + delivered CSV/notebook evidence; not a full production rerun",
            "checks": checks}


def component_edge_features(edges, snapshot, branch):
    """Map a frozen historical account snapshot to later transactions only."""
    from pyspark.sql import functions as F
    from src.motif.evaluation import require_unlabelled

    require_unlabelled(edges)
    require_unlabelled(snapshot)
    cutoffs = snapshot.select("as_of_step").distinct().limit(2).collect()
    require(len(cutoffs) == 1, "One historical snapshot is required")
    cutoff = cutoffs[0].as_of_step
    require(not edges.where(F.col("step") <= cutoff).limit(1).count(), "Snapshot must precede every decision transaction")
    names = ["degree", "pagerank"] if branch == "centrality" else ["community_size", "community_cross_fraction"]
    result = edges
    for side in ("src", "dst"):
        lookup = snapshot.select(F.col("id").alias(side), F.lit(1).alias(side + "_seen"),
                                 *[F.col(name).alias(side + "_" + name) for name in names])
        result = result.join(lookup, side, "left")
    result = result.fillna(0, subset=[side + "_" + name for side in ("src", "dst") for name in ["seen", *names]])
    for name in names:
        result = result.withColumn(name + "_score", F.greatest(F.col("src_" + name), F.col("dst_" + name)))
    return result.withColumn("novelty_score", ((F.col("src_seen") == 0) | (F.col("dst_seen") == 0)).cast("double"))


def component_rules(snapshot, branch):
    """Predeclared tails; cut values use history without any fraud labels."""
    names = ["degree", "pagerank"] if branch == "centrality" else ["community_size", "community_cross_fraction"]
    quantiles = (.01, .05, .1, .9, .95, .99)
    values = snapshot.approxQuantile(names, list(quantiles), 0.001)
    rules = [{"family": "novelty", "threshold": 1.0, "cut_value": 1.0, "score": "novelty_score", "direction": "high"}]
    for name, cuts in zip(names, values):
        require(len(cuts) == len(quantiles), "Empty historical feature support")
        for quantile, value in zip(quantiles, cuts):
            direction = "low" if quantile < .5 else "high"
            rules.append({"family": name + "_" + direction, "threshold": quantile,
                          "cut_value": float(value), "score": name + "_score", "direction": direction})
    return rules


def score_component_rules(features, truth, rules):
    """Count every decision transaction once per candidate, joining truth last."""
    from pyspark.sql import functions as F
    from src.motif.evaluation import binary_metrics, require_unlabelled

    require_unlabelled(features)
    flags = []
    for rule in rules:
        score, cutoff = F.col(rule["score"]), rule["cut_value"]
        alert = score <= cutoff if rule["direction"] == "low" else score >= cutoff
        flags.append(F.struct(F.lit(rule["family"]).alias("family"), F.lit(rule["threshold"]).alias("threshold"),
                              F.lit(cutoff).alias("cut_value"), alert.alias("alert")))
    decisions = features.select("event_id", F.explode(F.array(*flags)).alias("rule"))
    # No ground truth enters the account algorithms or the alert expression.
    labelled = decisions.select("event_id", "rule.*").join(truth.select("event_id", "isFraud"), "event_id")
    rows = labelled.groupBy("family", "threshold", "cut_value").agg(
        F.count("*").alias("n"), F.sum("isFraud").alias("p"),
        F.sum((F.col("alert") & (F.col("isFraud") == 1)).cast("long")).alias("tp"),
        F.sum((F.col("alert") & (F.col("isFraud") == 0)).cast("long")).alias("fp")).collect()
    return [{"family": r.family, "threshold": r.threshold, "cut_value": r.cut_value,
             **binary_metrics(r.n, r.p, r.tp, r.fp)} for r in rows]


def evaluate_component_signals(spark, dataset, branch, input_dir, output_dir):
    """Two expanding validation folds and one frozen test; no component fusion.

    Bounded pilot on existing samples. Reuse snapshot/edge-feature APIs for a
    later common-input integration run; never join independently sampled runs.
    """
    import pandas as pd
    import tempfile
    from pyspark.sql import functions as F
    from src.common.graph_utils import load_graph, write_spark_csv
    from src.common.run_evidence import write_run_evidence
    from src.motif.config import DATASETS
    from src.motif.features import normalize_edges
    from src.motif.evaluation import index_transactions
    from src.motif.modeling import choose_walk_forward_rule, score_histogram, precision_recall_curve, wilson_interval
    from src.paysim import metrics as centrality
    from src.paysim import community_detection as community

    require(branch in ("centrality", "community") and dataset in DATASETS, "Unknown component/dataset")
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    _, vertices, _ = parquet_info(input_dir / "vertices.parquet")
    _, transactions, _ = parquet_info(input_dir / "edges.parquet")
    require(vertices <= MAX_VERTICES and transactions <= MAX_EDGES, "Temporal pilot is sample-bounded; do not force full GraphX workloads")
    require(not output_dir.exists() or not any(output_dir.iterdir()), "Use a new/empty component experiment directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    records, owned = [], []
    selected = None
    snapshot = features = None
    temporary = tempfile.TemporaryDirectory(prefix="graphguard-signals-", ignore_cleanup_errors=True)
    try:
        indexed = index_transactions(normalize_edges(load_graph(spark, str(input_dir)).edges, DATASETS[dataset]))
        owned.append(indexed)
        truth = indexed.select("event_id", "step", "isFraud").localCheckpoint(eager=True)
        owned.append(truth)
        raw = indexed.drop("isFraud")
        cutoffs = tuple(int(x) for x in raw.approxQuantile("step", [.4, .6, .8], .001))
        require(len(cutoffs) == 3 and len(set(cutoffs)) == 3, "Three distinct time boundaries required")
        for fold, cutoff in enumerate(cutoffs):
            print(f"[SIGNAL] {dataset}/{branch}: historical snapshot through {cutoff}", flush=True)
            snapshot = (centrality.snapshot_features(raw, cutoff) if branch == "centrality" else
                        community.snapshot_features(raw, cutoff, spark, Path(temporary.name) / str(fold)))
            stop = cutoffs[fold + 1] if fold < 2 else None
            current = raw.where(F.col("step") > cutoff)
            if stop is not None:
                current = current.where(F.col("step") <= stop)
            features = component_edge_features(current, snapshot, branch).localCheckpoint(eager=True)
            support = truth.where(F.col("step") > cutoff)
            if stop is not None:
                support = support.where(F.col("step") <= stop)
            support_row = support.agg(F.count("*").alias("n"), F.sum("isFraud").alias("p")).first()
            require(support_row.n > 0 and support_row.p > 0, "Insufficient temporal positive support; no supported experiment")
            rules = component_rules(snapshot, branch)
            if fold < 2:
                scores = score_component_rules(features, truth, rules)
                require(all(row["transactions"] == support_row.n for row in scores), "Validation prediction coverage differs")
                records += [{"fold": fold + 1, **row} for row in scores]
                features.unpersist()
                snapshot.unpersist()
                features = snapshot = None
                continue
            validation = pd.DataFrame(records)
            selected, leaderboard = choose_walk_forward_rule(validation)
            family_rules = []
            for family in leaderboard.family.unique():
                best = leaderboard[leaderboard.family == family].iloc[0]
                family_rules.append(next(rule for rule in rules if rule["family"] == family and rule["threshold"] == best.threshold))
            metrics = pd.DataFrame(score_component_rules(features, truth, family_rules))
            require((metrics.transactions == support_row.n).all(), "Test prediction coverage differs")
            metrics["selected_on_validation"] = metrics.family == selected["family"]
            if selected["family"] == "abstain":
                final_rule = None
                predictions = features.withColumn("alert", F.lit(False)).withColumn("risk_score", F.lit(0.0))
            else:
                final_rule = next(rule for rule in family_rules if rule["family"] == selected["family"])
                value = F.col(final_rule["score"])
                risk_score = -value if final_rule["direction"] == "low" else value
                alert = value <= final_rule["cut_value"] if final_rule["direction"] == "low" else value >= final_rule["cut_value"]
                predictions = features.withColumn("alert", alert).withColumn("risk_score", risk_score)
            histogram = score_histogram(predictions, truth, cutoff, None)
            _, average_precision = precision_recall_curve(histogram)
            labelled = predictions.join(truth.select("event_id", "isFraud"), "event_id").localCheckpoint(eager=True)
            owned.append(labelled)
            cases = {"TP": "alert AND isFraud=1", "FP": "alert AND isFraud=0", "FN": "NOT alert AND isFraud=1"}
            examples = {case: [row.asDict() for row in labelled.where(condition).orderBy("event_key", "event_id")
                        .select("event_id", "event_key", "src", "dst", "step", "amount", "isFraud", "risk_score").limit(5).collect()]
                        for case, condition in cases.items()}
            report = {"dataset": dataset, "branch": branch, "scope": "sample temporal pilot", "cutoffs": cutoffs,
                "protocol": "40->60 and 60->80 validation; freeze family/quantile, refit snapshot at 80, test later; timestamp ties retained",
                "selection": json.loads(pd.DataFrame([selected]).to_json(orient="records"))[0], "final_rule": final_rule,
                "test_metrics": json.loads(metrics.to_json(orient="records", double_precision=15)),
                "selected_average_precision": average_precision, "examples": examples,
                "limitations": ["Internal sample holdout, not an untouched external benchmark", "Snapshot is frozen across each future decision interval",
                    "Low scores may reflect unseen accounts; compare novelty baseline", "Scores are uncalibrated structural signals, not fraud probabilities",
                    "Fraud labels never enter PageRank, LPA or structural thresholds", "Not comparable directly with full-data motif results"]}
            if final_rule is None:
                from src.motif.evaluation import binary_metrics
                report["selected_test_metrics"] = binary_metrics(support_row.n, support_row.p, 0, 0)
            else:
                report["selected_test_metrics"] = json.loads(metrics.loc[metrics.selected_on_validation].to_json(orient="records"))[0]
                row = metrics.loc[metrics.selected_on_validation].iloc[0]
                report["selected_precision_95"] = wilson_interval(int(row.TP), int(row.TP + row.FP))
                report["selected_recall_95"] = wilson_interval(int(row.TP), int(row.TP + row.FN))
            validation.to_csv(output_dir / "validation.csv", index=False, encoding="utf-8-sig")
            metrics.to_csv(output_dir / "test_metrics.csv", index=False, encoding="utf-8-sig")
            write_spark_csv(labelled.repartition(32), output_dir / "test_predictions.csv")
            write_spark_csv(snapshot.repartition(32), output_dir / "account_snapshot.csv")
            (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 4))
            metrics.set_index("family")[["precision", "recall", "F1"]].plot.bar(ax=ax, rot=20)
            ax.set(title=f"{dataset}: {branch}, frozen internal sample test", ylabel="Score", ylim=(0, 1))
            fig.tight_layout()
            fig.savefig(output_dir / "signal_metrics.png", dpi=130)
            plt.close(fig)
            outputs = [p for p in output_dir.iterdir() if p.is_file()]
            write_run_evidence(output_dir / "run.json", spark, task="Temporal signals " + dataset + " " + branch,
                inputs=[input_dir], outputs=outputs,
                sources=[Path(__file__), ROOT / "src/paysim/metrics.py", ROOT / "src/paysim/community_detection.py",
                         ROOT / "src/common/graph_utils.py", ROOT / "src/motif/evaluation.py", ROOT / "src/motif/modeling.py"],
                parameters={"branch": branch, "fractions": [.4, .6, .8], "quantiles": [.01, .05, .1, .9, .95, .99]}, metrics=report)
            print(metrics.to_string(index=False), flush=True)
            return report
    finally:
        for frame in (features, snapshot, *owned):
            if frame is not None:
                frame.unpersist()
        temporary.cleanup()



def verify_component_report(directory, dataset, branch):
    """Recompute confusion counts and CV choice from exported evidence."""
    import pandas as pd
    from src.common.run_evidence import verify_run_evidence
    from src.motif.modeling import choose_walk_forward_rule
    from src.motif.evaluation import binary_metrics

    manifest = verify_run_evidence(directory / "run.json", task="Temporal signals " + dataset + " " + branch)
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    require(report["dataset"] == dataset and report["branch"] == branch, "Wrong component evidence")
    cutoffs = report["cutoffs"]
    require(len(cutoffs) == 3 and cutoffs == sorted(set(cutoffs)), "Invalid component cutoffs")
    validation = pd.read_csv(directory / "validation.csv")
    require(set(validation.fold) == {1, 2}, "Two temporal validation folds required")
    require(not validation.duplicated(["fold", "family", "threshold"]).any(), "Duplicated validation candidate")
    selected, _ = choose_walk_forward_rule(validation)
    require(selected["family"] == report["selection"]["family"] and
            selected["threshold"] == report["selection"]["threshold"], "Selection changed after validation")
    n = p = tp = fp = 0
    seen = set()
    rule = report["final_rule"]
    if selected["family"] == "abstain":
        require(rule is None, "Abstention must not contain an alert rule")
    else:
        require(rule is not None and rule["family"] == selected["family"] and
                rule["threshold"] == selected["threshold"], "Test rule differs from validation selection")
    for row in csv_iter_rows(directory / "test_predictions.csv"):
        event = int(row["event_id"])
        require(event not in seen, "Duplicated component prediction")
        seen.add(event)
        require(int(row["step"]) > cutoffs[-1], "Historical snapshot used for a same-time/past decision")
        label_value = float(row["isFraud"])
        require(label_value in (0., 1.), "Invalid component ground truth")
        require(row["alert"].lower() in ("true", "false"), "Invalid alert value")
        alert = row["alert"].lower() == "true"
        if rule is None:
            expected = False
        else:
            score = float(row[rule["score"]])
            expected = score <= rule["cut_value"] if rule["direction"] == "low" else score >= rule["cut_value"]
        require(alert == expected, "Alert differs from frozen decision rule")
        positive = int(label_value)
        n += 1
        p += positive
        tp += int(alert and positive)
        fp += int(alert and not positive)
    actual = binary_metrics(n, p, tp, fp)
    require(n > 0, "Empty component test")
    for key in ("transactions", "fraud", "TP", "FP", "FN", "TN"):
        require(actual[key] == report["selected_test_metrics"][key], "Component confusion mismatch: " + key)
    accounts = set()
    for row in csv_iter_rows(directory / "account_snapshot.csv"):
        require(row["id"] not in accounts, "Duplicated account snapshot")
        accounts.add(row["id"])
        require(int(row["as_of_step"]) == cutoffs[-1], "Snapshot cutoff mismatch")
        require(not {"isFraud", "isLaundering", "label"}.intersection(row), "Ground truth in account feature export")
    require(accounts, "Empty account snapshot")
    return {"run_id": manifest["run_id"], "scope": report["scope"], "selected": selected["family"], **actual}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals-root", type=Path)
    parser.add_argument("--signals", choices=["centrality", "community"])
    parser.add_argument("--full-system", action="store_true", help="Full-data acceptance (default)")
    parser.add_argument("--legacy-samples", action="store_true", help="Explicit historical/development sample audit")
    parser.add_argument("--dataset", choices=["paysim", "ibm_aml"])
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "results/project_check/latest.json")
    args = parser.parse_args()
    if args.signals:
        if not args.legacy_samples:
            parser.error("--signals is a legacy pilot; pass --legacy-samples explicitly, or use the full-system pipeline")
        if not args.dataset:
            parser.error("--signals requires --dataset")
        from src.common.spark_session import get_graph_session
        source = (args.input_dir or ROOT / "data/processed/sample" / args.dataset).resolve()
        output = (args.output_dir or ROOT / "results/project_check/signals" / args.dataset / args.signals).resolve()
        require(not output.exists() or not any(output.iterdir()), "Use a new/empty signal output directory")
        spark = get_graph_session("Component-signals-" + args.dataset, driver_memory="4g")
        try:
            spark.sparkContext.setLogLevel("ERROR")
            evaluate_component_signals(spark, args.dataset, args.signals, source, output)
        finally:
            spark.stop()
        return
    report = audit_project(signal_root=args.signals_root) if args.legacy_samples else audit_full_system()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    for result in report["checks"]:
        print(f"[{result['status']}] {result['check']}: {result['evidence']}")
    print(f"Overall: {report['status']}. Report: {args.report}")
    raise SystemExit(0 if report["status"] == "PASS" else 1)




def verify_full_system_communities(run):
    """Independent full SQL reconciliation; no Python collect of account lists."""
    from pyspark.sql import functions as F
    from src.common.graph_utils import load_graph
    from src.ibm_aml.verify_communities import compare_values, same_keys, unique_keys
    graph = load_graph(run.spark, str(run.input_dir))
    assigned = run.table("communities")
    summary = run.table("community_summary_all")
    amounts = run.table("community_amounts_by_currency")
    unique_keys(assigned, ["id"], "full assignments")
    same_keys(assigned, graph.vertices, ["id"], "full assignment coverage")
    require(not assigned.where(F.col("label").isNull()).limit(1).count(), "Null full community label")
    members = assigned.groupBy("label").count().withColumnRenamed("count", "member_count")
    compare_values(summary.select("label", "member_count"), members, ["label"], ["member_count"], [], "all member counts")
    # Compute source/destination communities independently from the saved IDs.
    raw = graph.edges.join(assigned.select(F.col("id").alias("src"), F.col("label").alias("s")), "src").join(
        assigned.select(F.col("id").alias("dst"), F.col("label").alias("d")), "dst")
    expected = raw.groupBy("s").agg(F.count("*").alias("total_tx_count"),
        F.sum("isFraud").cast("long").alias("positive_tx_count"),
        F.sum(F.when(F.col("s")==F.col("d"), 1).otherwise(0)).alias("internal_tx_count")).withColumnRenamed("s", "label")
    expected = members.select("label").join(expected, "label", "left").fillna(0)
    compare_values(summary, expected, ["label"], ["total_tx_count", "positive_tx_count", "internal_tx_count"], [], "all transaction counts")
    require(not summary.where(F.col("cross_tx_count")+F.col("internal_tx_count")!=F.col("total_tx_count")).limit(1).count(), "Cross/internal totals mismatch")
    currency = F.col("payment_currency") if run.dataset == "ibm_aml" else F.lit("PaySim unit")
    expected_amounts = raw.withColumn("payment_currency", currency).groupBy("s", "payment_currency").agg(
        F.count("*").alias("total_tx_count"), F.sum("amount").alias("total_tx_amount")).withColumnRenamed("s", "label")
    compare_values(amounts, expected_amounts, ["label", "payment_currency"], ["total_tx_count"], ["total_tx_amount"], "full currency totals")
    if run.dataset == "paysim":
        for kind in ("Customer", "Merchant"):
            name = kind.lower()+"_count"
            counts = assigned.where(F.col("account_type")==kind).groupBy("label").count().withColumnRenamed("count", name)
            counts = members.select("label").join(counts, "label", "left").fillna(0)
            compare_values(summary, counts, ["label"], [name], [], "full account types")
    totals = summary.agg(F.count("*").alias("communities"), F.sum("member_count").alias("accounts"),
        F.sum("total_tx_count").alias("transactions"), F.sum("positive_tx_count").alias("positives"),
        F.sum("internal_tx_count").alias("internal_edges"), F.sum("cross_tx_count").alias("cross_edges")).first().asDict()
    require(totals["accounts"] == run.record["integrity"]["num_vertices"] and totals["transactions"] == run.record["support"]["n"], "Full denominator mismatch")
    require(totals["positives"] == run.record["support"]["positives"], "Full positive coverage mismatch")
    return totals


def verify_full_system_artifacts(directory, require_full=True):
    """Stream exported predictions independently and verify every artifact hash."""
    import csv
    import hashlib
    import pyarrow.parquet as pq
    from src.motif.evaluation import binary_metrics
    from src.motif.modeling import precision_recall_curve
    from src.motif.config import SYSTEM_FAMILY_GROUPS
    from src.common.run_evidence import file_fingerprint
    import pandas as pd
    directory = Path(directory).resolve()
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    require(report["status"] == "completed" and report["schema_version"] == "graphguard.full_system.v1", "Incomplete system report")
    require(not require_full or report["scope"] == "full", "Fixture/sample cannot pass full benchmark acceptance")
    from src.common.run_evidence import verify_run_evidence
    verify_run_evidence(directory / "run.json", task="Full system "+report["dataset"])
    run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    require(run["status"] == "PASS", "Missing execution evidence")
    for member in run["outputs"]:
        require(file_fingerprint(directory / Path(member["path"]).name)["sha256"] == member["sha256"], "Report/index fingerprint changed")
    for member in json.loads((directory / "artifact_index.json").read_text(encoding="utf-8")):
        path = (directory / member["path"]).resolve()
        require(path.is_relative_to(directory), "Foreign artifact path")
        require(path.stat().st_size == member["bytes"] and file_fingerprint(path)["sha256"] == member["sha256"], "Changed artifact: "+member["path"])
    frozen = json.loads((directory / "frozen_rules.json").read_text(encoding="utf-8"))
    digest = frozen.pop("sha256")
    require(hashlib.sha256(json.dumps(frozen, sort_keys=True, allow_nan=False).encode()).hexdigest() == digest == report["frozen_rule_sha256"], "Frozen rule changed")
    metrics = {row["model"]: row for row in report["test_metrics"]}
    require(set(metrics) == set(SYSTEM_FAMILY_GROUPS), "Missing ablations")
    expected_n = report["phases"]["frozen_test"]["test_transactions"]
    expected_p = report["phases"]["frozen_test"]["test_positives"]
    for family, row in metrics.items():
        n = p = tp = fp = 0
        bins = Counter()
        threshold = frozen["family_rules"][family]["threshold"]
        files = sorted((directory / "predictions" / (family+".parquet")).glob("*.parquet"))
        require(bool(files), "Missing prediction parts")
        for file in files:
            for batch in pq.ParquetFile(file).iter_batches(batch_size=4096, columns=["risk_score", "alert", "isFraud"]):
                data = batch.to_pydict()
                for score, alert, label in zip(data["risk_score"], data["alert"], data["isFraud"]):
                    require(label in (0, 1) and score is not None and math.isfinite(score) and 0 <= score <= 1, "Invalid score/label")
                    require(bool(alert) == (score >= threshold), "Alert does not follow frozen validation threshold")
                    n += 1; p += int(label); tp += int(bool(alert) and label==1); fp += int(bool(alert) and label==0)
                    bins[(score, int(label))] += 1
        require(n == expected_n and p == expected_p, "Different ablation population")
        actual = binary_metrics(n, p, tp, fp)
        for key in ("TP", "FP", "FN", "TN", "transactions", "fraud", "alerts"):
            require(actual[key] == row[key], "Prediction confusion differs from report: "+family+"/"+key)
        hist = pd.DataFrame([{"risk_score": score, "isFraud": label, "count": count} for (score, label), count in bins.items()])
        _, ap = precision_recall_curve(hist)
        require(ap is not None and math.isclose(ap, row["average_precision"], abs_tol=1e-12), "Average precision differs")
    for name, count in (("transactions", report["support"]["n"]), ("features", report["support"]["n"]),
                        ("communities", report["integrity"]["num_vertices"]), ("account_metrics", report["integrity"]["num_vertices"]), ("final_predictions", expected_n)):
        actual = sum(pq.ParquetFile(p).metadata.num_rows for p in (directory / (name+".parquet")).glob("*.parquet"))
        require(actual == count, "Full output footer coverage differs: "+name)
    if require_full:
        for member in report["phases"]["raw_reconciliation"]["raw_files"]:
            require(file_fingerprint(Path(member["path"]))["sha256"]==member["sha256"], "Raw file changed after reconciliation")
        require(report["phases"].get("raw_reconciliation",{}).get("status")=="PASS", "No full raw reconciliation")
        require((report["integrity"]["num_vertices"],report["support"]["n"])==FULL_COUNTS[report["dataset"]], "Not the declared full dataset")
    final_counts = Counter()
    selected = frozen["selection"]["family"]
    for file in (directory / "final_predictions.parquet").glob("*.parquet"):
        for batch in pq.ParquetFile(file).iter_batches(batch_size=4096,columns=["risk_score","alert","isFraud","step","snapshot_as_of","dataset"]):
            values = batch.to_pydict()
            for i, score in enumerate(values["risk_score"]):
                alert,label = values["alert"][i], values["isFraud"][i]
                require(values["dataset"][i] == report["dataset"], "Wrong dataset in final prediction")
                require(values["step"][i]>report["snapshot_cutoffs"][-1] and values["snapshot_as_of"][i]<values["step"][i], "Noncausal final prediction context")
                require(not alert and score==0 if selected=="abstain" else bool(alert)==(score>=frozen["selection"]["threshold"]), "Final alert rule changed")
                final_counts["n"]+=1; final_counts["p"]+=int(label)
                final_counts["tp"]+=int(alert and label==1); final_counts["fp"]+=int(alert and label==0)
    require(final_counts["n"]==expected_n and final_counts["p"]==expected_p, "Final selected output coverage mismatch")
    final_metrics=binary_metrics(expected_n,expected_p,final_counts["tp"],final_counts["fp"])
    require(all(final_metrics[k]==report["selected_test_metrics"][k] for k in ("TP","FP","FN","TN","alerts")), "Selected final confusion mismatch")
    return {"status": "PASS", "scope": report["scope"], "full_transactions": report["support"]["n"],
            "full_accounts": report["integrity"]["num_vertices"], "models": len(metrics), "test_transactions": expected_n,
            "test_positives": expected_p, "predictions_confusion_and_AP": "independently recomputed", "artifact_hashes": "PASS"}



def verify_full_system_notebook(path, directory, root=ROOT):
    """Bind executed cells/figures/source hashes to the exact accepted run."""
    notebook = json.loads(Path(path).read_text(encoding="utf-8"))
    code = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    execution = notebook["metadata"].get("graphguard_execution", {})
    require(execution.get("status") == "completed" and execution.get("completed_code_cells") == len(code), "Incomplete full-system notebook")
    require([c["execution_count"] for c in code] == list(range(1,len(code)+1)), "Incomplete cell execution order")
    digest = hashlib.sha256(json.dumps(["".join(c["source"]) for c in code], ensure_ascii=False).encode("utf-8")).hexdigest()
    require(digest == notebook["metadata"].get("graphguard_executed_code_sha256"), "Notebook code changed after execution")
    report = json.loads((Path(directory) / "report.json").read_text(encoding="utf-8"))
    require(notebook["metadata"].get("graphguard_dataset") == report["dataset"], "Notebook/dataset mismatch")
    hashes = notebook["metadata"].get("graphguard_source_sha256", {})
    require(set(report["source_sha256"]) <= set(hashes), "Notebook missing executed source dependencies")
    for name, expected in hashes.items():
        content = (root/name).read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        require(actual == expected or hashlib.sha256(content.replace(b"\r\n",b"\n")).hexdigest() == expected, "Notebook source changed: "+name)
    images, directories = 0, []
    for cell in code:
        ast.parse("".join(cell["source"]))
        for output in cell.get("outputs",[]):
            require(output["output_type"] != "error", "Saved notebook error")
            if "image/png" in output.get("data",{}):
                require(base64.b64decode("".join(output["data"]["image/png"])).startswith(b"\x89PNG"), "Invalid figure")
                images += 1
            stream = output.get("text", "")
            stream = "".join(stream) if isinstance(stream,list) else stream
            for line in stream.splitlines():
                if line.startswith("Full run directory: "):
                    directories.append(Path(line.split(": ",1)[1]).resolve())
    require(images >= 6, "Missing full-system benchmark graphs")
    require(directories == [Path(directory).resolve()], "Notebook does not present the accepted latest run")
    expected = {r["model"]:r for r in report["test_metrics"]}
    tables = [rows for rows in notebook_tables(notebook) if rows and {"model","TP","FP","FN","TN","F1"} <= rows[0].keys()]
    require(bool(tables), "Notebook missing ablation confusion metrics")
    for rows in tables:
        require({row["model"] for row in rows} == set(expected), "Notebook missing an ablation")
        for row in rows:
            for name in ("TP","FP","FN","TN"):
                require(int(row[name]) == expected[row["model"]][name], "Notebook metric differs from accepted run")
    return {"cells":len(code),"figures":images,"models":len(expected),"executed_source_hashes":len(hashes),"scope":"full"}


def audit_full_system(root=ROOT):
    """Full artifact acceptance; starts no Spark and never accepts a sample run."""
    configure_runtime()
    checks=[]
    for dataset, notebook in (("ibm_aml","IBM_full_system.ipynb"),("paysim","PaySIM_full_system.ipynb")):
        try:
            pointer = json.loads((root/"results/full_system"/dataset/"latest.json").read_text(encoding="utf-8"))
            require(pointer["status"] == "completed", "Latest run is not completed")
            directory = Path(pointer["directory"]).resolve()
            require(directory.is_relative_to((root/"results/full_system"/dataset).resolve()), "Foreign latest directory")
            require(json.loads((directory/"report.json").read_text(encoding="utf-8"))["dataset"]==dataset, "Latest pointer dataset mismatch")
            require(hashlib.sha256((directory/"report.json").read_bytes()).hexdigest() == pointer["report_sha256"], "Latest report changed")
            checks.append({"check":dataset+".full_system","status":"PASS","evidence":verify_full_system_artifacts(directory)})
            checks.append({"check":dataset+".full_notebook","status":"PASS","evidence":verify_full_system_notebook(root/"notebooks"/notebook,directory,root)})
            check_memory()
        except (FileNotFoundError, AuditBlocked) as error:
            checks.append({"check":dataset+".full_acceptance","status":"BLOCKED","evidence":str(error)})
        except Exception as error:
            checks.append({"check":dataset+".full_acceptance","status":"FAIL","evidence":f"{type(error).__name__}: {error}"})
    return {"schema_version":"graphguard.full_acceptance.v1","created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"PASS" if len(checks)==4 and all(c["status"]=="PASS" for c in checks) else "FAIL",
            "scope":"Two actual full datasets, eight factorial ablations plus novelty control each, exported predictions and executed matching notebooks", "checks":checks}

if __name__ == "__main__":
    main()
