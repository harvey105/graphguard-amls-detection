r"""Compare accepted full degree distributions without starting another Spark job.

Usage:
    & .\.venv\Scripts\python.exe -m src.comparison.degree_distribution
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, StrMethodFormatter
import pandas as pd
from pyspark.sql import functions as F

from src.common.graph_utils import load_graph
from src.common.spark_session import get_graph_session

ROOT = Path(__file__).resolve().parents[2]


def validate_full_distribution(table, vertices, edges):
    """Require every account, including isolates, and transaction degree sum=2E."""
    table = table[["degree", "account_count"]].copy()
    for column in table:
        values = pd.to_numeric(table[column], errors="raise")
        if not all(math.isfinite(float(x)) and float(x).is_integer() for x in values):
            raise ValueError("Degree bins/counts must be finite integers")
        table[column] = values.astype("int64")
    if table.empty or table.degree.duplicated().any() or (table.degree < 0).any() or (table.account_count <= 0).any():
        raise ValueError("Invalid or duplicate degree bins")
    if int(table.account_count.sum()) != vertices or int((table.degree*table.account_count).sum()) != 2*edges:
        raise ValueError("Full degree distribution lost accounts or transaction multiplicity")
    table["proportion"] = table.account_count / vertices
    return table.sort_values("degree").reset_index(drop=True)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_full_distributions(root=ROOT):
    """Bind small aggregate CSVs to accepted full reports and their artifact index."""
    from src.common.project_audit import FULL_COUNTS
    tables, inputs = {}, {}
    for dataset in ("paysim", "ibm_aml"):
        base = (root/"results/full_system"/dataset).resolve()
        pointer = json.loads((base/"latest.json").read_text(encoding="utf-8"))
        directory = Path(pointer["directory"]).resolve()
        if pointer["status"] != "completed" or not directory.is_relative_to(base):
            raise ValueError("Comparison requires an accepted full run: "+dataset)
        report_path, index_path = directory/"report.json", directory/"artifact_index.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (_sha(report_path) != pointer["report_sha256"] or report["status"] != "completed"
                or report["scope"] != "full" or report["dataset"] != dataset):
            raise ValueError("Changed/non-full comparison input: "+dataset)
        evidence = json.loads((directory/"run.json").read_text(encoding="utf-8"))
        recorded = {Path(item["path"]).name:item["sha256"] for item in evidence["outputs"]}
        if evidence["status"] != "PASS" or any(recorded.get(path.name) != _sha(path) for path in (report_path,index_path)):
            raise ValueError("Unverified report/index for comparison")
        csv_path = directory/"degree_distribution.csv"
        member = next(item for item in json.loads(index_path.read_text(encoding="utf-8")) if item["path"]==csv_path.name)
        if csv_path.stat().st_size != member["bytes"] or _sha(csv_path) != member["sha256"]:
            raise ValueError("Full degree CSV changed after acceptance")
        vertices, edges = FULL_COUNTS[dataset]
        if (report["integrity"]["num_vertices"],report["support"]["n"]) != (vertices,edges):
            raise ValueError("Comparison input is not the declared full population")
        tables[dataset] = validate_full_distribution(pd.read_csv(csv_path),vertices,edges)
        inputs[dataset] = {"run_id":directory.name,"report_sha256":_sha(report_path),
                           "degree_csv_sha256":_sha(csv_path),"vertices":vertices,"edges":edges}
    return tables, inputs


def _comparison_table(tables):
    return pd.concat([table.assign(dataset=dataset)[["dataset","degree","account_count","proportion"]]
                      for dataset,table in tables.items()],ignore_index=True)


def full_comparison(output_dir=None, *, verify_only=False, root=ROOT):
    """Render/verify full PMFs from frozen aggregates; never rescan graph data."""
    from src.common.project_audit import configure_runtime, check_memory
    configure_runtime()
    directory = Path(output_dir or root/"results/comparison/full").resolve()
    tables, inputs = load_full_distributions(root)
    csv_path = directory/"degree_distribution_paysim_vs_ibm.csv"
    png_path = directory/"degree_distribution_paysim_vs_ibm.png"
    manifest_path = directory/"comparison_run.json"
    if verify_only:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["status"] != "PASS" or manifest["scope"] != "full" or manifest["inputs"] != inputs or manifest["source_sha256"] != _sha(__file__):
            raise ValueError("Full comparison is stale or has different source/inputs")
        for path in (csv_path,png_path):
            if _sha(path) != manifest["outputs"][path.name]:
                raise ValueError("Changed full comparison output: "+path.name)
        expected = _comparison_table(tables).sort_values(["dataset","degree"]).reset_index(drop=True)
        actual = pd.read_csv(csv_path).sort_values(["dataset","degree"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(actual,expected,check_dtype=False,rtol=1e-12,atol=1e-15)
        if not png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid comparison PNG")
        check_memory()
        return {"status":"PASS","scope":"full","datasets":inputs,"Spark_started":False}
    directory.mkdir(parents=True,exist_ok=True)
    _comparison_table(tables).to_csv(csv_path,index=False,encoding="utf-8-sig")
    plot_degree_comparison(tables["paysim"],tables["ibm_aml"],png_path,
                           inputs["paysim"]["vertices"],inputs["ibm_aml"]["vertices"],scope="FULL accepted graphs")
    check_memory()
    manifest = {"schema_version":"graphguard.full_degree_comparison.v1","status":"PASS","scope":"full",
        "created_utc":datetime.now(timezone.utc).isoformat(),"system":platform.system(),"python":platform.python_version(),
        "pandas":pd.__version__,"matplotlib":matplotlib.__version__,
        "inputs":inputs,"source_sha256":_sha(__file__),"outputs":{p.name:_sha(p) for p in (csv_path,png_path)},"Spark_started":False}
    temporary = manifest_path.with_suffix(".tmp")
    with temporary.open("w",encoding="utf-8",newline="\n") as stream:
        stream.write(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,manifest_path)
    return full_comparison(directory,verify_only=True,root=root)


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
    fig, ax = plt.subplots(figsize=(12, 7), layout="constrained")

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
                s=65, alpha=0.9, edgecolors="white", linewidths=0.6,
            )
            largest = positive.iloc[-1]
            ax.annotate(
                f"{name}: max degree {int(largest['degree']):,}",
                (largest["degree"], largest["proportion"]),
                xytext=(-12, 22), textcoords="offset points", ha="right",
                fontsize=11, color=color,
                arrowprops={"arrowstyle": "-", "color": color},
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
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value * 100:g}%"))
        ax.minorticks_off()
        ax.tick_params(labelsize=12)
        ax.margins(x=0.08, y=0.12)
        ax.set_xlabel("Total degree, k (log scale)", fontsize=13, labelpad=10)
        ax.set_ylabel("Accounts with degree k (%) — log scale", fontsize=13, labelpad=10)
        ax.set_title(
            "Degree Distribution: PaySim vs IBM AML\n"
            f"{scope} • Transaction-based total degree • Log–log axes",
            fontsize=15, pad=16,
        )
        ax.grid(which="major", linestyle="--", alpha=0.3)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(fontsize=12, loc="upper right")
        fig.savefig(output_path, dpi=300)
    finally:
        plt.close(fig)
    print(f"[+] Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare PaySim and IBM AML degree distributions.")
    parser.add_argument("--sample", action="store_true", help="Explicit legacy sample Spark comparison")
    parser.add_argument("--verify-only", action="store_true", help="Verify accepted full comparison; no Spark")
    parser.add_argument("--input", default=None,
                        help="PaySim Parquet directory")
    parser.add_argument("--ibm-input", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    custom = args.input is not None or args.ibm_input is not None
    if custom and (args.sample or not args.input or not args.ibm_input):
        parser.error("Custom mode requires both input paths and cannot use --sample")
    if args.verify_only and (args.sample or custom):
        parser.error("--verify-only accepts only full-system comparison")
    if not args.sample and not custom:
        print(json.dumps(full_comparison(args.output_dir,verify_only=args.verify_only),indent=2))
        return

    # Resolve before the shared Windows runtime changes the working directory.
    paysim_input = Path(args.input or "data/processed/sample/paysim").resolve()
    ibm_input = Path(args.ibm_input or "data/processed/sample/ibm_aml").resolve()
    output_dir = Path(args.output_dir or "results/comparison").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    spark = get_graph_session("Viz-Degree-Comparison",driver_memory="4g" if args.sample else "5g")
    try:
        graph = load_graph(spark, str(paysim_input))
        ibm_graph = load_graph(spark, str(ibm_input))
        paysim_distribution, paysim_count = calculate_degree_distribution(graph)
        ibm_distribution, ibm_count = calculate_degree_distribution(ibm_graph)
        # Preserve raw counts and fractions for report authors; no binning or fitting.
        tables = []
        for name, distribution, count in (
            ("PaySim", paysim_distribution, paysim_count),
            ("IBM AML", ibm_distribution, ibm_count),
        ):
            table = distribution.copy()
            isolated = count - int(table["account_count"].sum())
            if isolated < 0:
                raise ValueError(f"{name}: degree counts exceed vertex count.")
            if isolated:
                table.loc[len(table)] = [0, isolated, isolated / count]
            table.insert(0, "dataset", name)
            table = table.astype({"degree": "int64", "account_count": "int64"})
            tables.append(table.sort_values("degree"))
        csv_path = output_dir / "degree_distribution_paysim_vs_ibm.csv"
        pd.concat(tables, ignore_index=True).to_csv(
            csv_path, index=False, encoding="utf-8-sig"
        )
        print(f"[+] Saved: {csv_path}")
        scope = "Sample graphs" if all(
            "sample" in path.parts for path in (paysim_input, ibm_input)
        ) else "Selected graphs"
        plot_degree_comparison(
            paysim_distribution, ibm_distribution,
            output_dir / "degree_distribution_paysim_vs_ibm.png",
            paysim_count, ibm_count, scope=scope,
        )

        print("[+] Done")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
