"""Revise the two local reports from frozen aggregate evidence, without Spark.

Native Windows / repository .venv Python 3.12 only. Build into a fresh revision
directory, validate, then optionally update the two user-facing reports. Every
updated artifact is backed up; original computations and their hashes stay intact.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import unquote, urlsplit


BASE = Path(__file__).resolve().parent
REPO = BASE.parent.parent
BUNDLE = REPO / "GraphGuard_FULL_Report_Bundle_2026-10-24"
SELECTED = {"ibm_aml": "full_fusion", "paysim": "without_centrality"}
LABEL = {"ibm_aml": "IBM AML", "paysim": "PaySim"}
SHORT = {"transaction_only": "Giao dịch", "transaction_novelty": "Giao dịch + đã thấy tài khoản",
         "full_fusion": "Đủ C/M/L", "without_centrality": "Lịch sử + cộng đồng",
         "motif_assisted": "Giao dịch + lịch sử"}
FRACTIONS = (0.001, 0.005, 0.01)
TOL = 1e-9


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    if value == "":
        return None
    if value in ("True", "False"):
        return value == "True"
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return [{k: number(v) for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def n(value):
    return f"{int(value):,}".replace(",", ".")


def dec(value, digits=2):
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value, digits=2):
    return "—" if value is None else dec(100 * value, digits) + "%"


def inline(text):
    text = html.escape(str(text))
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


CSS = """
:root{--ink:#233746;--muted:#536879;--navy:#123d50;--teal:#087f79;--line:#d9e3e9;--paper:#fff;--bg:#f3f6f8;--amber:#9a5b23}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:var(--ink);background:var(--bg);font:17px/1.72 'Segoe UI',Arial,sans-serif}
main{max-width:1160px;margin:auto;padding:38px 34px 68px}header{padding:26px 0 32px;border-bottom:3px solid var(--teal)}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--teal)}h1{font-size:43px;line-height:1.16;letter-spacing:-.025em;max-width:940px;margin:16px 0;color:var(--navy)}
.lead{font-size:22px;line-height:1.55;max-width:940px}h2{font-size:28px;line-height:1.3;color:var(--navy);margin:0 0 20px}h3{font-size:20px;line-height:1.4;color:var(--navy)}p{margin:14px 0}a{color:#066a78;text-underline-offset:3px}a:focus-visible,summary:focus-visible{outline:3px solid #bd682c;outline-offset:4px}
section{padding:38px 0;border-bottom:1px solid var(--line);scroll-margin-top:18px}.small,figcaption{font-size:14px;line-height:1.6;color:var(--muted)}.scope{padding:17px 20px;border:1px solid var(--line);border-radius:8px;background:#fff;font-size:14px;margin-top:22px}
nav{margin:26px 0 6px;padding:20px 24px;background:#e7eff2;border-radius:10px}nav ol{display:grid;grid-template-columns:1fr 1fr;column-gap:28px;margin:0;padding-left:22px}nav li{padding:4px 0;font-size:15px}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin:26px 0 6px}.card{background:#fff;border:1px solid var(--line);border-top:4px solid var(--teal);border-radius:10px;padding:20px}.card h3{font-size:18px;margin:0 0 12px}.card strong.metric{display:block;font-size:31px;line-height:1.2;color:var(--navy)}.card p{font-size:15px;margin-bottom:0}
.table{overflow-x:auto;border:1px solid var(--line);border-radius:8px;margin:22px 0;background:#fff}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.55}caption{text-align:left;padding:12px 15px;background:#edf3f5;font-weight:600}th,td{padding:12px 14px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#e5eff2;color:var(--navy);font-weight:650}tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f7fafb}td:first-child{font-weight:600}
figure{margin:25px 0;padding:15px;background:#fff;border:1px solid var(--line);border-radius:10px}figure img{display:block;width:100%;height:auto}figcaption{padding:12px 7px 3px}.callout{padding:19px 22px;background:#e3f0ee;border-left:4px solid var(--teal);margin:22px 0}.callout.caution{background:#faf0e5;border-color:var(--amber)}.callout p{margin:0}ul{padding-left:24px}li{margin:9px 0}code{font:13px/1.5 Consolas,monospace;background:#e9eff2;padding:2px 4px;overflow-wrap:anywhere}details{padding:20px 22px;border:1px solid var(--line);background:#fff;border-radius:10px;margin:20px 0}summary{font-weight:650;color:var(--navy);cursor:pointer}footer{padding-top:24px;font-size:13px;color:var(--muted)}.technical main{max-width:1320px}.technical table{font-size:13px}.technical h1{font-size:40px}
@media(max-width:760px){main{padding:22px 16px 42px}h1,.technical h1{font-size:32px}.lead{font-size:20px}h2{font-size:25px}.cards{grid-template-columns:1fr}nav ol{grid-template-columns:1fr}th,td{padding:10px}figure{padding:5px}}
@media print{body{background:#fff;font-size:11pt}main,.technical main{max-width:none;padding:0}h1,.technical h1{font-size:26pt}h2{font-size:18pt;break-after:avoid}h3{break-after:avoid}header{padding-top:0}nav{display:none}.cards{gap:10px}.card{break-inside:avoid}.card strong.metric{font-size:22pt}table{font-size:9pt}.technical table{font-size:8pt}thead{display:table-header-group}tr,figure,.callout{break-inside:avoid}figure{padding:6px}figcaption,.small{font-size:9pt}.table{overflow:visible}a{color:inherit}section{padding:22px 0}.scope{font-size:9pt}details{break-inside:auto}footer{font-size:8pt}}
"""


class Document:
    def __init__(self, title, subtitle, technical=False):
        self.title, self.subtitle, self.technical = title, subtitle, technical
        self.parts, self.md, self.toc = [], ["# " + title, "", subtitle, ""], []
        self.open_section = False

    def section(self, title, anchor):
        if self.open_section:
            self.parts.append("</section>")
        self.parts.append(f'<section id="{anchor}"><h2>{inline(title)}</h2>')
        self.md += ["## " + title, ""]
        self.toc.append((title, anchor))
        self.open_section = True

    def p(self, text, small=False):
        self.parts.append(f'<p class="{"small" if small else "text"}">{inline(text)}</p>')
        self.md += [text, ""]

    def note(self, text, caution=False):
        self.parts.append(f'<aside class="callout{" caution" if caution else ""}"><p>{inline(text)}</p></aside>')
        self.md += ["> " + text, ""]

    def bullets(self, items):
        self.parts.append("<ul>" + "".join("<li>" + inline(x) + "</li>" for x in items) + "</ul>")
        self.md += ["- " + x for x in items] + [""]

    def h3(self, text):
        self.parts.append("<h3>" + inline(text) + "</h3>")
        self.md += ["### " + text, ""]

    def table(self, headers, rows, caption):
        self.parts.append('<div class="table"><table><caption>' + inline(caption) + "</caption><thead><tr>" +
                          "".join('<th scope="col">' + inline(x) + "</th>" for x in headers) + "</tr></thead><tbody>" +
                          "".join("<tr>" + "".join("<td>" + inline(x) + "</td>" for x in row) + "</tr>" for row in rows) +
                          "</tbody></table></div>")
        self.md += ["**" + caption + "**", "", "| " + " | ".join(headers) + " |",
                    "| " + " | ".join("---" for _ in headers) + " |"]
        self.md += ["| " + " | ".join(str(x).replace("|", "\\|") for x in row) + " |" for row in rows] + [""]

    def figure(self, name, alt, caption):
        path = "figures_insights/" + name + ".png"
        self.parts.append(f'<figure><img src="{path}" alt="{html.escape(alt, quote=True)}"><figcaption>{inline(caption)}</figcaption></figure>')
        self.md += [f"![{alt}]({path})", "", caption, ""]

    def cards(self, cards):
        self.parts.append('<div class="cards">' + "".join('<article class="card"><h3>' + inline(title) +
                          '</h3><strong class="metric">' + inline(value) + "</strong><p>" + inline(text) +
                          "</p></article>" for title, value, text in cards) + "</div>")
        self.md += ["- **" + a + ": " + b + "** — " + c for a, b, c in cards] + [""]

    def details(self, title, fn):
        self.parts.append("<details open><summary>" + inline(title) + "</summary>")
        self.h3(title)
        fn()
        self.parts.append("</details>")

    def save(self, folder, stem):
        if self.open_section:
            self.parts.append("</section>")
        nav = '<nav aria-label="Mục lục"><ol>' + "".join(f'<li><a href="#{anchor}">{inline(title)}</a></li>' for title, anchor in self.toc) + "</ol></nav>"
        scope = ("Phân tích thăm dò từ kết quả đã xuất · Hai bộ dữ liệu mô phỏng · IBM: laundering; PaySim: fraud. "
                 "Test nội bộ đã được xem trong quá trình phát triển. Mô hình/ngưỡng giữ theo mean validation F1; "
                 "các mức ngân sách test không được dùng để chọn lại phương án tối ưu.")
        page = ('<!doctype html>\n<html lang="vi"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>' + html.escape(self.title) + '</title><style>' + CSS + '</style></head>'
                f'<body class="{"technical" if self.technical else "business"}"><main><header>'
                '<div class="eyebrow">GraphGuard / Phân tích tổng hợp / Cập nhật 28.10.2026</div><h1>' + inline(self.title) +
                '</h1><p class="lead">' + inline(self.subtitle) + '</p><div class="scope">' + inline(scope) +
                '</div></header>' + nav + "\n".join(self.parts) +
                '<footer>Chỉ tổng hợp và diễn giải evidence đã có. Không chạy lại Spark, huấn luyện hoặc chấm điểm giao dịch. '
                'Số liệu lịch sử và định danh thực thi được giữ nguyên; kiểm tra bản báo cáo này có manifest riêng.</footer></main></body></html>')
        self.md[4:4] = [scope, ""]
        (folder / (stem + ".html")).write_text(page, encoding="utf-8")
        (folder / (stem + ".md")).write_text("\n".join(self.md), encoding="utf-8")


class Evidence:
    def __init__(self, folder):
        self.root = folder
        self.checks = []
        self.models = read_csv(folder / "model_comparison.csv")
        self.budgets = read_csv(folder / "review_budget_comparison.csv")
        self.usage = read_csv(folder / "feature_usage.csv")
        self.temporal = read_csv(folder / "temporal_comparison.csv")
        self.overview = read_csv(folder / "sources/tables/dataset_overview.csv")
        self.cohorts, self.marginal, self.periods, self.ties, self.structure = [], [], [], [], []
        self.validate_frozen_sources()
        self.derive()

    def check(self, ok, label):
        self.checks.append({"check": label, "pass": bool(ok)})
        if not ok:
            raise ValueError(label)

    def model(self, ds, family=None):
        return next(r for r in self.models if r["dataset"] == ds and r["family"] == (family or SELECTED[ds]))

    def budget(self, ds, family, fraction):
        return next(r for r in self.budgets if r["dataset"] == ds and r["model"] == family and r["review_fraction"] == fraction)

    def motif(self, ds, motif):
        return next(r for r in self.cohorts if r["dataset"] == ds and r["motif"] == motif)

    def validate_frozen_sources(self):
        inventory = read_csv(self.root / "source_inventory.csv")
        for r in inventory:
            self.check(sha(self.root / "sources" / r["source_file"]) == r["sha256"], "historical source SHA-256: " + r["source_file"])
        complete = json.loads((self.root / "completion.json").read_text(encoding="utf-8"))
        self.check(complete["status"] == "COMPLETE" and complete["failure_count"] == 0,
                   "historical aggregate validation completed without failures")
        for ds in SELECTED:
            raw_models = read_csv(self.root / f"sources/datasets/{ds}/tables/test_metrics.csv")
            for r in [x for x in self.models if x["dataset"] == ds]:
                original = next(x for x in raw_models if x["model"] == r["family"])
                for key in ("threshold", "TP", "FP", "FN", "TN", "alerts", "precision", "recall", "F1", "average_precision"):
                    self.check(abs(r[key] - original[key]) < TOL, ds + "/" + r["family"] + ": metric matches source " + key)
                self.check(r["test_transactions"] == original["transactions"] and r["test_positives"] == original["fraud"],
                           ds + "/" + r["family"] + ": model population matches source")
            raw_budgets = read_csv(self.root / f"sources/datasets/{ds}/tables/review_budgets.csv")
            for r in [x for x in self.budgets if x["dataset"] == ds]:
                original = next(x for x in raw_budgets if x["model"] == r["model"] and x["review_fraction"] == r["review_fraction"])
                for key in ("K", "transactions", "fraud", "TP_at_K", "precision_at_K", "recall_at_K"):
                    self.check(abs(r[key] - original[key]) < TOL, ds + "/" + r["model"] + ": budget matches source " + key)

    def derive(self):
        self.check(len(self.models) == 18 and len(self.budgets) == 54, "18 models and 54 exported budget rows")
        for r in self.models:
            tp, fp, fn, tn = (r[k] for k in ("TP", "FP", "FN", "TN"))
            self.check(tp + fp == r["alerts"] and tp + fn == r["test_positives"] and tp + fp + fn + tn == r["test_transactions"], f'{r["dataset"]}/{r["family"]}: confusion populations')
            for key, value in (("precision", tp / (tp + fp)), ("recall", tp / (tp + fn)), ("F1", 2 * tp / (2 * tp + fp + fn))):
                self.check(abs(value - r[key]) < TOL, f'{r["dataset"]}/{r["family"]}: {key}')
        for r in self.budgets:
            self.check(r["K"] == math.ceil(r["review_fraction"] * r["transactions"]) and
                       abs(r["precision_at_K"] - r["TP_at_K"] / r["K"]) < TOL and
                       abs(r["recall_at_K"] - r["TP_at_K"] / r["fraud"]) < TOL,
                       f'{r["dataset"]}/{r["model"]}/{r["K"]}: K and rates')
        for ds in SELECTED:
            frozen = json.loads((self.root / f"sources/datasets/{ds}/provenance/frozen_rules.json").read_text(encoding="utf-8"))
            self.check(self.model(ds)["selected_on_validation"] and frozen["selection"]["family"] == SELECTED[ds] and
                       frozen["selection"]["threshold"] == self.model(ds)["threshold"], ds + ": frozen winner retained")
            motifs = read_csv(self.root / f"sources/datasets/{ds}/tables/motif_coverage.csv")
            for r in [x for x in motifs if x["scope"] == "test"]:
                covered, positives = r["covered_transactions"], r["covered_positives"]
                rate = positives / covered if covered else None
                prevalence = r["positives"] / r["transactions"]
                lift = rate / prevalence if rate is not None else None
                self.check(0 <= positives <= covered and abs(prevalence - r["population_prevalence"]) < TOL and
                           abs(positives / r["positives"] - r["positive_coverage"]) < TOL and
                           (rate is None and r["positive_fraction_when_present"] is None or rate is not None and abs(rate - r["positive_fraction_when_present"]) < TOL),
                           ds + "/" + r["motif"] + ": cohort denominators")
                self.cohorts.append({"dataset": ds, "scope": "test exploratory cohort; not model prediction", "motif": r["motif"],
                    "N_test": r["transactions"], "positive_test": r["positives"], "covered_transactions": covered,
                    "covered_positives": positives, "population_share": covered / r["transactions"],
                    "positive_coverage": r["positive_coverage"], "positive_rate_when_present": rate,
                    "population_prevalence": prevalence, "lift": lift,
                    "source_file": f"sources/datasets/{ds}/tables/motif_coverage.csv"})
            for family in ("transaction_only", "transaction_novelty", SELECTED[ds]):
                bs = [self.budget(ds, family, f) for f in FRACTIONS]
                self.check(all(b["TP_at_K"] >= a["TP_at_K"] for a, b in zip(bs, bs[1:])), ds + "/" + family + ": nested ranking counts")
                for a, b in zip(bs, bs[1:]):
                    dk, dtp = b["K"] - a["K"], b["TP_at_K"] - a["TP_at_K"]
                    self.marginal.append({"dataset": ds, "model": family, "from_fraction": a["review_fraction"],
                        "to_fraction": b["review_fraction"], "from_K": a["K"], "to_K": b["K"], "added_reviews": dk,
                        "added_TP": dtp, "added_FP": dk - dtp, "marginal_positive_rate": dtp / dk,
                        "scope": "same fitted model and exported deterministic tie order; not switch-policy evaluation",
                        "source_file": "review_budget_comparison.csv"})
                prs = read_csv(self.root / f"sources/datasets/{ds}/tables/pr_curve_{family}.csv")
                self.check(sum(x["transactions"] for x in prs) == self.model(ds, family)["test_transactions"], ds + "/" + family + ": score-bin population")
                cum_n = cum_p = 0
                ap = 0.0
                previous_score = math.inf
                for p in prs:
                    self.check(p["risk_score"] < previous_score and 0 <= p["positives"] <= p["transactions"], ds + "/" + family + ": score bin bounds")
                    previous_score = p["risk_score"]
                    cum_n += p["transactions"]
                    cum_p += p["positives"]
                    ap += p["positives"] / self.model(ds, family)["test_positives"] * cum_p / cum_n
                self.check(cum_p == self.model(ds, family)["test_positives"] and abs(ap - self.model(ds, family)["average_precision"]) < TOL, ds + "/" + family + ": AP from score bins")
                for b in bs:
                    above_n = above_p = 0
                    for p in prs:
                        if above_n + p["transactions"] >= b["K"]:
                            taken, total, pos = b["K"] - above_n, p["transactions"], p["positives"]
                            expected = above_p + taken * pos / total
                            variance = taken * (pos / total) * (1 - pos / total) * (total - taken) / (total - 1) if total > 1 else 0
                            lower = above_p + max(0, taken - (total - pos))
                            upper = above_p + min(taken, pos)
                            self.check(lower <= b["TP_at_K"] <= upper, ds + "/" + family + ": observed top-K feasible within boundary bin")
                            self.ties.append({"dataset": ds, "model": family, "K": b["K"], "review_fraction": b["review_fraction"],
                                "distinct_scores": len(prs), "boundary_score": p["risk_score"], "rows_above_boundary": above_n,
                                "positives_above_boundary": above_p, "boundary_rows": total, "boundary_positives": pos,
                                "taken_from_boundary": taken, "observed_TP": b["TP_at_K"], "expected_TP_random_boundary": expected,
                                "random_boundary_TP_sd": math.sqrt(variance), "minimum_possible_TP": lower, "maximum_possible_TP": upper,
                                "interpretation": "uniform sampling within tied score bin; SD is allocation sensitivity, not model uncertainty or significance",
                                "source_file": f"sources/datasets/{ds}/tables/pr_curve_{family}.csv"})
                            break
                        above_n += p["transactions"]
                        above_p += p["positives"]
            ov = next(r for r in self.overview if r["dataset"] == ds)
            degree = read_csv(self.root / f"sources/datasets/{ds}/tables/degree_distribution.csv")
            degree_one = next(r["account_count"] for r in degree if r["degree"] == 1)
            self.check(sum(r["account_count"] for r in degree) == ov["accounts"], ds + ": degree account total")
            self.structure.append({"dataset": ds, "scope": "full descriptive graph; not predictive feature snapshot",
                                   "accounts": ov["accounts"], "degree_one_accounts": degree_one,
                                   "degree_one_fraction": degree_one / ov["accounts"], "mean_degree": ov["mean_total_degree"],
                                   "source_file": f"sources/datasets/{ds}/tables/degree_distribution.csv"})
            a = sorted([r for r in self.temporal if r["dataset"] == ds and r["model"] == SELECTED[ds]], key=lambda x: x["test_period"])
            baseline = {r["test_period"]: r for r in self.temporal if r["dataset"] == ds and r["model"] == "transaction_only"}
            self.check(len(a) == len(baseline) == 5 and sum(r["fraud"] for r in a) == ov["test_positives"], ds + ": five temporal populations")
            for model in ("transaction_only", SELECTED[ds]):
                periods = [r for r in self.temporal if r["dataset"] == ds and r["model"] == model]
                self.check(all(sum(r[k] for r in periods) == self.model(ds, model)[k] for k in ("TP", "FP", "FN", "TN", "alerts")), ds + "/" + model + ": temporal confusion sums")
            for r in a:
                b = baseline[r["test_period"]]
                self.check(r["transactions"] == b["transactions"] and r["fraud"] == b["fraud"], ds + ": paired temporal populations")
                self.periods.append({"dataset": ds, "period": r["test_period"] + 1, "transactions": r["transactions"],
                    "positives": r["fraud"], "share_of_test_positives": r["fraud"] / ov["test_positives"],
                    "prevalence": r["prevalence"], "baseline_recall": b["recall"], "selected_recall": r["recall"],
                    "baseline_F1": b["F1"], "selected_F1": r["F1"], "delta_recall_pp": 100 * (r["recall"] - b["recall"]),
                    "source_file": f"sources/datasets/{ds}/tables/test_temporal_stability.csv"})
        self.leaves = read_csv(self.root / "sources/datasets/paysim/model_details/without_centrality/leaf_rules.csv")
        self.leaf14, self.leaf15 = (next(r for r in self.leaves if r["leaf_id"] == i) for i in (14, 15))
        self.parameters = json.loads((self.root / "sources/datasets/paysim/model_details/without_centrality/saved_model_parameters.json").read_text(encoding="utf-8"))
        labels = self.parameters[0]["saved_data"][0]["labelsArray"][0]
        self.check(labels == ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"], "saved categorical vocabulary for illustrated branch")
        self.check(self.leaf14["condition"].replace("receiver_in_168h <= 0.5", "receiver_in_168h > 0.5") == self.leaf15["condition"] and
                   "type_index NOT IN [0.0, 2.0, 3.0]" in self.leaf14["condition"] and
                   "type_index IN [0.0, 2.0, 3.0, 4.0]" in self.leaf14["condition"] and
                   self.leaf14["risk_score"] > self.leaf15["risk_score"], "leaf 14/15 differ only in receiver history; CASH_OUT branch")
        for ds in SELECTED:
            used = [r for r in self.usage if r["dataset"] == ds and r["family"] == SELECTED[ds] and r["used_in_split"]]
            self.check(abs(sum(r["importance"] for r in used) - 1) < TOL, ds + ": selected impurity importance sums to one")
            if ds == "paysim":
                self.check({r["feature"] for r in used} == {"type_index", "scaled_amount", "receiver_in_168h"}, "PaySim selected split features retained")


def plots(e, folder):
    os.environ["MPLCONFIGDIR"] = str(folder.parent / ".mplconfig_insights")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    folder.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titleweight": "bold", "figure.facecolor": "white"})
    colors = {"transaction_only": "#788c9d", "transaction_novelty": "#b67830", "selected": "#087f79"}
    def finish(fig, name):
        fig.savefig(folder / (name + ".png"), dpi=175, bbox_inches="tight")
        fig.savefig(folder / (name + ".svg"), bbox_inches="tight")
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), layout="constrained")
    names = {"cycle3_count": "Cycle", "reciprocal_24h": "Reciprocal 24h", "fanin_168h": "Fan-in 168h", "relay_168h": "Relay 168h", "fanin_24h": "Fan-in 24h"}
    offsets = {"cycle3_count": (9, 7), "reciprocal_24h": (9, -14), "fanin_168h": (-90, 10), "relay_168h": (-80, -19), "fanin_24h": (9, -13)}
    for ax, ds in zip(axes, SELECTED):
        motifs = ["cycle3_count", "reciprocal_24h", "fanin_168h", "relay_168h"] if ds == "ibm_aml" else ["fanin_24h", "fanin_168h"]
        for motif in motifs:
            r = e.motif(ds, motif)
            ax.scatter(100 * r["positive_coverage"], r["lift"], color="#087f79", s=65, zorder=3)
            ax.annotate(names[motif], (100 * r["positive_coverage"], r["lift"]), xytext=offsets[motif], textcoords="offset points", fontsize=9)
        ax.axhline(1, color="#b67830", linestyle="--", linewidth=1)
        ax.set(xlim=(-3, 90), ylim=(0.1, 400), yscale="log", title=LABEL[ds], xlabel="Positive coverage (%)", ylabel="Lift vs dataset prevalence (log scale)")
        ax.grid(axis="y", alpha=.15)
    finish(fig, "motif_coverage_lift")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout="constrained")
    for ax, ds in zip(axes, SELECTED):
        for family, label, color, style in [("transaction_only", "Transaction only", colors["transaction_only"], "-"),
                ("transaction_novelty", "+ Seen-account flags", colors["transaction_novelty"], "--"),
                (SELECTED[ds], "Validation-selected", colors["selected"], "-")]:
            rows = [e.budget(ds, family, f) for f in FRACTIONS]
            ax.plot([100*f for f in FRACTIONS], [r["TP_at_K"] for r in rows], marker="o", color=color, linestyle=style, label=label)
        ax.set(title=LABEL[ds], xlabel="Reviewed share of test (%)", ylabel="True positives in top K", xticks=[.1, .5, 1], ylim=(0, None))
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(axis="y", alpha=.16)
    finish(fig, "ranking_depth")
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.2), layout="constrained")
    for col, ds in enumerate(SELECTED):
        rows = [r for r in e.periods if r["dataset"] == ds]
        x = [r["period"] for r in rows]
        axes[0, col].bar(x, [100*r["prevalence"] for r in rows], color="#9bb1be", width=.6)
        axes[0, col].set(title=LABEL[ds] + " | label prevalence", ylabel="Positive transactions (%)", xticks=x)
        for key, label, color in [("baseline_recall", "Transaction only", colors["transaction_only"]), ("selected_recall", "Validation-selected", colors["selected"])]:
            axes[1, col].plot(x, [100*r[key] for r in rows], marker="o", color=color, label=label)
        axes[1, col].set(xlabel="Ordered test period (1–5)", ylabel="Recall (%)", xticks=x, ylim=(0, 65))
        axes[1, col].legend(fontsize=8)
        for ax in axes[:, col]:
            ax.grid(axis="y", alpha=.15)
    finish(fig, "temporal_prevalence_recall")
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.9), layout="constrained")
    for ax, ds in zip(axes, SELECTED):
        families = ["transaction_only", "transaction_novelty", SELECTED[ds]]
        rows = [next(r for r in e.marginal if r["dataset"] == ds and r["model"] == f and r["from_fraction"] == .005) for f in families]
        bars = ax.barh(["Transaction only", "+ Seen-account flags", "Validation-selected"], [100*r["marginal_positive_rate"] for r in rows], color=list(colors.values()))
        ax.bar_label(bars, labels=[f'{100*r["marginal_positive_rate"]:.2f}%' for r in rows], padding=5)
        ax.set(title=LABEL[ds] + " | 0.5% → 1%", xlabel="Positive rate among additional reviews (%)", xlim=(0, 10.5))
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=.15)
    finish(fig, "marginal_review_yield")


def scope_and_sources(d, technical=False):
    d.p("Nguồn là các lần chạy full ngày 24/10/2026 và bản kiểm tra aggregate ngày 26/10/2026. Lift, hiệu suất biên, tỷ trọng positive theo kỳ và phân tích hòa điểm được tính bổ sung từ exports; không phải một lần huấn luyện hay đánh giá predictions mới.")
    d.bullets([
        "Đơn vị đánh giá là giao dịch có nhãn: IBM laundering và PaySim fraud. Không cộng kết quả giữa hai dataset; TP không đồng nghĩa số vụ án, khách hàng hoặc đường dây.",
        "Mô hình và ngưỡng giữ nguyên theo mean F1 của 3-fold walk-forward validation. Chưa tối ưu riêng cho từng ngân sách kiểm tra; không chọn lại mô hình bằng kết quả test.",
        "Full graph chỉ mô tả cấu trúc. Feature C/L của mô hình lấy từ snapshot quá khứ, M dùng strict-past; hình full graph không phải bằng chứng mô hình biết trước tương lai.",
        "Không có dữ liệu thời gian điều tra, chi phí mỗi ca hoặc tổn thất được ngăn chặn. Cùng số giao dịch được xem chưa đồng nghĩa cùng thời gian hoặc chi phí.",
        "Các case cũ thiếu feature values để xác minh rule path (CP5 LIMITED). Nhánh cây minh họa là logic tổng quát từ model đã lưu, không phải lời giải thích đã xác nhận cho một case cụ thể.",
    ])
    d.p("Phương pháp: [tham số và protocol](sources/02_METHODS_AND_PARAMETERS.md). Phạm vi bằng chứng: [reliability](sources/06_RELIABILITY_AND_VALIDATION.md). Nghiệm thu aggregate gốc: [completion.json](" + ("completion.json" if technical else "sources/completion.json") + "). Kiểm tra revision hiện tại: [revision_validation.json](revision_validation.json).", small=True)
    d.p("Giữ cả hai thư mục `generated` và `business_report` cạnh nhau để dùng các liên kết qua lại offline. Các hình, bảng và tài liệu dẫn trực tiếp đều nằm trong bộ này.", small=True)


def common_budget_table(d, e):
    rows = []
    for ds in SELECTED:
        for f in FRACTIONS:
            bs = [e.budget(ds, family, f) for family in ("transaction_only", "transaction_novelty", SELECTED[ds])]
            rows.append([LABEL[ds], pct(f, 1), n(bs[0]["K"]), *(n(r["TP_at_K"]) for r in bs)])
    d.table(["Dataset", "Phần test được xem", "K giao dịch", "T tìm đúng", "T + novelty tìm đúng", "Mô hình chọn tìm đúng"], rows,
            "Cùng số lượt kiểm tra trong từng dataset; số đếm là TP@K")


def business_report(e, folder):
    d = Document("Từ cấu trúc giao dịch đến giá trị kiểm tra",
        "Tín hiệu nào tập trung positive, thông tin nào được mô hình khai thác, và lợi ích xuất hiện ở đâu trong danh sách cần xem xét?")
    cycle = e.motif("ibm_aml", "cycle3_count")
    ibm_base, ibm_sel = e.model("ibm_aml", "transaction_only"), e.model("ibm_aml")
    ps_base, ps_sel, ps_novel = (e.model("paysim", f) for f in ("transaction_only", SELECTED["paysim"], "transaction_novelty"))
    d.section("1. Ba phát hiện nối các phần của project", "findings")
    d.cards([
        ("IBM · tín hiệu hiếm", pct(cycle["positive_rate_when_present"]), f'Tỷ lệ laundering trong {n(cycle["covered_transactions"])} giao dịch có cycle trên test; chỉ phủ {pct(cycle["positive_coverage"])} laundering.'),
        ("PaySim · độ sâu danh sách", "+" + n(e.budget("paysim", SELECTED["paysim"], .005)["TP_at_K"] - e.budget("paysim", "transaction_only", .005)["TP_at_K"]), "Chênh lệch ròng số fraud tìm đúng khi cùng xem 6.244 giao dịch; kết quả so với đối chứng chỉ thuộc tính giao dịch."),
        ("Giá trị phụ thuộc cách dùng", "0,1% → 1%", "PaySim duy trì lợi ích khi mở rộng danh sách; IBM chuyển từ lợi thế nhỏ sang kém đối chứng ở mức 1% đã đánh giá."),
    ])
    d.p("Câu hỏi xuyên suốt là: **quan hệ và lịch sử bổ sung giá trị gì so với chỉ nhìn giao dịch riêng lẻ, và giá trị đó phụ thuộc vào dữ liệu và năng lực kiểm tra thế nào?**")
    d.p("Các task tạo thành một chuỗi bằng chứng: cấu trúc mạng → nhóm hành vi → thông tin cây sử dụng → kết quả ưu tiên kiểm tra. Mỗi bước trả lời một câu hỏi riêng; một pattern đáng chú ý chưa tự động trở thành một cảnh báo hiệu quả.")
    d.note("Phát hiện chính: thông tin graph có nhiều vai trò. Một số motif xác định nhóm nhỏ tập trung positive; lịch sử giúp phân biệt giao dịch; centrality/community cung cấp bối cảnh. Bằng chứng hiện tại chưa cho thấy cần kết hợp đủ ba nhóm để luôn đạt kết quả tốt hơn.")

    d.section("2. Hai môi trường giao dịch cung cấp ngữ cảnh khác nhau", "context")
    rows = []
    for ds in SELECTED:
        r = next(x for x in e.structure if x["dataset"] == ds)
        ov = next(x for x in e.overview if x["dataset"] == ds)
        rows.append([LABEL[ds], n(ov["transactions"]), n(r["accounts"]), pct(r["degree_one_fraction"]), dec(r["mean_degree"])])
    d.table(["Dataset", "Giao dịch full", "Tài khoản full", "Tài khoản degree = 1", "Degree trung bình"], rows, "Đặc điểm full graph dùng để đặt bối cảnh")
    d.p("PaySim có phần lớn tài khoản chỉ gắn với một giao dịch trong full graph. IBM ghi nhận nhiều giao dịch trên mỗi tài khoản hơn theo degree trung bình; chỉ số này chưa xác định số đối tác duy nhất hay mức lặp lại giữa cùng một cặp tài khoản. Đây là cơ sở đặt giả thuyết rằng lượng ngữ cảnh quan hệ có thể khai thác khác nhau giữa hai dataset; chưa chứng minh cấu trúc này gây ra chênh lệch hiệu năng.")
    d.p("Các chỉ số full graph không mô tả trực tiếp lượng lịch sử có sẵn tại một thời điểm quyết định. Vì vậy, câu chuyện cấu trúc phải được đối chiếu tiếp với feature và kết quả predictive theo thời gian.")
    d.p("Nguồn: [đặc điểm cấu trúc](insights/structure_summary.csv), [dataset overview](sources/tables/dataset_overview.csv).", small=True)

    d.section("3. Tín hiệu phổ biến và tín hiệu tập trung positive có giá trị khác nhau", "signals")
    d.p("Coverage trả lời tín hiệu có mặt ở bao nhiêu positive. Tỷ lệ positive trong nhóm và lift trả lời nhóm đó tập trung positive đến mức nào. Cần đọc cùng số giao dịch có tín hiệu; coverage cao có thể đến từ việc tín hiệu phổ biến trong cả dữ liệu bình thường.")
    rows = []
    for ds, motif, label in [("ibm_aml", "cycle3_count", "IBM · cycle"), ("ibm_aml", "reciprocal_24h", "IBM · qua lại 24h"),
                              ("ibm_aml", "fanin_168h", "IBM · fan-in 168h"), ("paysim", "fanin_168h", "PaySim · fan-in 168h")]:
        r = e.motif(ds, motif)
        rows.append([label, n(r["covered_transactions"]), n(r["covered_positives"]), pct(r["positive_rate_when_present"], 3), pct(r["positive_coverage"]), dec(r["lift"]) + "×"])
    d.table(["Nhóm trên test", "Giao dịch", "Positive", "Positive trong nhóm", "Bao phủ positive", "Lift / nền"], rows, "Mức tập trung nhãn positive khi tín hiệu hiện diện; không phải kết quả classifier")
    d.figure("motif_coverage_lift", "Đối chiếu coverage và lift của các nhóm motif trên test",
             "Trục dọc là lift theo thang log; đường ngang 1× là tỷ lệ positive nền của từng dataset. IBM có nhóm hiếm tập trung laundering cao, trong khi fan-in PaySim nằm dưới nền. Các điểm chỉ là cohort quan sát; nhóm rỗng hoặc có lift bằng 0 không được vẽ trên trục log.")
    d.bullets([
        "**IBM: cycle và giao dịch qua lại là nhóm nhỏ tập trung laundering.** Có thể đặt giả thuyết kiểm tra chuyên biệt cho các nhóm này, nhưng coverage thấp giới hạn giá trị phát hiện diện rộng.",
        "**IBM: fan-in 168h bao phủ rộng nhưng mức tập trung positive chỉ nhỉnh hơn nền.** Tín hiệu xuất hiện ở " + pct(e.motif("ibm_aml", "fanin_168h")["population_share"]) + " toàn bộ giao dịch test; riêng sự hiện diện chưa đủ để ưu tiên một khối lượng lớn giao dịch.",
        "**PaySim: có fan-in chưa đồng nghĩa fraud cao hơn.** Tỷ lệ fraud khi fan-in 168h hiện diện thấp hơn nền. Cycle không xuất hiện; relay 168h chỉ phủ 21 giao dịch test và không có fraud trong nhóm quan sát đó.",
    ])
    d.note("Hàm ý: phân biệt tín hiệu phục vụ rà soát nhóm nhỏ với thông tin phục vụ xếp hạng diện rộng. Những nhóm nhỏ có lift cao cần kiểm chứng ở thời gian khác trước khi đề xuất quy tắc cảnh báo. Các cohort chồng lấp, không cộng positive giữa các motif.", caution=True)
    d.p("Nền test: IBM " + pct(e.model("ibm_aml")["test_positives"] / e.model("ibm_aml")["test_transactions"], 3) + "; PaySim " + pct(e.model("paysim")["test_positives"] / e.model("paysim")["test_transactions"], 3) + ". [Bảng cohort, công thức và nguồn](insights/motif_cohort_insights.csv).", small=True)

    d.section("4. PaySim: thiếu lịch sử cũng mang thông tin", "history")
    d.p("Cây PaySim được chọn sử dụng loại giao dịch, số tiền chuẩn hóa và lịch sử nhận tiền trong 168 giờ. Các nhánh cây cho thấy giá trị không chỉ đến từ việc phát hiện một pattern dòng tiền đã hiện diện.")
    d.table(["Điều kiện được giữ giống nhau", "Lịch sử nhận tiền", "Score của leaf"], [
        ["CASH_OUT; cùng nhánh số tiền chuẩn hóa", "Không có lượt nhận tiền hợp lệ được ghi nhận trong 168h trước", dec(e.leaf14["risk_score"], 4)],
        ["CASH_OUT; cùng nhánh số tiền chuẩn hóa", "Có lịch sử nhận tiền hợp lệ trong 168h trước", dec(e.leaf15["risk_score"], 4)],
    ], "Hai leaf của cây đã lưu chỉ khác điều kiện lịch sử nhận tiền")
    d.p("**Trong nhóm điều kiện này, sự vắng mặt của lịch sử nhận tiền là thông tin phân biệt mà cây sử dụng.** Điều đó nối kết quả task history với hiệu quả mô hình dù cycle/relay gần như không cung cấp coverage fraud trên PaySim.")
    d.note("Đây là logic tổng quát của mô hình đã fit. Chưa có lịch sử trong 168 giờ không chứng minh tài khoản vừa mở; score của weighted tree không phải xác suất fraud đã hiệu chỉnh. Nhánh minh họa chưa xác minh đường đi của bất kỳ case cụ thể nào.", caution=True)
    d.p("IBM dùng feature thuộc cả C/M/L. Trên PaySim, L có trong cấu hình nhưng không được cây được chọn dùng để chia nhánh; C không nằm trong cấu hình được chọn. Vì vậy, kết quả PaySim hỗ trợ giá trị của bối cảnh lịch sử, chưa chứng minh mô hình phát hiện đường dây hoặc cần đủ ba nhóm graph.")
    d.p("Nguồn: [leaf rules PaySim](sources/datasets/paysim/model_details/without_centrality/leaf_rules.csv), [vocabulary loại giao dịch](sources/datasets/paysim/model_details/without_centrality/saved_model_parameters.json), [feature usage](sources/feature_usage.csv).", small=True)

    d.section("5. Giá trị nằm ở đâu trong danh sách cần kiểm tra?", "review")
    d.p("Đối chứng T chỉ dùng thuộc tính giao dịch. T + novelty bổ sung cờ tài khoản đã xuất hiện trong lịch sử prefix; đây là đối chứng đơn giản cần giữ để đánh giá giá trị vượt quá thông tin đã thấy tài khoản. Mô hình chọn là full_fusion ở IBM và without_centrality ở PaySim.")
    common_budget_table(d, e)
    d.figure("ranking_depth", "TP ở ba mức ngân sách cho baseline, novelty và mô hình được chọn",
             "Mỗi điểm là một mức đã xuất; đoạn nối chỉ hỗ trợ đọc xu hướng, không xác định điểm giao hay ngân sách tối ưu ở giữa. PaySim: novelty cạnh tranh ở đầu danh sách, mô hình dùng lịch sử nổi bật khi mở rộng. IBM: lợi thế nhỏ chuyển thành bất lợi tại mức 1%.")
    d.p("**PaySim: giá trị nổi bật là độ sâu hữu ích của danh sách.** Ở 0,1%, novelty tìm đúng 913 fraud so với 900 của mô hình được chọn. Khi mở rộng tới 0,5% và 1%, mô hình được chọn lần lượt tìm đúng 1.523 và 2.044, cao hơn novelty 401 và 910. Đây là chênh lệch ròng, chưa xác định danh tính các fraud được thêm vào hoặc bị mất đi giữa hai danh sách.")
    rows = []
    for ds in SELECTED:
        a, b = (next(r for r in e.marginal if r["dataset"] == ds and r["model"] == family and r["from_fraction"] == .005)
                for family in ("transaction_only", SELECTED[ds]))
        rows.append([LABEL[ds], n(a["added_reviews"]), n(a["added_TP"]), pct(a["marginal_positive_rate"]), n(b["added_TP"]), pct(b["marginal_positive_rate"])])
    d.table(["Dataset", "Lượt xem thêm", "T: positive thêm", "T: hiệu suất biên", "Mô hình: positive thêm", "Mô hình: hiệu suất biên"], rows,
            "Mở rộng cùng danh sách từ 0,5% lên 1%; hiệu suất biên = positive thêm / lượt xem thêm")
    d.p("**IBM: hiệu quả phụ thuộc độ sâu kiểm tra.** Mô hình tìm hơn T 17 laundering ở 0,5%, nhưng phần danh sách mở rộng tiếp theo tìm ít hơn T 105 laundering; tổng chênh lệch tại 1% thành −88. Kết quả chưa ủng hộ ưu thế nhất quán khi thay T bằng mô hình được chọn.")
    rates = []
    for ds in SELECTED:
        a, b = (e.budget(ds, family, .005) for family in ("transaction_only", SELECTED[ds]))
        rates.append([LABEL[ds], n(a["K"]), pct(a["precision_at_K"]) + " → " + pct(b["precision_at_K"]), pct(a["recall_at_K"]) + " → " + pct(b["recall_at_K"])])
    d.table(["Dataset", "K ở 0,5%", "Tỷ lệ tìm đúng trong danh sách: T → mô hình", "Bao phủ positive: T → mô hình"], rates, "Đọc số tìm thêm cùng mẫu số và phần positive còn bỏ sót")
    d.h3("Một đánh đổi khác: dùng ngưỡng cảnh báo đã cố định")
    d.p(f'IBM: cảnh báo {n(ibm_base["alerts"])} → {n(ibm_sel["alerts"])}; tìm đúng {n(ibm_base["TP"])} → {n(ibm_sel["TP"])}; cảnh báo nhầm {n(ibm_base["FP"])} → {n(ibm_sel["FP"])}. Danh sách ngắn hơn đi cùng mức phát hiện thấp hơn.')
    d.p(f'PaySim: so với T, mô hình tìm đúng {n(ps_base["TP"])} → {n(ps_sel["TP"])} nhưng cảnh báo nhầm {n(ps_base["FP"])} → {n(ps_sel["FP"])}. Đối chứng novelty cũng tìm đúng {n(ps_novel["TP"])} với {n(ps_novel["FP"])} cảnh báo nhầm, ít hơn mô hình được chọn {n(ps_sel["FP"] - ps_novel["FP"])}. Mô hình được chọn không dẫn đầu ở mọi mục tiêu test.')
    d.note("Các số tại ngưỡng cố định và các số top-K trả lời hai câu hỏi khác nhau. Chưa có kiểm định paired cho chênh lệch mô hình. Nhiều giao dịch có cùng score nên TP@K còn phụ thuộc thứ tự hòa điểm; bản kỹ thuật trình bày độ nhạy này.", caution=True)
    d.p("Nguồn: [54 dòng ngân sách](sources/review_budget_comparison.csv), [hiệu suất biên](insights/marginal_review_yield.csv), [18 cấu hình và confusion](sources/model_comparison.csv).", small=True)

    d.section("6. Kết quả theo thời gian và hàm ý sử dụng", "implications")
    ibm_last = next(r for r in e.periods if r["dataset"] == "ibm_aml" and r["period"] == 5)
    ps_last = sum(r["share_of_test_positives"] for r in e.periods if r["dataset"] == "paysim" and r["period"] >= 4)
    d.p(f'Phân bố positive thay đổi mạnh giữa các kỳ: kỳ cuối chứa {pct(ibm_last["share_of_test_positives"])} laundering test IBM; hai kỳ cuối chứa {pct(ps_last)} fraud test PaySim. Đếm số kỳ thắng như những kỳ có sức nặng bằng nhau sẽ bỏ qua cấu trúc này.')
    d.figure("temporal_prevalence_recall", "Prevalence và recall theo năm kỳ test có thứ tự thời gian",
             "Hai hàng cùng thứ tự kỳ: tỷ lệ positive ở trên, recall ở dưới. IBM có recall mô hình thấp hơn T ở cả 5 kỳ; PaySim có recall cao hơn T ở cả 5 kỳ. Đây là kết quả tại ngưỡng đã cố định, không phải top-K theo từng kỳ.")
    d.p("IBM có F1 cao hơn T ở 3/5 kỳ, nhưng recall thấp hơn ở cả 5/5 kỳ: một kết quả F1 cao hơn chưa đồng nghĩa tìm được nhiều laundering hơn. PaySim cải thiện recall ở cả năm kỳ quan sát; hướng cải thiện này chưa xác nhận khả năng khái quát ngoài dữ liệu mô phỏng.")
    d.table(["Bằng chứng", "Hàm ý hiện tại", "Câu hỏi kiểm chứng tiếp theo"], [
        ["IBM: cycle/reciprocal tập trung laundering trong nhóm nhỏ", "Giữ như giả thuyết rà soát nhóm hành vi chuyên biệt", "Mức tập trung có lặp lại ở giai đoạn khác? Các nhóm này bổ sung positive nào cho danh sách hiện tại?"],
        ["PaySim: lịch sử tạo giá trị ở danh sách sâu hơn", "Đánh giá mô hình theo năng lực kiểm tra dự kiến", "Nếu chọn theo ngân sách trên validation, lợi thế còn giữ ở giai đoạn mới?"],
        ["IBM: không có ưu thế nhất quán theo ngân sách/recall", "Giữ đối chứng và nêu rõ đánh đổi", "Có nhóm hành vi nào hưởng lợi và nhóm nào bị giảm phát hiện?"],
        ["C/L có giá trị mô tả; lợi ích predictive khác nhau", "Nối các task bằng vai trò bằng chứng", "Thông tin nào giúp người kiểm tra hiểu giao dịch hơn, dù không tăng metric tổng hợp?"],
    ], "Phân biệt phát hiện hiện có với giả thuyết và bước đánh giá tiếp theo")
    d.p("Các câu hỏi về positive mới/mất đi, tác động theo nhóm tài khoản và giải thích case cần predictions/feature ở từng giao dịch. Báo cáo này không suy các kết quả đó từ vài examples. Hướng dùng được nêu là đề xuất đánh giá tiếp, chưa phải quyết định triển khai ngân hàng.")
    d.p("Chi tiết bằng chứng và giới hạn: [bản kỹ thuật](../generated/CONNECTED_RESULTS_REPORT.html). Số liệu thời gian: [temporal insights](insights/temporal_insights.csv).", small=True)
    d.section("Nguồn số liệu và cách đọc", "sources")
    scope_and_sources(d)
    d.save(folder, "GRAPHGUARD_BUSINESS_REPORT")


def technical_report(e, folder):
    d = Document("GraphGuard: bằng chứng cho giá trị của ngữ cảnh giao dịch",
        "Phụ lục phân tích cho báo cáo tổng hợp: cấu trúc → mức tập trung positive → logic mô hình → hiệu quả theo ngân sách và thời gian.", technical=True)
    d.section("1. Câu hỏi phân tích và mức bằng chứng", "question")
    d.p("Câu hỏi: quan hệ và lịch sử bổ sung giá trị gì so với thuộc tính của giao dịch riêng lẻ, và giá trị đó thay đổi theo dataset, ngân sách và thời gian thế nào? Phần pipeline/kỹ thuật đã được trình bày riêng; nội dung này nối các kết quả thành lập luận phân tích.")
    d.table(["Lớp evidence", "Câu hỏi", "Không suy trực tiếp thành"], [
        ["Full descriptive graph", "Mạng lưới và lịch sử quan hệ có đặc điểm gì?", "Giá trị feature biết tại thời điểm dự đoán hoặc nguyên nhân hiệu năng"],
        ["Cohort motif trên test", "Tín hiệu hiện diện ở nhóm nào; mức tập trung positive ra sao?", "Recall classifier, đóng góp độc lập hoặc quy tắc cảnh báo đã được xác nhận"],
        ["Saved tree / allowlist", "Feature nào được cung cấp, feature nào thực sự dùng và theo chiều nào?", "Đóng góp nhân quả hoặc lời giải thích đã xác minh cho từng case"],
        ["Ablation / top-K / temporal", "Khác biệt hiệu quả quan sát được ở mục tiêu nào?", "Hiệu quả ngân hàng thực tế, tiết kiệm chi phí hoặc phát hiện đường dây"],
    ], "Chuỗi bằng chứng dùng để kết nối các task")
    d.note("Phân tích khám phá trên holdout nội bộ đã được xem trong phát triển. Winner/ngưỡng giữ nguyên theo mean validation F1; không chọn lại mô hình hoặc ngân sách tối ưu từ bảng test. CP0–CP4 và CP6–CP7 của kiểm tra aggregate gốc PASS; CP5 LIMITED vì thiếu feature cho rule-path verification. Revision tài liệu có kiểm tra riêng.")
    d.p("Bản trình bày nghiệp vụ: [Từ cấu trúc giao dịch đến giá trị kiểm tra](../business_report/GRAPHGUARD_BUSINESS_REPORT.html).", small=True)

    d.section("2. Cấu trúc và tín hiệu: coverage cần đọc cùng lift", "cohorts")
    rows = []
    for ds in SELECTED:
        ov = next(r for r in e.overview if r["dataset"] == ds)
        st = next(r for r in e.structure if r["dataset"] == ds)
        rows.append([LABEL[ds], n(ov["transactions"]), n(ov["accounts"]), pct(st["degree_one_fraction"]), dec(st["mean_degree"]), n(ov["communities"]), n(ov["internal_edges"]), n(ov["cross_edges"])])
    d.table(["Dataset", "Full edges", "Full accounts", "Degree 1", "Mean degree", "LPA groups", "Internal edges", "Cross edges"], rows, "Full graph: các chỉ số mô tả có cùng scope")
    d.p("Degree tính theo physical transactions, gồm giao dịch lặp thật; đây không phải số đối tác duy nhất. PaySim có 94,83% tài khoản degree=1, IBM 3,37%. LPA là kết quả 5 vòng đã thực chạy: internal edges=0 ở PaySim không chứng minh graph bipartite hoặc mọi giao dịch cross-community đáng ngờ. LPA groups không phải connected components hay ground-truth fraud rings.")
    d.p("Định nghĩa cohort: S là tín hiệu hiện diện theo định nghĩa feature đã xuất. Population share = N(S)/N; positive coverage = P(S)/P; positive rate = P(S)/N(S); lift = positive rate / (P/N). Nếu N(S)=0, rate và lift không xác định, được để trống thay vì gán 0.")
    rows = []
    for r in e.cohorts:
        if r["motif"] not in {"cycle3_count", "reciprocal_24h", "reciprocal_168h", "fanin_24h", "fanin_168h", "relay_168h"}:
            continue
        rows.append([LABEL[r["dataset"]], r["motif"], n(r["covered_transactions"]), n(r["covered_positives"]), pct(r["population_share"]), pct(r["positive_coverage"]), pct(r["positive_rate_when_present"], 3), "—" if r["lift"] is None else dec(r["lift"]) + "×"])
    d.table(["Dataset", "Tín hiệu test", "N(S)", "P(S)", "Population share", "Positive coverage", "Positive rate", "Lift"], rows, "Cohort tín hiệu khi hiện diện; các tập chồng lấp")
    d.figure("motif_coverage_lift", "Coverage và lift trên test ở các cohort motif",
             "Trục log chỉ vẽ cohort có lift > 0; đường 1× là nền riêng từng dataset. Vị trí là thống kê cohort khi hiện diện, không thể hiện độ lớn liên tục hoặc tương tác của feature trong classifier.")
    d.bullets([
        "IBM cycle: 41/132 positive, lift khoảng 175,7× nhưng chỉ bao phủ 2,28% laundering. Reciprocal 24h cũng tập trung positive trên nhóm nhỏ. Đặt giả thuyết rà soát hẹp là hợp lý; chưa xác nhận quy tắc độc lập hoặc ổn định ngoài giai đoạn này.",
        "IBM fan-in 168h: population share 69,39%, positive coverage 77,54%, lift khoảng 1,12×. Coverage cao không đồng nghĩa khả năng phân biệt mạnh khi chỉ xét presence. Giá trị liên tục/conditional của feature có thể khác thống kê presence.",
        "PaySim fan-in 168h: lift khoảng 0,44×; fan-in 24h khoảng 0,19×. Pattern presence không phải bằng chứng nhóm có nguy cơ cao hơn nền. Cycle rỗng; relay 168h có 21 giao dịch test và 0 fraud, chưa đủ để kết luận không tồn tại fraud theo hành vi relay ở môi trường khác.",
        "Các nhóm overlap; không cộng P(S), không suy intersection, không gắn các tỷ lệ này vào TP/FN của mô hình. Nhãn và cơ chế mô phỏng khác nhau nên lift chỉ được chuẩn hóa và diễn giải trong từng dataset.",
    ])
    d.p("Full-scope motif và baseline audit vẫn giữ riêng trong sources. Ví dụ PaySim baseline relay_pairs=30 là số cặp theo phép đếm baseline; relay_168h covered_transactions=94 full/21 test là coverage giao dịch theo feature theo thời gian. Không so chúng như cùng đơn vị hoặc cùng điều kiện. [Cohort mới](insights/motif_cohort_insights.csv), [IBM motif gốc](sources/datasets/ibm_aml/tables/motif_coverage.csv), [PaySim motif gốc](sources/datasets/paysim/tables/motif_coverage.csv), [baseline PaySim](sources/datasets/paysim/tables/baseline_summary.csv).", small=True)

    d.section("3. Feature sử dụng: sự vắng mặt lịch sử là một phần của tín hiệu", "features")
    rows = [[LABEL[r["dataset"]], r["family"], r["group"], r["feature"], pct(r["importance"])]
            for r in e.usage if r["selected_on_validation"] and r["used_in_split"]]
    d.table(["Dataset", "Frozen family", "Nhóm", "Feature dùng trong split", "Impurity importance"], rows, "Mức dùng feature trong cây fit trên training prefix")
    d.p("Impurity importance mô tả cây đã fit; không phải phần trăm cải thiện hiệu quả. Feature không xuất hiện trong split có thể dư thừa với feature khác. Feature có trong split chưa chứng minh bỏ nó sẽ giảm mọi metric.")
    d.h3("Một đối chiếu điều kiện có thể xác minh từ saved tree")
    d.table(["Leaf", "Điều kiện chính xác", "Score", "Alert ở θ=0,7", "Training rows"], [
        [n(r["leaf_id"]), "`" + r["condition"] + "`", dec(r["risk_score"], 6), "Có" if r["alert_at_frozen_threshold"] else "Không", n(r["training_raw_count"])]
        for r in (e.leaf14, e.leaf15)], "PaySim leaves 14 và 15: chỉ thay đổi điều kiện receiver_in_168h")
    d.p("Vocabulary đã lưu là CASH_IN=0, CASH_OUT=1, DEBIT=2, PAYMENT=3, TRANSFER=4. Kết hợp hai điều kiện type trong bảng cho CASH_OUT. Trong nhánh scaled_amount > 1,1517823481, cây chia receiver_in_168h ở 0,5: không có lượt nhận tiền hợp lệ trong cửa sổ trước đó được chấm score cao hơn nhánh có lịch sử.")
    d.p("Đây là sự tương tác giữa lịch sử, loại giao dịch và nhóm amount; không khái quát mọi tài khoản thiếu lịch sử đều fraud. Cửa sổ 168h không phải tuổi tài khoản. Score weighted tree không được diễn giải như xác suất đã calibrate; scaled_amount không phải ngưỡng tiền chung cho các currency.")
    d.p("IBM selected tree sử dụng C/M/L nhưng không dùng cycle trong split. Điều đó không chứng minh các giao dịch có cycle đều bị bỏ sót: chúng có thể được phân loại qua feature khác. PaySim selected không có C trong allowlist; L có trong allowlist nhưng không xuất hiện trong split. Cần giữ phân biệt cấu hình được cung cấp với thông tin thực sự sử dụng.")
    d.p("Nguồn: [allowlists](sources/tables/exact_feature_allowlists.csv), [feature usage](feature_usage.csv), [leaf rules](sources/datasets/paysim/model_details/without_centrality/leaf_rules.csv), [saved parameters và vocabulary](sources/datasets/paysim/model_details/without_centrality/saved_model_parameters.json).", small=True)

    d.section("4. Giá trị theo mục tiêu: top-K, ngưỡng và đối chứng novelty", "budgets")
    d.p("T = thuộc tính giao dịch; novelty = cờ endpoint đã có trong prefix; C = centrality và seen flags; M = motif/history; L = community context. Novelty được giữ làm đối chứng để đánh giá phần giá trị vượt quá việc đã thấy tài khoản.")
    common_budget_table(d, e)
    d.figure("ranking_depth", "TP@K theo ba ngân sách đã xuất",
             "Đường nối ba điểm không xác định ngân sách tối ưu hoặc điểm giao chính xác. K=ceil(f×Ntest); chỉ so cùng K trong cùng dataset. Không tái dựng top-K từ examples.")
    d.p("PaySim selected so với novelty có ΔTP = −13, +401, +910 tại 0,1%, 0,5%, 1%. Quan sát hỗ trợ giả thuyết lịch sử tăng độ sâu hữu ích của ranking hơn là luôn cải thiện phần đầu danh sách. IBM selected so với T có ΔTP = +13, +17, −88: chưa có ưu thế nhất quán theo ngân sách.")
    d.table(["Dataset", "Model", "Khoảng mở rộng", "Lượt xem thêm", "Positive thêm", "Hiệu suất biên"], [
        [LABEL[r["dataset"]], r["model"], pct(r["from_fraction"], 1) + " → " + pct(r["to_fraction"], 1), n(r["added_reviews"]), n(r["added_TP"]), pct(r["marginal_positive_rate"])]
        for r in e.marginal], "Hiệu suất biên trên cùng ranking: ΔTP/ΔK")
    d.figure("marginal_review_yield", "Tỷ lệ positive trong phần danh sách thêm khi tăng từ 0,5% lên 1%",
             "Hiệu suất biên khác với precision tích lũy. Đây là mở rộng từng ranking riêng, chưa phải đánh giá một chính sách chuyển mô hình hoặc hợp nhất các danh sách.")
    d.h3("Operating point được cố định trước test")
    d.table(["Dataset", "Family", "θ", "TP", "FP", "FN", "Precision", "Recall", "F1", "AP"], [
        [LABEL[ds], family, dec(r["threshold"], 1), n(r["TP"]), n(r["FP"]), n(r["FN"]), pct(r["precision"]), pct(r["recall"]), pct(r["F1"]), pct(r["average_precision"])]
        for ds in SELECTED for family in ("transaction_only", "transaction_novelty", SELECTED[ds]) for r in [e.model(ds, family)]],
        "Đối chứng chính; θ chọn theo mean validation F1, AP đo ranking ở các score bins")
    d.p("Trên test PaySim, novelty đạt cùng TP/recall với selected nhưng ít FP hơn 171 tại θ=0,7; F1 cũng cao hơn. Selected có AP cao hơn novelty và lợi thế ở các K lớn hơn. Đây là khác biệt theo mục tiêu; không đổi winner đã freeze. Trên IBM, precision/AP tăng nhẹ đi cùng giảm recall/F1 ở ngưỡng cố định. Chỉ giảm số cảnh báo chưa đủ để kết luận hệ thống hiệu quả hơn.")
    d.p("Nguyên tắc báo cáo: AP/PR cho ranking, P/R/F1/confusion cho operating point, TP@K cho năng lực kiểm tra. Chi phí/giờ điều tra, số khách hàng và mức tổn thất chưa được đo. [18 models](model_comparison.csv), [54 budgets](review_budget_comparison.csv), [hiệu suất biên](insights/marginal_review_yield.csv).", small=True)

    d.section("5. Hòa điểm và thời gian giới hạn độ mạnh của kết luận", "reliability")
    d.h3("Nhiều giao dịch có cùng score")
    d.p("Thứ tự top-K gốc giữ risk DESC, event_key ASC, event_id ASC. Baseline PaySim chỉ có 3 mức score; một bin có 7.727 giao dịch cùng score. Khi K cắt trong bin, thứ tự phụ ảnh hưởng TP@K. Phân tích dưới đây chỉ thay thứ tự trong bin biên theo giả thiết chọn đều, không thay các score bins hay mô hình.")
    tie_rows = [r for r in e.ties if r["review_fraction"] == .005]
    d.table(["Dataset", "Model", "Mức score", "K", "Bin biên N", "Lấy từ bin", "TP gốc", "E[TP] hòa điểm ngẫu nhiên", "SD phân bổ"], [
        [LABEL[r["dataset"]], r["model"], n(r["distinct_scores"]), n(r["K"]), n(r["boundary_rows"]), n(r["taken_from_boundary"]), n(r["observed_TP"]), dec(r["expected_TP_random_boundary"]), dec(r["random_boundary_TP_sd"])]
        for r in tie_rows], "Độ nhạy phân bổ trong bin biên ở ngân sách 0,5%")
    d.p("Với B positive trong n giao dịch ở bin biên và lấy m giao dịch, E[TP]=positive phía trên + mB/n. Var=m(B/n)(1−B/n)(n−m)/(n−1). SD chỉ mô tả độ nhạy do phân bổ trong bin dưới giả thiết này; không phải CI cho chất lượng mô hình, không phải kiểm định chênh lệch paired, và không điều chỉnh phụ thuộc account/time.")
    d.p("[Bảng độ nhạy đủ ba mức K](insights/tie_sensitivity.csv). Những TP gốc trong báo cáo vẫn giữ nguyên thứ tự đã thực thi. Kỳ vọng ngẫu nhiên là phép tính bổ sung từ score-bin aggregates, không phải scoring mới.", small=True)
    d.h3("Thay đổi tỷ lệ positive theo thời gian")
    d.figure("temporal_prevalence_recall", "Tỷ lệ positive và recall theo thứ tự năm kỳ test",
             "Các kỳ đánh số 1–5 theo thứ tự xuất; không coi chúng là năm khoảng có thời lượng bằng nhau. Mỗi kỳ có population và số positive thực riêng. Recall là ở ngưỡng cố định, chưa phải cùng ngân sách trong từng kỳ.")
    d.table(["Dataset", "Kỳ", "Giao dịch", "Positive", "Tỷ trọng positive test", "Prevalence", "Recall T", "Recall chọn", "F1 T", "F1 chọn"], [
        [LABEL[r["dataset"]], n(r["period"]), n(r["transactions"]), n(r["positives"]), pct(r["share_of_test_positives"]), pct(r["prevalence"], 3), pct(r["baseline_recall"]), pct(r["selected_recall"]), pct(r["baseline_F1"]), pct(r["selected_F1"])]
        for r in e.periods], "Không đếm số kỳ thắng như những kỳ có lượng positive tương đương")
    d.p("IBM: kỳ 5 chứa 60,92% positive test. Selected F1 cao hơn T ở 3/5 kỳ nhưng recall thấp hơn ở cả 5/5. PaySim: kỳ 4–5 chứa 86,87% positive test; selected recall cao hơn ở 5/5 kỳ, F1 cao hơn ở 4/5. Positive rate thay đổi chưa xác định nguyên nhân drift hoặc chứng nhận ổn định tương lai.")
    d.p("Không lấy trung bình F1 theo kỳ làm full-test F1; full-test counts được cộng và kiểm tra riêng. CI Wilson P/R trong exports gốc là binomial theo giao dịch, chưa điều chỉnh phụ thuộc account/time. Không suy CI cho delta từ hai CI biên. Phân tích paired hoặc resampling theo khối cần predictions và định nghĩa phụ thuộc phù hợp.")

    d.section("6. Hàm ý phân tích và câu hỏi tiếp theo", "decisions")
    d.table(["Phát hiện", "Diễn giải được bảo vệ", "Kiểm chứng tiếp / dữ liệu cần"], [
        ["IBM rare motifs có positive concentration cao", "Có nhóm hành vi hẹp đáng phân tích bổ sung; coverage hạn chế", "Cohort theo thời gian khác; incremental positive so với ranking hiện tại; cần dữ liệu giao dịch"],
        ["PaySim history cải thiện ranking ở K lớn", "Giá trị nằm ở phần danh sách sâu hơn so với các đối chứng hiện có", "Chọn tiêu chí ngân sách bằng validation rồi đánh giá trên thời gian mới"],
        ["Novelty cạnh tranh tốt ở đầu ranking/ngưỡng cố định", "Giữ đối chứng đơn giản để tránh gán mọi lợi ích cho graph phức tạp", "So sánh theo cùng mục tiêu và cùng tập đánh giá; không đổi winner bằng test"],
        ["Community/centrality có giá trị dùng khác nhau", "Các task đóng góp những lớp bằng chứng khác nhau", "Đánh giá thông tin hỗ trợ người kiểm tra nếu có thiết kế và nhãn nghiệp vụ phù hợp"],
    ], "Đề xuất đánh giá tiếp; chưa phải chính sách triển khai")
    d.p("Các phép đếm hiện có không xác định phần giao nhau của danh sách mô hình, số positive mới duy nhất, positive bị mất đi, số khách hàng được phát hiện hay số đường dây. Muốn đánh giá bổ sung thật sự cần joined row-level predictions và một đơn vị case/account được định nghĩa rõ. Không suy các đại lượng này từ six examples.")

    d.section("Phụ lục: đối chứng đầy đủ và khả năng truy xuất", "appendix")
    def all_models():
        for ds in SELECTED:
            d.table(["Family", "Chọn từ validation", "θ", "TP", "FP", "FN", "Alerts", "Precision", "Recall", "F1", "AP"], [
                [r["family"], "Có" if r["selected_on_validation"] else "Không", dec(r["threshold"], 1), n(r["TP"]), n(r["FP"]), n(r["FN"]), n(r["alerts"]), pct(r["precision"]), pct(r["recall"]), pct(r["F1"]), pct(r["average_precision"])]
                for r in e.models if r["dataset"] == ds], LABEL[ds] + ": toàn bộ 9 cấu hình trên full test tương ứng")
    d.details("A. Toàn bộ 18 cấu hình", all_models)
    def all_deltas():
        rows = read_csv(e.root / "ablation_deltas.csv")
        for ds in SELECTED:
            d.table(["Contrast", "Enhanced / reference", "θ enhanced / reference", "ΔP pp", "ΔR pp", "ΔF1 pp", "ΔAP pp", "ΔTP", "ΔFP"], [
                [r["contrast"], r["enhanced"] + " / " + r["reference"], dec(r["enhanced_threshold"], 1) + " / " + dec(r["reference_threshold"], 1),
                 *(dec(r[k], 3) for k in ("delta_precision_pp", "delta_recall_pp", "delta_F1_pp", "delta_average_precision_pp")), n(r["delta_TP"]), n(r["delta_FP"])]
                for r in rows if r["dataset"] == ds], LABEL[ds] + ": chênh lệch giữa các cấu hình đã fit")
        d.p("pp là điểm phần trăm. Threshold có thể khác; refit tree thay đổi cấu trúc và tương tác. Không diễn giải delta như đóng góp nhân quả độc lập của nhóm feature. [CSV đầy đủ](ablation_deltas.csv).")
    d.details("B. Ablation giữa các cấu hình đã fit", all_deltas)
    d.h3("C. Examples và nguồn gốc")
    d.p("[Case examples](case_examples.csv) giữ nguyên 6 TP/FP/FN từ selected-model JSON. Tất cả rule_path_verified=false; score khớp leaf không xác nhận các condition của từng giao dịch. Không dùng examples để dựng top-K hoặc kết luận giao nhau C∩M∩L.")
    d.p("[Original run identity](run_identity.csv), [kiểm tra aggregate gốc](checkpoint_status.csv), [validation findings gốc](validation_findings.csv), [inventory gốc](source_inventory.csv), [input hashes gốc](input_hashes.json). Các tệp gốc này không được gắn lại hash của script revision.")
    d.p("Phần nguồn bổ sung để sửa liên kết sâu được sao chép nguyên byte từ bundle gốc. Manifest revision ghi riêng các source đã bổ sung và hash hiện tại. Source snapshots lịch sử không bị chỉnh nội dung.")
    scope_and_sources(d, technical=True)
    d.save(folder, "CONNECTED_RESULTS_REPORT")


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.ids, self.duplicates, self.tags = [], set(), [], {}

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        data = dict(attrs)
        if "id" in data:
            if data["id"] in self.ids:
                self.duplicates.append(data["id"])
            self.ids.add(data["id"])
        for attr in ("href", "src"):
            if attr in data:
                self.links.append(data[attr])


def protected_hashes(root):
    result = {}
    for name in ("generated", "business_report"):
        folder = root / name
        for p in folder.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(folder).as_posix()
            if (rel.startswith(("insights/", "figures_insights/", ".mplconfig_insights/")) or
                rel in {"CONNECTED_RESULTS_REPORT.html", "CONNECTED_RESULTS_REPORT.md", "GRAPHGUARD_BUSINESS_REPORT.html",
                        "GRAPHGUARD_BUSINESS_REPORT.md", "revision_validation.json", "revision_source_inventory.csv"} or
                name == "business_report" and rel == "validation.json"):
                continue
            result[name + "/" + rel] = sha(p)
    return result


def supplement_sources(stage, evidence):
    technical = stage / "generated"
    supplemented = []
    # Keep the old Markdown byte-identical and satisfy its relative references.
    required = ["tables/full_time_blocks.csv", "tables/evaluation_splits.csv", "src/motif/modeling.py",
                "evidence/existing_full_artifact_verification.log", "validation/bundle_checks.json"]
    for rel in required:
        source, dest = BUNDLE / rel, technical / "sources" / rel
        evidence.check(source.is_file(), "deep-link original exists: " + rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            evidence.check(sha(dest) == sha(source), "existing supplement matches original: " + rel)
        else:
            shutil.copy2(source, dest)
        supplemented.append({"source_file": rel, "sha256": sha(source), "origin": "original full report bundle; byte-identical supplement"})
    business = stage / "business_report"
    shutil.copytree(technical / "sources", business / "sources", dirs_exist_ok=True)
    for name in ("model_comparison.csv", "review_budget_comparison.csv", "feature_usage.csv", "completion.json"):
        dest = business / "sources" / name
        evidence.check(not dest.exists() or sha(dest) == sha(technical / name), "business aggregate snapshot matches: " + name)
        shutil.copy2(technical / name, dest)
    return supplemented


def validate_narrative(e):
    # Fixed wording is deliberately tied to the source populations of this report.
    expected = {("paysim", "transaction_novelty", .001): 913, ("paysim", SELECTED["paysim"], .001): 900,
                ("paysim", "transaction_novelty", .005): 1122, ("paysim", SELECTED["paysim"], .005): 1523,
                ("paysim", "transaction_novelty", .01): 1134, ("paysim", SELECTED["paysim"], .01): 2044,
                ("ibm_aml", "transaction_only", .005): 488, ("ibm_aml", SELECTED["ibm_aml"], .005): 505,
                ("ibm_aml", "transaction_only", .01): 877, ("ibm_aml", SELECTED["ibm_aml"], .01): 789}
    for (ds, family, fraction), tp in expected.items():
        e.check(e.budget(ds, family, fraction)["TP_at_K"] == tp, "narrative TP fact: " + str((ds, family, fraction)))
    for ds, recall_wins, f1_wins in (("ibm_aml", 0, 3), ("paysim", 5, 4)):
        periods = [r for r in e.periods if r["dataset"] == ds]
        e.check(sum(r["selected_recall"] > r["baseline_recall"] for r in periods) == recall_wins and
                sum(r["selected_F1"] > r["baseline_F1"] for r in periods) == f1_wins, ds + ": temporal narrative directions")
    ps, novelty = e.model("paysim"), e.model("paysim", "transaction_novelty")
    e.check(ps["TP"] == novelty["TP"] == 1109 and ps["FP"] - novelty["FP"] == 171, "PaySim operating-point novelty comparison")
    cycle = e.motif("ibm_aml", "cycle3_count")
    e.check(cycle["covered_transactions"] == 132 and cycle["covered_positives"] == 41, "IBM rare-cycle cohort narrative")


def validate_links(root, checks):
    pages = {}
    for p in root.rglob("*.html"):
        parser = PageLinks()
        parser.feed(p.read_text(encoding="utf-8"))
        pages[p.resolve()] = parser
        if parser.duplicates:
            raise ValueError("Duplicate anchors: " + str(p))
        if parser.tags.get("script", 0) or parser.tags.get("iframe", 0):
            raise ValueError("Unexpected external/dynamic content: " + str(p))
    count = 0
    for name in ("generated", "business_report"):
        for p in (root / name).rglob("*"):
            if not p.is_file() or p.suffix not in {".md", ".html"}:
                continue
            if p.suffix == ".html":
                links = pages[p.resolve()].links
            else:
                links = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", p.read_text(encoding="utf-8"))
            for link in links:
                target = urlsplit(html.unescape(link))
                if target.scheme or target.netloc:
                    raise ValueError("Report should have no external dependency/link: " + link)
                path = (p.parent / unquote(target.path)).resolve() if target.path else p.resolve()
                if root.resolve() not in path.parents or not path.is_file():
                    raise ValueError("Broken or escaping link: " + str(p.relative_to(root)) + " -> " + link)
                if target.fragment and path.suffix == ".html" and target.fragment not in pages[path].ids:
                    raise ValueError("Broken anchor: " + link)
                count += 1
    checks.append({"check": "recursive HTML/Markdown links, anchors, no scripts, no duplicate IDs", "pass": True, "links_checked": count})
    return count


def revision_manifest(stage, e, before, supplemented, stamp):
    input_paths = [BASE / key for key in before]
    inventory = [{"path": str(p.relative_to(BASE)).replace("\\", "/"), "sha256": sha(p), "role": "preserved pre-revision evidence"}
                 for p in input_paths]
    inventory += [{"path": "bundle/" + r["source_file"], "sha256": r["sha256"], "role": r["origin"]} for r in supplemented]
    facts = {"schema_version": 1, "revision": stamp, "created_utc": datetime.now(timezone.utc).isoformat(),
             "user_facing_date": "2026-10-28", "status": "PASS", "scope": "aggregate-derived insight/report revision; not full pipeline acceptance",
             "python": sys.version, "executable": sys.executable, "platform": sys.platform,
             "builder_sha256": sha(__file__), "builder": Path(__file__).name,
             "no_spark": True, "no_training": True, "no_scoring": True,
             "historical_source_and_result_hashes_preserved": True,
             "html_browser_render_verified": False,
             "html_browser_render_limitation": "Local file navigation blocked by browser policy; HTML structure, links and native PNG figures verified separately.",
             "case_rule_paths": "LIMITED: unchanged historical CP5; saved tree branch is global logic, not case verification",
             "new_derived_tables": ["motif_cohort_insights", "marginal_review_yield", "temporal_insights", "tie_sensitivity", "structure_summary"],
             "tie_sensitivity_scope": "analytic uniform allocation inside boundary score bin; not model CI or significance",
             "supplemented_sources": supplemented,
             "protected_evidence_sha256_before": before,
             "checks": e.checks}
    for name in ("generated", "business_report"):
        write_csv(stage / name / "revision_source_inventory.csv", inventory)
        facts["report_directory"] = name
        write_json(stage / name / "revision_validation.json", facts)
    # Placeholder is needed before validating links to the current manifest.
    link_count = validate_links(stage, e.checks)
    for name in ("generated", "business_report"):
        facts["report_directory"] = name
        facts["checks"] = e.checks
        artifacts = {}
        for p in (stage / name).rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(stage / name).as_posix()
            if p.name in {"CONNECTED_RESULTS_REPORT.html", "CONNECTED_RESULTS_REPORT.md", "GRAPHGUARD_BUSINESS_REPORT.html", "GRAPHGUARD_BUSINESS_REPORT.md"} or rel.startswith(("insights/", "figures_insights/")):
                artifacts[rel] = sha(p)
        facts["report_artifact_sha256"] = artifacts
        facts["recursive_links_checked"] = link_count
        write_json(stage / name / "revision_validation.json", facts)
    # Business has a public validation.json entry point from the old report.
    shutil.copy2(stage / "business_report/revision_validation.json", stage / "business_report/validation.json")
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-reports", action="store_true", help="After successful staging validation, update the two user-facing files with backups")
    parser.add_argument("--check-only", action="store_true", help="Read-only verification of current reports, evidence and current artifact manifests")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12) or Path(sys.executable).resolve() != (REPO / ".venv/Scripts/python.exe").resolve():
        parser.error("Use native Windows repository .venv Python 3.12")
    e = Evidence(BASE / "generated")
    validate_narrative(e)
    if args.check_only:
        counts = []
        for name in ("generated", "business_report"):
            manifest = json.loads((BASE / name / "revision_validation.json").read_text(encoding="utf-8"))
            for rel, digest in manifest["report_artifact_sha256"].items():
                e.check(sha(BASE / name / rel) == digest, name + ": current artifact hash " + rel)
            for rel, digest in manifest["protected_evidence_sha256_before"].items():
                e.check(sha(BASE / rel) == digest, "preserved evidence " + rel)
            for r in manifest["supplemented_sources"]:
                e.check(sha(BASE / name / "sources" / r["source_file"]) == r["sha256"], name + ": supplementary source " + r["source_file"])
            counts.append(len(manifest["report_artifact_sha256"]))
        # Check only the current report pair; revision archives intentionally preserve old broken links.
        temp_root = BASE / "report_revisions"
        pages = []
        for name in ("generated", "business_report"):
            for p in (BASE / name).rglob("*.html"):
                parser_ = PageLinks()
                parser_.feed(p.read_text(encoding="utf-8"))
                pages.append((p, parser_))
        page_map = {p.resolve(): parsed for p, parsed in pages}
        link_count = 0
        for name in ("generated", "business_report"):
            for p in (BASE / name).rglob("*"):
                if not p.is_file() or p.suffix not in {".html", ".md"}:
                    continue
                links = page_map[p.resolve()].links if p.suffix == ".html" else re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", p.read_text(encoding="utf-8"))
                for link in links:
                    target = urlsplit(html.unescape(link))
                    dest = (p.parent / unquote(target.path)).resolve() if target.path else p.resolve()
                    e.check(not target.scheme and not target.netloc and BASE in dest.parents and temp_root not in dest.parents and dest.is_file(), "current link: " + link)
                    if target.fragment and dest.suffix == ".html":
                        e.check(target.fragment in page_map[dest].ids, "current anchor: " + link)
                    link_count += 1
        print(json.dumps({"status": "PASS", "scope": "current report revision and preserved aggregate evidence", "checks": len(e.checks), "links": link_count, "artifacts_per_report": counts, "no_spark": True}, ensure_ascii=False))
        return 0
    before = protected_hashes(BASE)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    revision = BASE / "report_revisions" / stamp
    stage, backup = revision / "after", revision / "before"
    stage.mkdir(parents=True)
    for name in ("generated", "business_report"):
        shutil.copytree(BASE / name, stage / name)
        shutil.copytree(BASE / name, backup / name)
    shutil.copy2(__file__, revision / Path(__file__).name)
    supplemented = supplement_sources(stage, e)
    outputs = {"motif_cohort_insights.csv": e.cohorts, "marginal_review_yield.csv": e.marginal,
               "temporal_insights.csv": e.periods, "tie_sensitivity.csv": e.ties, "structure_summary.csv": e.structure}
    for name in ("generated", "business_report"):
        for filename, rows in outputs.items():
            write_csv(stage / name / "insights" / filename, rows)
    plots(e, stage / "generated/figures_insights")
    shutil.copytree(stage / "generated/figures_insights", stage / "business_report/figures_insights", dirs_exist_ok=True)
    business_report(e, stage / "business_report")
    technical_report(e, stage / "generated")
    for rel, digest in before.items():
        e.check(sha(BASE / rel) == digest and sha(stage / rel) == digest, "preserved original and staged evidence: " + rel)
    revision_manifest(stage, e, before, supplemented, stamp)
    if args.update_reports:
        for name in ("generated", "business_report"):
            for p in (stage / name).rglob("*"):
                if not p.is_file() or ".mplconfig_insights" in p.parts:
                    continue
                dest = BASE / name / p.relative_to(stage / name)
                if dest.is_file() and sha(dest) == sha(p):
                    continue
                rel = dest.relative_to(BASE).as_posix()
                if rel in before:
                    raise ValueError("Refusing to replace protected evidence: " + rel)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
        for rel, digest in before.items():
            e.check(sha(BASE / rel) == digest, "post-update preserved evidence: " + rel)
    write_json(revision / "revision_summary.json", {"revision": stamp, "status": "PASS", "scope": "report-only aggregate insight revision",
               "checks": len(e.checks), "updated_current_reports": args.update_reports, "before": str(backup), "after": str(stage),
               "no_spark": True, "builder_sha256": sha(__file__), "protected_files": len(before)})
    print(json.dumps({"status": "PASS", "checks": len(e.checks), "updated_current_reports": args.update_reports,
                      "revision_directory": str(revision), "protected_evidence_files": len(before), "no_spark": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
