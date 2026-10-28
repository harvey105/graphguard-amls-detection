"""Read-only aggregate GraphGuard analysis. No Spark, training or row-level inference.

Run with the repository Windows Python 3.12 and -B. All writes are confined to a
new output directory. Source snapshots make the resulting HTML portable offline.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit

DATASETS = {
    "ibm_aml": ("run_20261024T081350344149Z", "full_fusion", 0.5),
    "paysim": ("run_20261024T084918669391Z", "without_centrality", 0.7),
}
FAMILIES = ["transaction_only", "transaction_novelty", "transaction_centrality",
            "motif_assisted", "transaction_community", "full_fusion",
            "without_centrality", "without_motifs", "without_community"]
METRICS = ["precision", "recall", "F1", "average_precision"]
TOL = 1e-9


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def ratio(a, b):
    return a / b if b else None


def numeric(value):
    if value in ("True", "False"):
        return value == "True"
    if value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return float(value)
        except (ValueError, TypeError):
            return value


def read_csv_bytes(data):
    return [{k: numeric(v) for k, v in r.items()}
            for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig")))]


def group(feature):
    if feature in {"type_index", "currency_index", "scaled_amount", "unseen_amount_group", "fx_payment"}:
        return "T"
    if "community" in feature:
        return "L"
    if feature in {"src_seen", "dst_seen"} or "degree" in feature.lower() or "pagerank" in feature:
        return "C"
    if re.match(r"^(sender_|receiver_|fanin_|fanout_|relay_|reciprocal_|cycle3_)", feature):
        return "M"
    raise ValueError(f"Unknown feature group: {feature}")


def validate_confusion(row, check, context):
    tp, fp, fn, tn = (row[x] for x in ("TP", "FP", "FN", "TN"))
    check(all(isinstance(x, int) and x >= 0 for x in (tp, fp, fn, tn)), context + ": nonnegative integers")
    check(tp + fp == row["alerts"], context + ": alerts")
    check(tp + fn == row["fraud"], context + ": positives")
    check(tp + fp + fn + tn == row["transactions"], context + ": total")
    for key, actual in {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
                        "F1": ratio(2 * tp, 2 * tp + fp + fn)}.items():
        check(actual is None and row[key] is None or actual is not None and row[key] is not None
              and math.isclose(actual, row[key], abs_tol=TOL, rel_tol=0), context + ": " + key)


def validate_pr(rows, metric, check, context):
    cum_t = cum_p = 0
    ap = 0.0
    previous = math.inf
    for r in rows:
        check(r["risk_score"] < previous, context + ": unique descending scores")
        previous = r["risk_score"]
        check(r["transactions"] >= r["positives"] >= 0, context + ": bin bounds")
        cum_t += r["transactions"]
        cum_p += r["positives"]
        p, rec = ratio(cum_p, cum_t), ratio(cum_p, metric["fraud"])
        check(p is not None and abs(p - r["precision"]) <= TOL, context + ": cumulative precision")
        check(rec is not None and abs(rec - r["recall"]) <= TOL, context + ": cumulative recall")
        ap += r["positives"] / metric["fraud"] * p
    check(cum_t == metric["transactions"] and cum_p == metric["fraud"], context + ": populations")
    check(abs(ap - metric["average_precision"]) <= TOL, context + ": AP")


class Analysis:
    def __init__(self, bundle, output):
        self.bundle = bundle.resolve()
        self.output = output.resolve()
        allowed = Path(__file__).resolve().parent
        if self.output == allowed or allowed not in self.output.parents or self.bundle in self.output.parents:
            raise ValueError("Output must be a new child directory of the analysis directory, outside bundle")
        if self.output.exists() and any(self.output.iterdir()):
            raise FileExistsError("Refusing nonempty output directory: " + str(self.output))
        self.output.mkdir(parents=True, exist_ok=True)
        self.inputs, self.inventory, self.findings, self.checkpoints = {}, [], [], []
        self.phase = None
        self.models, self.usage, self.deltas, self.budgets, self.cases = [], [], [], [], []
        self.evidence, self.temporal, self.identities = [], [], []
        self.data, self.deps = {}, {}
        self.write_json("analysis_config.json", {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                        "datasets": DATASETS, "tolerance": TOL, "python": sys.version,
                        "platform": sys.platform, "builder_sha256": digest(__file__),
                        "bundle_root": str(self.bundle), "output_root": str(self.output),
                        "no_spark": True, "no_training": True, "no_scoring": True,
                        "resume_policy": "No checkpoint reuse: nonempty outputs are refused; use a fresh output directory."})

    def write_json(self, name, obj):
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    def write_csv(self, name, rows):
        if not rows:
            return
        keys = list(dict.fromkeys(k for row in rows for k in row))
        with (self.output / name).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    def check(self, condition, message):
        self.findings.append({"checkpoint": self.phase, "status": "PASS" if condition else "FAIL", "check": message})

    def need(self, condition, message):
        self.check(condition, message)
        if not condition:
            raise ValueError(message)

    def phase_run(self, cp, label, fn, dependencies=()):
        self.phase = cp
        before = len(self.findings)
        bad = [d for d in dependencies if self.deps.get(d) not in {"PASS", "LIMITED"}]
        reason = ""
        if bad:
            status, reason = "BLOCKED", "Dependency failed: " + ", ".join(bad)
        else:
            try:
                limitation = fn()
                status = "FAIL" if any(f["status"] == "FAIL" for f in self.findings[before:]) else ("LIMITED" if limitation else "PASS")
                reason = limitation or ""
            except Exception as exc:
                status, reason = "FAIL", f"{type(exc).__name__}: {exc}"
                self.findings.append({"checkpoint": cp, "status": "FAIL", "check": reason})
        sources = sorted({r["source_file"] for r in self.inventory if cp in r["used_by"].split(";")})
        self.checkpoints.append({"checkpoint": cp, "label": label, "status": status, "reason": reason,
                                 "checks": len(self.findings) - before, "sources": ";".join(sources)})
        self.deps[cp] = status
        self.write_csv("checkpoint_status.csv", self.checkpoints)
        self.write_csv("validation_findings.csv", self.findings)
        self.write_json(f"checkpoints/{cp}.json", self.checkpoints[-1])
        print(cp, status, label, reason, flush=True)

    def load(self, rel, role, scope, dataset="shared", twin=None):
        rel = str(rel).replace("\\", "/")
        if rel in self.inputs:
            item = next(r for r in self.inventory if r["source_file"] == rel)
            phases = set(item["used_by"].split(";")) | {self.phase}
            item["used_by"] = ";".join(sorted(phases))
            return self.data[rel]
        p = self.bundle / rel
        self.need(p.is_file(), "Input exists: " + rel)
        raw = p.read_bytes()
        h = hashlib.sha256(raw).hexdigest()
        duplicate = "not_applicable"
        if twin:
            q = self.bundle / twin
            duplicate = "missing_copy"
            if q.is_file():
                self.inputs[str(twin)] = digest(q)
                duplicate = "identical" if self.inputs[str(twin)] == h else "CONFLICT"
                self.need(duplicate == "identical", "Duplicate hash: " + rel + " vs " + str(twin))
        if p.suffix == ".csv":
            obj = read_csv_bytes(raw)
            schema = ";".join(obj[0]) if obj else ""
            count = len(obj)
        elif p.suffix == ".json":
            obj = json.loads(raw.decode("utf-8-sig"))
            schema = ";".join(obj) if isinstance(obj, dict) else ";".join(obj[0]) if obj and isinstance(obj[0], dict) else "array"
            count = len(obj)
        else:
            obj, schema, count = raw.decode("utf-8-sig"), "text", None
        self.inputs[rel], self.data[rel] = h, obj
        snap = self.output / "sources" / rel
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_bytes(raw)
        self.inventory.append({"dataset": dataset, "source_file": rel, "sha256": h,
                               "bytes": len(raw), "rows_or_items": count, "schema": schema,
                               "role": role, "scope": scope, "duplicate_file": str(twin or ""),
                               "duplicate_status": duplicate, "used_by": self.phase})
        return obj

    def ds(self, d, sub, scope="test", duplicate=True):
        run = DATASETS[d][0]
        twin = f"results/full_system/{d}/{run}/{sub.split('/')[-1]}" if duplicate and sub.startswith(("tables/", "provenance/", "examples/")) else None
        return self.load(f"datasets/{d}/{sub}", sub, scope, d, twin)

    def source_link(self, rel, label=None):
        return f"[{label or rel}](sources/{quote(rel, safe='/')})"

    def sources(self):
        self.mapping = self.load("tables/model_families.csv", "family mapping", "configuration")
        self.allow = self.load("tables/exact_feature_allowlists.csv", "feature order", "configuration")
        self.overview = self.load("tables/dataset_overview.csv", "populations", "full/test")
        self.load("02_METHODS_AND_PARAMETERS.md", "temporal protocol", "method")
        self.load("06_RELIABILITY_AND_VALIDATION.md", "evidence limits", "method")
        self.need({r["family"] for r in self.mapping} == set(FAMILIES), "Nine family mappings")
        self.need({r["dataset"] for r in self.overview} == set(DATASETS), "Two dataset overview rows")
        for d, (run, family, threshold) in DATASETS.items():
            report = self.ds(d, "provenance/report.json", "full")
            meta = self.ds(d, "provenance/run.json", "provenance")
            frozen = self.ds(d, "provenance/frozen_rules.json", "validation")
            self.need(report["dataset"] == d and report["scope"] == "full" and report["status"] == "completed", d + ": completed full")
            self.need(frozen["selection"]["family"] == family and frozen["selection"]["threshold"] == threshold, d + ": selected rule")
            ov = next(r for r in self.overview if r["dataset"] == d)
            self.need(ov["source_run_id"] == run and ov["selected_family"] == family and ov["threshold"] == threshold, d + ": overview identity")
            self.identities.append({"dataset": d, "run_directory_name": run, "metadata_run_id": meta["run_id"],
                                    "recorded_executed_git_revision": meta.get("git_revision"),
                                    "selected_family": family, "threshold": threshold})
        self.write_csv("run_identity.csv", self.identities)

    def metrics(self):
        mapping = {r["family"]: r for r in self.mapping}
        for d, (_, selected, threshold) in DATASETS.items():
            rows = self.ds(d, "tables/test_metrics.csv")
            self.need(len(rows) == 9 and {r["model"] for r in rows} == set(FAMILIES), d + ": 9 unique models")
            report = self.ds(d, "provenance/report.json", "full")
            report_metrics = {r["model"]: r for r in report["test_metrics"]}
            ov = next(r for r in self.overview if r["dataset"] == d)
            frozen = self.ds(d, "provenance/frozen_rules.json", "validation")
            for r in rows:
                validate_confusion(r, self.check, d + "/" + r["model"])
                self.check(r["transactions"] == ov["test_transactions"] and r["fraud"] == ov["test_positives"], d + ": test population")
                self.check(r["selected_on_validation"] == (r["model"] == selected), d + ": selected flag")
                self.check(r["threshold"] == frozen["family_rules"][r["model"]]["threshold"], d + ": frozen family threshold")
                rr = report_metrics[r["model"]]
                for k in ["TP", "FP", "FN", "TN", "alerts", "transactions", "fraud", "threshold", *METRICS]:
                    self.check(abs(r[k] - rr[k]) <= TOL, d + ": report vs CSV " + r["model"] + "/" + k)
                curve = self.ds(d, f"tables/pr_curve_{r['model']}.csv")
                validate_pr(curve, r, self.check, d + "/" + r["model"])
                m = mapping[r["model"]]
                self.models.append({"dataset": d, "family": r["model"], **{k: m[k] for k in ["T", "C", "M", "L", "novelty_only"]},
                                    "threshold": r["threshold"], "selected_on_validation": r["selected_on_validation"],
                                    "test_transactions": r["transactions"], "test_positives": r["fraud"],
                                    **{k: r[k] for k in ["TP", "FP", "FN", "TN", "alerts", *METRICS]},
                                    "source_file": f"datasets/{d}/tables/test_metrics.csv"})
        self.write_csv("model_comparison.csv", self.models)

    def features(self):
        for d, (_, selected, _) in DATASETS.items():
            importance = self.ds(d, "tables/feature_importance.csv", "fitted model")
            for family in FAMILIES:
                allowed = sorted([r for r in self.allow if r["dataset"] == d and r["family"] == family], key=lambda r: r["feature_index"])
                names = [r["feature"] for r in allowed]
                prefix = f"model_details/{family}/"
                nodes = self.ds(d, prefix + "tree_nodes.csv", "fitted model", False)
                leaves = self.ds(d, prefix + "leaf_rules.csv", "fitted model", False)
                training = self.ds(d, prefix + "training.json", "fitted model", False)
                self.ds(d, prefix + "saved_model_parameters.json", "fitted model", False)
                self.ds(d, prefix + "amount_scales.csv", "training", False)
                self.need(training["feature_names"] == names, f"{d}/{family}: feature order")
                imp = {r["feature"]: r["importance"] for r in importance if r["family"] == family}
                self.need(set(imp) == set(names), f"{d}/{family}: importance coverage")
                self.check(all(v >= 0 for v in imp.values()) and abs(sum(imp.values()) - 1) <= TOL, f"{d}/{family}: importance sum")
                split_features = {r["feature_name"] for r in nodes if not r["is_leaf"]}
                self.check(split_features <= set(names), f"{d}/{family}: split allowlist")
                self.check(split_features == {f for f, v in imp.items() if v > 0}, f"{d}/{family}: splits vs importance")
                leaf_ids = {r["id"] for r in nodes if r["is_leaf"]}
                self.check(leaf_ids == {r["leaf_id"] for r in leaves}, f"{d}/{family}: leaf identities")
                threshold = next(r["threshold"] for r in self.models if r["dataset"] == d and r["family"] == family)
                for leaf in leaves:
                    self.check(leaf["alert_at_frozen_threshold"] == (leaf["risk_score"] >= threshold), f"{d}/{family}: leaf alert")
                    tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", leaf["condition"])) - {"IN", "AND", "NOT"}
                    self.check(tokens <= set(names), f"{d}/{family}: leaf condition allowlist")
                for f in names:
                    self.usage.append({"dataset": d, "family": family, "selected_on_validation": family == selected,
                                       "feature": f, "group": group(f), "allowed": True,
                                       "used_in_split": f in split_features, "importance": imp[f],
                                       "scope": "fitted on training prefix <=80%", "source_file": f"datasets/{d}/{prefix}tree_nodes.csv"})
        self.write_csv("feature_usage.csv", self.usage)

    def ablation(self):
        contrasts = [
            ("novelty_control", "transaction_novelty", "transaction_only"),
            ("centrality_alone", "transaction_centrality", "transaction_only"),
            ("motif_alone", "motif_assisted", "transaction_only"),
            ("community_alone", "transaction_community", "transaction_only"),
            ("all_graph", "full_fusion", "transaction_only"),
            ("centrality_in_fusion", "full_fusion", "without_centrality"),
            ("motif_in_fusion", "full_fusion", "without_motifs"),
            ("community_in_fusion", "full_fusion", "without_community")]
        for d, (_, selected, _) in DATASETS.items():
            m = {r["family"]: r for r in self.models if r["dataset"] == d}
            existing = self.ds(d, "tables/graph_contributions.csv")
            for contrast, enhanced, reference in contrasts + [("selected_vs_baseline", selected, "transaction_only")]:
                a, b = m[enhanced], m[reference]
                row = {"dataset": d, "scope": "test", "contrast": contrast, "enhanced": enhanced, "reference": reference,
                       "enhanced_threshold": a["threshold"], "reference_threshold": b["threshold"],
                       **{"delta_" + k + "_pp": 100 * (a[k] - b[k]) for k in METRICS},
                       **{"delta_" + k: a[k] - b[k] for k in ["alerts", "TP", "FP", "FN"]},
                       "interpretation": "difference between fitted configurations; not causal contribution",
                       "source_file": f"datasets/{d}/tables/test_metrics.csv"}
                matched = [r for r in existing if r["contrast"] == contrast]
                for r in matched:
                    for k in METRICS:
                        self.check(abs(row["delta_" + k + "_pp"] / 100 - r["delta_" + k]) <= TOL, d + ": exported delta " + contrast + "/" + k)
                self.deltas.append(row)
            self.check(len(existing) == 7 and all(r["contrast"] in {c[0] for c in contrasts} for r in existing), d + ": seven original contrasts")
        self.write_csv("ablation_deltas.csv", self.deltas)

    def budget(self):
        for d in DATASETS:
            rows = self.ds(d, "tables/review_budgets.csv")
            self.need(len(rows) == 27 and len({(r["model"], r["review_fraction"]) for r in rows}) == 27, d + ": 27 unique budgets")
            self.need({r["model"] for r in rows} == set(FAMILIES) and {r["review_fraction"] for r in rows} == {0.001, 0.005, 0.01}, d + ": models/fractions")
            base = {r["review_fraction"]: r for r in rows if r["model"] == "transaction_only"}
            for r in rows:
                m = next(m for m in self.models if m["dataset"] == d and m["family"] == r["model"])
                self.check(r["transactions"] == m["test_transactions"] and r["fraud"] == m["test_positives"], d + ": budget population")
                self.check(r["K"] == math.ceil(r["review_fraction"] * r["transactions"]), d + ": ceil K")
                self.check(0 <= r["TP_at_K"] <= min(r["K"], r["fraud"]), d + ": budget bounds")
                self.check(abs(r["precision_at_K"] - r["TP_at_K"] / r["K"]) <= TOL and abs(r["recall_at_K"] - r["TP_at_K"] / r["fraud"]) <= TOL, d + ": budget rates")
                b = base[r["review_fraction"]]
                self.check(r["K"] == b["K"] and r["tie_policy"] == "risk descending, event_key ascending, event_id ascending", d + ": matched K/ties")
                self.budgets.append({"dataset": d, "scope": "test", **r,
                                     "delta_TP_at_K_vs_baseline": r["TP_at_K"] - b["TP_at_K"],
                                     "delta_precision_at_K_pp": 100 * (r["precision_at_K"] - b["precision_at_K"]),
                                     "delta_recall_at_K_pp": 100 * (r["recall_at_K"] - b["recall_at_K"]),
                                     "source_file": f"datasets/{d}/tables/review_budgets.csv"})
        self.write_csv("review_budget_comparison.csv", self.budgets)

    def examples(self):
        for d, (_, selected, threshold) in DATASETS.items():
            leaves = self.ds(d, f"model_details/{selected}/leaf_rules.csv", "fitted model", False)
            for kind in ["TP", "FP", "FN"]:
                rel = f"examples/examples_{selected}_{kind}.json"
                records = self.ds(d, rel, "example")
                self.need(bool(records), d + ": nonempty " + kind + " examples")
                r = records[0]
                alert, positive = bool(r["alert"]), r["isFraud"] == 1
                self.check((alert, positive) == {"TP": (True, True), "FP": (True, False), "FN": (False, True)}[kind], d + ": case label " + kind)
                self.check(alert == (r["risk_score"] >= threshold), d + ": case threshold")
                self.check(r.get("snapshot_as_of") is None or r["snapshot_as_of"] < r["step"], d + ": case past snapshot")
                matches = [leaf for leaf in leaves if abs(leaf["risk_score"] - r["risk_score"]) <= TOL]
                self.cases.append({"dataset": d, "family": selected, "scope": "example from full test",
                                   "case": kind, **{k: r.get(k) for k in ["event_id", "event_key", "step", "src", "dst", "type", "amount", "payment_currency", "risk_score", "alert", "isFraud", "snapshot_as_of"]},
                                   "rule_path_verified": False, "score_matching_leaf_ids": ";".join(str(x["leaf_id"]) for x in matches),
                                   "attribution": "score corresponds to unique leaf; feature path NOT verified" if len(matches) == 1 else "leaf ambiguous or unmatched; path NOT verified",
                                   "source_file": f"datasets/{d}/{rel}"})
        self.write_csv("case_examples.csv", self.cases)
        return "JSON examples thiếu các feature cần để xác minh toàn bộ rule path; score matching không thay thế feature verification."

    def add_evidence(self, d, component, observation, source, limitation, scope="full"):
        claim = f"{d}-{component}-{len(self.evidence)+1:02d}"
        self.evidence.append({"claim_id": claim, "dataset": d, "component": component, "scope": scope,
                              "observation": observation, "source_file": source, "limitation": limitation})

    def structural(self):
        for d, (_, selected, _) in DATASETS.items():
            ov = next(r for r in self.overview if r["dataset"] == d)
            deg = self.ds(d, "tables/degree_distribution.csv", "full")
            comm = self.ds(d, "tables/community_size_distribution.csv", "full")
            motif = self.ds(d, "tables/motif_coverage.csv", "full/test")
            self.ds(d, "tables/baseline_summary.csv", "full baseline audit")
            self.check(sum(r["account_count"] for r in deg) == ov["accounts"], d + ": degree accounts")
            self.check(sum(r["degree"] * r["account_count"] for r in deg) == 2 * ov["transactions"], d + ": degree sum=2E including loops")
            self.check(sum(r["member_count"] * r["count"] for r in comm) == ov["accounts"], d + ": community members")
            self.check(sum(r["count"] for r in comm) == ov["communities"], d + ": community count")
            self.check(ov["internal_edges"] + ov["cross_edges"] == ov["transactions"], d + ": edge partitions")
            self.add_evidence(d, "C", f"V={ov['accounts']}; E={ov['transactions']}; mean degree={ov['mean_total_degree']:.4f}", f"datasets/{d}/tables/degree_distribution.csv", "Full descriptive graph; không xác nhận power-law hoặc predictive causality.")
            self.add_evidence(d, "L", f"communities={ov['communities']}; internal={ov['internal_edges']}; cross={ov['cross_edges']}", f"datasets/{d}/tables/community_size_distribution.csv;tables/dataset_overview.csv", "LPA 5 iterations; community không phải CC/fraud ring; internal=0 không chứng minh bipartite.")
            for r in motif:
                n = ov["transactions"] if r["scope"] == "full" else ov["test_transactions"]
                p = ov["positives"] if r["scope"] == "full" else ov["test_positives"]
                self.check(r["transactions"] == n and r["positives"] == p, d + ": motif population")
                self.check(0 <= r["covered_positives"] <= r["covered_transactions"] <= n, d + ": motif bounds")
                self.check(abs(r["positive_coverage"] - r["covered_positives"] / p) <= TOL, d + ": motif coverage")
                fraction = ratio(r["covered_positives"], r["covered_transactions"])
                self.check(r["positive_fraction_when_present"] is None if fraction is None else abs(fraction - r["positive_fraction_when_present"]) <= TOL, d + ": motif fraction")
                if r["motif"] in {"cycle3_count", "relay_168h", "fanin_168h"}:
                    self.add_evidence(d, "M", f"{r['motif']}: covered={r['covered_transactions']}; positives={r['covered_positives']}; positive coverage={100*r['positive_coverage']:.2f}%", f"datasets/{d}/tables/motif_coverage.csv", "Các tập overlap; coverage không phải classifier recall hoặc TP.", r["scope"])
            used = [r for r in self.usage if r["dataset"] == d and r["family"] == selected and r["used_in_split"]]
            for component in ["T", "C", "M", "L"]:
                names = ", ".join(r["feature"] for r in used if r["group"] == component) or "Không có feature được dùng trong split"
                self.add_evidence(d, component, f"Selected {selected}: {names}", f"datasets/{d}/tables/feature_importance.csv;datasets/{d}/model_details/{selected}/tree_nodes.csv", "Impurity importance / fitted splits; không phải đóng góp nhân quả hoặc row-level attribution.", "fitted training-prefix model")
            temporal_path = self.bundle / f"datasets/{d}/tables/test_temporal_stability.csv"
            if temporal_path.is_file():
                rows = self.ds(d, "tables/test_temporal_stability.csv")
                for family in ["transaction_only", selected]:
                    periods = [r for r in rows if r["model"] == family]
                    self.need(len(periods) == 5, d + ": five temporal periods " + family)
                    m = next(r for r in self.models if r["dataset"] == d and r["family"] == family)
                    for r in periods:
                        validate_confusion(r, self.check, d + ": temporal " + family)
                    for k in ["TP", "FP", "FN", "TN", "alerts"]:
                        self.check(sum(r[k] for r in periods) == m[k], d + ": period sum " + k)
                    self.temporal.extend({"dataset": d, "scope": "test period", **r, "source_file": f"datasets/{d}/tables/test_temporal_stability.csv"} for r in periods)
                baseline = {r["test_period"]: r for r in rows if r["model"] == "transaction_only"}
                for r in [r for r in rows if r["model"] == selected]:
                    self.check(r["transactions"] == baseline[r["test_period"]]["transactions"] and r["fraud"] == baseline[r["test_period"]]["fraud"], d + ": same temporal population")
            else:
                self.findings.append({"checkpoint": self.phase, "status": "LIMITED", "check": d + ": temporal export missing"})
        self.write_csv("structural_evidence_matrix.csv", self.evidence)
        self.write_csv("temporal_comparison.csv", self.temporal)

    def figures(self):
        # Config/font caches are directed to this new output only.
        os.environ["MPLCONFIGDIR"] = str(self.output / ".mplconfig")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
        dest = self.output / "figures"
        dest.mkdir(exist_ok=True)
        colors = ["#2864a5", "#2b876e", "#d68c32", "#8d60a8"]
        fig, axes = plt.subplots(2, 1, figsize=(13, 9), layout="constrained")
        for ax, d in zip(axes, DATASETS):
            rows = [r for r in self.models if r["dataset"] == d]
            for i, k in enumerate(METRICS):
                ax.bar([j + (i-1.5)*0.19 for j in range(9)], [100*r[k] for r in rows], width=.18, label=k.replace("average_precision", "AP"), color=colors[i])
            ax.set_xticks(range(9), [r["family"] + (" *" if r["selected_on_validation"] else "") for r in rows], rotation=22, ha="right", fontsize=8)
            ax.set_title(d + " | full test holdout | * validation-selected")
            ax.set_ylabel("Percent (%)")
            ax.legend(ncol=4, fontsize=8)
        fig.savefig(dest/"metric_comparison.png", dpi=160); plt.close(fig)
        fig, axes = plt.subplots(2, 1, figsize=(13, 9), layout="constrained")
        for ax, d in zip(axes, DATASETS):
            rows = [r for r in self.deltas if r["dataset"] == d]
            for i, k in enumerate(METRICS):
                ax.bar([j + (i-1.5)*.19 for j in range(len(rows))], [r["delta_"+k+"_pp"] for r in rows], width=.18, label=k.replace("average_precision", "AP"), color=colors[i])
            ax.axhline(0, color="#555", linewidth=.7)
            ax.set_xticks(range(len(rows)), [r["contrast"] for r in rows], rotation=24, ha="right", fontsize=8)
            ax.set_title(d + " | enhanced minus reference (family thresholds may differ)")
            ax.set_ylabel("Percentage points")
            ax.legend(ncol=4, fontsize=8)
        fig.savefig(dest/"ablation_deltas.png", dpi=160); plt.close(fig)
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
        for i, (d, (_, selected, _)) in enumerate(DATASETS.items()):
            for family in dict.fromkeys(["transaction_only", "full_fusion", selected]):
                rows = sorted([r for r in self.budgets if r["dataset"] == d and r["model"] == family], key=lambda r:r["K"])
                for j, k in enumerate(["precision_at_K", "recall_at_K"]):
                    axes[i,j].plot([r["K"] for r in rows], [100*r[k] for r in rows], marker="o", label=family)
                    axes[i,j].set_title(d + " | " + k)
                    axes[i,j].set_xlabel("K reviewed transactions"); axes[i,j].set_ylabel("Percent (%)")
                    axes[i,j].legend(fontsize=8)
        fig.savefig(dest/"review_budgets.png", dpi=160); plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(13, 6), layout="constrained")
        for ax, (d, (_, selected, _)) in zip(axes, DATASETS.items()):
            rows = sorted([r for r in self.usage if r["dataset"] == d and r["family"] == selected and r["importance"] > 0], key=lambda r:r["importance"])
            ax.barh([r["feature"] + " ["+r["group"]+"]" for r in rows], [100*r["importance"] for r in rows], color="#2864a5")
            ax.set_title(d + " | " + selected); ax.set_xlabel("Impurity importance (%)")
        fig.savefig(dest/"feature_importance.png", dpi=160); plt.close(fig)
        self.check(len(list(dest.glob("*.png"))) == 4, "Four PNG charts produced")

    def report(self):
        self.structural()
        if any(f["status"] == "FAIL" for f in self.findings if f["checkpoint"] == self.phase):
            raise ValueError("Structural checks failed; report withheld")
        self.figures()
        lines = ["# GraphGuard: kết nối bằng chứng và ablation", "",
                 "## 1. Câu hỏi nghiên cứu và phạm vi", "",
                 "Phân tích này nối cấu trúc full graph, feature được cây thực sự sử dụng và hiệu quả screening trên test holdout. "
                 "Tất cả tính toán dùng aggregate exports đã có; không chạy lại Spark, train hoặc scoring.", "",
                 "Câu hỏi: C/M/L cung cấp ngữ cảnh gì, model có dùng không, và khi thêm/bỏ nhóm thì ranking, operating point và khối lượng review thay đổi thế nào?", "",
                 "T = transaction attributes; C = Degree/PageRank và seen flags; M = motif/history; L = LPA context. Novelty là đối chứng riêng.", "",
                 "Luồng bằng chứng: **Full descriptive graph → Feature importance / frozen rules → Ablation / metrics / cùng review budget → Insight riêng dataset**.", "",
                 "Validation: 3-fold walk-forward, freeze family/threshold rồi refit prefix ≤80%; test sau cutoff. C/L predictive dùng snapshot quá khứ; M dùng strict-past. "
                 "Full graph không được diễn giải thành feature biết tương lai. Test nội bộ đã được đọc trong phát triển; không phải untouched external benchmark.", "",
                 "Phương pháp: " + self.source_link("02_METHODS_AND_PARAMETERS.md") + ". Giới hạn evidence: " + self.source_link("06_RELIABILITY_AND_VALIDATION.md") + ".", "",
                 "## 2. Cấu trúc full graph", ""]
        lines += md_table(self.overview, [("dataset","Dataset"),("transactions","Full transactions"),("accounts","Accounts"),("mean_total_degree","Mean degree"),("communities","LPA communities"),("internal_edges","Internal edges"),("cross_edges","Cross edges")])
        lines += ["", "Nguồn: " + self.source_link("tables/dataset_overview.csv") + ". Degree sum=2E, member totals và edge partitions được kiểm tra lại từ exports.", "",
                  "IBM có mean degree cao hơn PaySim; điều này mô tả độ kết nối, chưa xác nhận power-law hoặc lý giải nhân quả hiệu năng. "
                  "PaySim internal edges=0 ở LPA 5 vòng đã chạy; không chứng minh toàn graph bipartite hoặc mọi account là bất thường.", "",
                  "Các motif dưới đây là coverage của những tập chồng lấp, không phải TP hoặc recall của classifier:", ""]
        lines += md_table([r for r in self.evidence if r["component"] == "M" and r["scope"] in {"full", "test"}], [("claim_id","Claim"),("dataset","Dataset"),("scope","Scope"),("observation","Quan sát")])
        for d in DATASETS:
            lines += ["", self.source_link(f"datasets/{d}/tables/motif_coverage.csv") + "; baseline audit tách riêng: " + self.source_link(f"datasets/{d}/tables/baseline_summary.csv") + "."]
        lines += ["", "## 3. Feature được cung cấp và thực sự sử dụng", "",
                  "Đủ feature trong family không có nghĩa cây dùng tất cả. Danh sách đầy đủ: [feature usage](feature_usage.csv); "
                  "[allowlists](sources/tables/exact_feature_allowlists.csv). Importance là impurity importance; không phải tỷ lệ cải thiện fraud detection.", ""]
        selected_usage = [r for r in self.usage if r["selected_on_validation"] and r["used_in_split"]]
        lines += md_table(selected_usage, [("dataset","Dataset"),("family","Selected family"),("group","Nhóm"),("feature","Feature dùng trong split"),("importance","Importance", "percent")])
        for d, (_, selected, _) in DATASETS.items():
            lines += ["", self.source_link(f"datasets/{d}/tables/feature_importance.csv") + "; " + self.source_link(f"datasets/{d}/model_details/{selected}/leaf_rules.csv") + "."]
        lines += ["", "IBM selected tree dùng C, M và L; PaySim selected tree dùng receiver history `receiver_in_168h`, không phải fan-in/fan-out trực tiếp. "
                  "PaySim L features có trong cấu hình nhưng không dùng trong split của selected tree. Không suy luận C=0 ở mọi transaction vì selected model không chứa C.", "",
                  "## 4. Toàn bộ 18 cấu hình và ablation", "",
                  "Mỗi dòng là toàn bộ test holdout tương ứng, không phải sample. Selected giữ theo validation. Threshold khác nhau giữa family phải được đọc cùng metrics.", ""]
        lines += md_table(self.models, [("dataset","Dataset"),("family","Family"),("threshold","Threshold"),("selected_on_validation","Selected"),("TP","TP"),("FP","FP"),("FN","FN"),("alerts","Alerts")] + [(k,k.replace("average_precision","AP"),"percent") for k in METRICS])
        lines += ["", "Nguồn và confusions đầy đủ: [model comparison](model_comparison.csv). AP được kiểm tra lại từ grouped-score bins cho cả 18 model.", "",
                  "### Chênh lệch operating point", "",
                  "Delta rate tính bằng điểm phần trăm (pp); count tính bằng số giao dịch. Đây là khác biệt giữa cấu hình đã fit, chưa phải đóng góp nhân quả của nhóm feature.", ""]
        lines += md_table(self.deltas, [("dataset","Dataset"),("contrast","Contrast"),("enhanced_threshold","θ enhanced"),("reference_threshold","θ reference"),("delta_precision_pp","ΔP pp"),("delta_recall_pp","ΔR pp"),("delta_F1_pp","ΔF1 pp"),("delta_average_precision_pp","ΔAP pp"),("delta_alerts","ΔAlerts"),("delta_TP","ΔTP"),("delta_FP","ΔFP")])
        lines += ["", "Đối chiếu nguồn: [ablation deltas](ablation_deltas.csv). Hai file graph_contributions gốc được kiểm tra lại từng delta.", "",
                  "## 5. So sánh cùng khối lượng review", "",
                  "Budget 0.1%, 0.5%, 1% dùng K=ceil(f×Ntest). Tie policy giữ nguyên: score giảm dần, event_key và event_id tăng dần. "
                  "K tương đương chỉ trong cùng dataset. Không dựng lại danh sách top-K từ examples.", ""]
        highlighted = [r for r in self.budgets if r["model"] in {"transaction_only", "full_fusion", DATASETS[r["dataset"]][1]}]
        lines += md_table(highlighted, [("dataset","Dataset"),("model","Family"),("K","K"),("TP_at_K","TP@K"),("precision_at_K","P@K","percent"),("recall_at_K","R@K","percent"),("delta_TP_at_K_vs_baseline","ΔTP vs T")])
        lines += ["", "Đủ 54 dòng: [review budget comparison](review_budget_comparison.csv).", ""]
        for d, (_, selected, _) in DATASETS.items():
            rows = [r for r in self.budgets if r["dataset"] == d and r["model"] == selected]
            parts = [f"K={r['K']:,}: ΔTP={r['delta_TP_at_K_vs_baseline']:+,}, ΔP={r['delta_precision_at_K_pp']:+.2f} pp, ΔR={r['delta_recall_at_K_pp']:+.2f} pp" for r in sorted(rows,key=lambda r:r['K'])]
            lines += [f"**{d}, selected so với T:** " + "; ".join(parts) + ". "
                      "Đây là kiểm tra ranking ở cùng khối lượng review; lợi ích có thể khác nhau theo K.", ""]
        lines += ["### Biến thiên theo thời gian", "",
                  "Không lấy trung bình F1 các kỳ làm full-test F1; kiểm tra tổng confusion counts của 5 kỳ.", ""]
        for d, (_, selected, _) in DATASETS.items():
            rows = [r for r in self.temporal if r["dataset"] == d and r["model"] == selected]
            if rows:
                base = {r["test_period"]:r for r in self.temporal if r["dataset"] == d and r["model"] == "transaction_only"}
                improvements = sum(r["F1"] > base[r["test_period"]]["F1"] for r in rows)
                lines += [f"**{d}:** selected test-period F1 dao động {100*min(r['F1'] for r in rows):.2f}%–{100*max(r['F1'] for r in rows):.2f}%; "
                          f"F1 cao hơn baseline ở {improvements}/5 kỳ. Đây là biến thiên quan sát, không chứng nhận ổn định ngoài dataset. " + self.source_link(f"datasets/{d}/tables/test_temporal_stability.csv") + ".", ""]
        lines += ["## 6. TP / FP / FN minh họa", "",
                  "Chọn record đầu tiên của mỗi loại từ selected-model JSON; 6 case không đại diện thống kê cho toàn bộ test. "
                  "Tất cả `rule_path_verified=false`: JSON thiếu feature để kiểm tra path. Score khớp leaf không xác nhận từng feature condition.", ""]
        lines += md_table(self.cases, [("dataset","Dataset"),("case","Case"),("event_id","Event ID"),("type","Type"),("amount","Amount"),("payment_currency","Currency"),("risk_score","Score"),("alert","Alert"),("score_matching_leaf_ids","Score-matching leaves")])
        lines += ["", "Event key, snapshot và nguồn: [case examples](case_examples.csv). Không so raw amounts khác currency hoặc cộng witness thành test TP.", "",
                  "## 7. Insights và kết luận", ""]
        for d, (_, selected, _) in DATASETS.items():
            a = next(r for r in self.models if r["dataset"] == d and r["family"] == selected)
            b = next(r for r in self.models if r["dataset"] == d and r["family"] == "transaction_only")
            lines += [f"**{d}:** validation-selected `{selected}` cho P {100*b['precision']:.2f}% → {100*a['precision']:.2f}%, "
                      f"R {100*b['recall']:.2f}% → {100*a['recall']:.2f}%, F1 {100*b['F1']:.2f}% → {100*a['F1']:.2f}%, "
                      f"AP {100*b['average_precision']:.2f}% → {100*a['average_precision']:.2f}%; "
                      f"alerts {b['alerts']:,} → {a['alerts']:,}, TP {b['TP']:,} → {a['TP']:,}, FP {b['FP']:,} → {a['FP']:,}. "
                      + self.source_link(f"datasets/{d}/tables/test_metrics.csv") + ".", ""]
        lines += ["IBM fusion thu hẹp danh sách cảnh báo và tăng precision/AP nhẹ, đồng thời giảm recall/F1 tại operating point đã freeze. "
                  "Cây sử dụng cả C/M/L, nhưng việc có split không chứng minh từng nhóm làm tăng mọi metric. Community cross fraction là một feature cấu trúc, không phải nhãn nhóm phạm tội.", "",
                  "PaySim selected T+M+L có cùng metrics với T+M; importance/rules cho thấy L không được dùng trong selected tree. "
                  "Receiver history bổ sung ngữ cảnh, bao gồm thông tin thiếu lịch sử, chứ không chỉ sự hiện diện motif. Recall/F1/AP cao hơn baseline đi cùng nhiều FP hơn. "
                  "Full fusion có AP test cao hơn selected không phải lý do chọn lại winner bằng test.", "",
                  "Đóng góp của project là đánh giá giá trị ngữ cảnh đồ thị theo cấu trúc dataset, model được fit và ngân sách review. "
                  "Kết quả không đủ để công bố danh sách giao nhau C∩M∩L hoặc recall của cả đường dây.", "",
                  "### Giới hạn bắt buộc", "",
                  "- Chỉ kiểm tra lại aggregate exports; không revalidate millions-row predictions hoặc thực thi notebook gốc.",
                  "- Hai dataset synthetic, nhãn khác nhau; không gộp F1/confusion giữa dataset.",
                  "- Ablation giữa model đã fit, có thể khác threshold; chưa có paired row-level significance tests hoặc CI cho delta.",
                  "- Full motif coverage chồng lấp, zero coverage không đồng nghĩa không có fraud.",
                  "- Community là LPA output; không có đánh giá CC hoặc ring-level ground truth trong phân tích này.",
                  "- Case rule paths chưa xác minh; không tái dựng feature values hoặc xếp tier từ score.",
                  "- Không tái sử dụng checkpoint output cũ: rerun vào thư mục mới, input hashes/config được lưu để đối chiếu.", "",
                  "## 8. Biểu đồ và nghiệm thu", ""]
        for name, caption in [("metric_comparison", "Metrics toàn bộ test, đủ 18 models"), ("ablation_deltas", "Chênh lệch cấu hình theo điểm phần trăm"), ("review_budgets", "Precision/recall tại cùng K"), ("feature_importance", "Impurity importance của selected trees")]:
            lines += [f"![{caption}](figures/{name}.png)", ""]
        lines += ["[Checkpoint status](checkpoint_status.csv), [validation findings](validation_findings.csv), "
                  "[source inventory](source_inventory.csv), [input hashes](input_hashes.json), "
                  "[evidence matrix](structural_evidence_matrix.csv), [temporal comparison](temporal_comparison.csv).", "",
                  "Mỗi nguồn đã dùng có bản snapshot nguyên byte trong sources/. Các link hoạt động offline khi giữ nguyên thư mục generated."]
        md = "\n".join(lines)
        (self.output/"CONNECTED_RESULTS_REPORT.md").write_text(md, encoding="utf-8")
        (self.output/"CONNECTED_RESULTS_REPORT.html").write_text(render_html(md), encoding="utf-8")
        self.check(len(self.cases) == 6 and len(self.models) == 18 and len(self.budgets) == 54, "Report populations and cases")

    def preservation(self):
        # Persist manifests before validating all report links.
        self.write_csv("source_inventory.csv", self.inventory)
        self.write_json("input_hashes.json", self.inputs)
        for rel, old in self.inputs.items():
            self.check((self.bundle/rel).is_file() and digest(self.bundle/rel) == old, "Source unchanged: " + rel)
        for r in self.inventory:
            self.check(digest(self.output/"sources"/r["source_file"]) == r["sha256"], "Snapshot exact bytes: " + r["source_file"])
        report = self.output/"CONNECTED_RESULTS_REPORT.html"
        if report.is_file():
            text = report.read_text(encoding="utf-8")
            links = re.findall(r'(?:href|src)="([^"]+)"', text)
            self.check(bool(links), "HTML links present")
            for link in links:
                target = urlsplit(html.unescape(link))
                self.check(not target.scheme and not target.netloc, "Offline local link: " + link)
                p = (self.output/unquote(target.path)).resolve()
                self.check(self.output in p.parents and p.is_file(), "Link resolves within output: " + link)
            self.check("<script" not in text.lower(), "No external scripts or dynamic dependencies")
        else:
            self.check(False, "Report not produced")

    def run(self):
        self.phase_run("CP0", "Nguồn và provenance", self.sources)
        self.phase_run("CP1", "Metrics / confusion / grouped AP", self.metrics, ["CP0"])
        self.phase_run("CP2", "Allowlist / importance / tree rules", self.features, ["CP0", "CP1"])
        self.phase_run("CP3", "Ablation", self.ablation, ["CP1"])
        self.phase_run("CP4", "Review budget", self.budget, ["CP1"])
        self.phase_run("CP5", "Cases minh họa", self.examples, ["CP1", "CP2"])
        self.phase_run("CP6", "Cấu trúc / temporal / báo cáo / figures", self.report, ["CP0", "CP1", "CP2", "CP3", "CP4", "CP5"])
        self.phase_run("CP7", "Bảo toàn nguồn / offline links", self.preservation)
        complete = all(self.deps.get(cp) == "PASS" for cp in ["CP0", "CP1", "CP2", "CP3", "CP4", "CP6", "CP7"]) and self.deps.get("CP5") in {"PASS", "LIMITED"}
        self.write_json("completion.json", {"status": "COMPLETE" if complete else "INCOMPLETE", "checkpoint_status": self.deps,
                        "finding_count": len(self.findings), "failure_count": sum(f["status"] == "FAIL" for f in self.findings),
                        "input_files_including_copies": len(self.inputs), "no_spark": True,
                        "scope": "aggregate export validation; not full pipeline acceptance"})
        return 0 if complete else 1


def format_cell(value, mode=None):
    if value is None:
        return "N/A"
    if mode == "percent":
        return f"{100*value:.2f}%"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}" if abs(value) < 1 else f"{value:.2f}"
    return str(value)


def md_table(rows, columns):
    def safe(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    return ["| " + " | ".join(c[1] for c in columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"] + [
        "| " + " | ".join(safe(format_cell(r.get(c[0]), c[2] if len(c)>2 else None)) for c in columns) + " |" for r in rows]


def render_html(md):
    # Deliberately small Markdown subset used by this builder; no third-party runtime.
    def inline(text):
        text = html.escape(text)
        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2" loading="lazy">', text)
        text = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    out, table, ul = [], False, False
    for line in md.splitlines():
        if line.startswith("| "):
            cells = line.strip("| ").split(" | ")
            if all(re.fullmatch(r"[-: ]+", c) for c in cells):
                continue
            if not table:
                out.append('<div class="table"><table><thead><tr>' + "".join("<th>"+inline(c)+"</th>" for c in cells) + "</tr></thead><tbody>")
                table = True
            else:
                out.append("<tr>" + "".join("<td>"+inline(c)+"</td>" for c in cells) + "</tr>")
            continue
        if table:
            out.append("</tbody></table></div>"); table = False
        if line.startswith("- "):
            if not ul:
                out.append("<ul>"); ul = True
            out.append("<li>"+inline(line[2:])+"</li>"); continue
        if ul:
            out.append("</ul>"); ul = False
        if line.startswith("#"):
            level = len(line)-len(line.lstrip("#"))
            out.append(f"<h{level}>"+inline(line[level:].strip())+f"</h{level}>")
        elif line:
            out.append("<p>"+inline(line)+"</p>")
    if table: out.append("</tbody></table></div>")
    if ul: out.append("</ul>")
    return '<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>GraphGuard evidence và ablation</title><style>body{font:16px/1.65 system-ui,Segoe UI,sans-serif;max-width:1280px;margin:40px auto;padding:0 24px;color:#203047;background:#fafbfd}h1,h2,h3{line-height:1.3;color:#164e76}h2{margin-top:2.5em}a{color:#185a97}img{max-width:100%;height:auto;background:white}.table{overflow-x:auto;border:1px solid #dae2ec;border-radius:6px;margin:20px 0}table{border-collapse:collapse;font-size:13px;width:100%;background:white}td,th{padding:9px 12px;border-bottom:1px solid #e3e9ef;text-align:left;vertical-align:top}th{background:#e9f1f8;white-space:nowrap}tr:nth-child(even){background:#f5f8fc}code{background:#edf1f5;padding:2px 4px}@media print{body{margin:0;max-width:none;font-size:11px}.table{overflow:visible}td,th{padding:4px}img{max-height:90vh;object-fit:contain}}</style><main>' + "\n".join(out) + "</main></html>"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.platform != "win32":
        parser.error("Use native Windows repository .venv Python 3.12")
    sys.exit(Analysis(args.bundle_root, args.output_dir).run())
