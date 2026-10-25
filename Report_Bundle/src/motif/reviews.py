"""Khánh's ETL, PageRank and LPA reviews, imported by concise notebooks."""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from graphframes import GraphFrame
from pyspark.sql import functions as F

from src.common.graph_utils import load_graph
from src.ibm_aml.verify_communities import (compare_partition_frames, numeric, same_keys, unique_keys, verify_community_frames)


@dataclass
class ETLReview:
    comparison: pd.DataFrame
    counts: pd.DataFrame
    log: str


def review_documented_cycle(spark, repo: Path) -> pd.DataFrame:
    """Audit a Patterns cycle against actual raw-mapped transactions; no detection claim."""
    from src.ibm_aml.visualize import read_three_account_cycles, select_example

    cycles = read_three_account_cycles(repo / "data/raw/ibm_aml/HI-Small_Patterns.txt")
    selected = select_example(cycles, repo / "results/ibm_aml/fraud_directed_cycles.csv")
    graph = load_graph(spark, str(repo / "data/processed/ibm_aml"))
    records = []
    for payment in selected:
        count = graph.edges.where(
            (F.col("src") == payment["src"]) & (F.col("dst") == payment["dst"])
            & (F.col("timestamp") == F.lit(payment["timestamp"]))
            & (F.col("amount") == float(payment["amount"]))
            & (F.col("payment_currency") == payment["payment_currency"]) & (F.col("isFraud") == 1)
        ).count()
        if count < 1:
            raise AssertionError("Documented cycle edge absent from input")
        records.append({**payment, "matching_input_rows": count, "source_three_hop_cycles": len(cycles)})
    return pd.DataFrame(records)


def review_ibm_etl(spark, repo: Path) -> ETLReview:
    """Full raw ETL contract suite and bidirectional multiset reconciliation."""
    from src.ibm_aml.etl import build_ibm_edges, build_ibm_vertices
    from tests.test_ibm_aml_etl import run_tests

    log = StringIO()
    edges = vertices = None
    try:
        with redirect_stdout(log):
            edges = build_ibm_edges(spark, str(repo / "data/raw/ibm_aml/HI-Small_Trans.csv")).cache()
            vertices = build_ibm_vertices(spark, str(repo / "data/raw/ibm_aml/HI-Small_accounts.csv"), edges).cache()
            run_tests(spark, vertices, edges, is_sample=False)
        saved = load_graph(spark, str(repo / "data/processed/ibm_aml"))
        records = []
        for name, fresh, persisted in (("vertices", vertices, saved.vertices), ("edges", edges, saved.edges)):
            columns = sorted(fresh.columns)
            missing = fresh.select(columns).exceptAll(persisted.select(columns)).limit(1).count()
            extra = persisted.select(columns).exceptAll(fresh.select(columns)).limit(1).count()
            if missing or extra:
                raise AssertionError("Raw/Parquet multiset mismatch: " + name)
            records.append({"table": name, "raw_minus_parquet": missing, "parquet_minus_raw": extra, "status": "PASS"})
        counts = pd.DataFrame([{"vertices": vertices.count(), "edges": edges.count(), "status": "PASS"}])
        return ETLReview(pd.DataFrame(records), counts, log.getvalue())
    finally:
        for frame in (edges, vertices):
            if frame is not None:
                frame.unpersist(blocking=True)


@dataclass
class LPAReview:
    metrics: pd.DataFrame
    overview: pd.DataFrame
    size_distribution: pd.DataFrame
    amounts: pd.DataFrame
    stability: pd.DataFrame
    log: str


def review_ibm_lpa(spark, repo: Path, checkpoint: Path) -> LPAReview:
    """Re-run full LPA, independent checker, and two live sample partitions."""
    from src.ibm_aml.community_detection import analyze_communities, run_lpa

    full = load_graph(spark, str(repo / "data/processed/ibm_aml"))
    log = StringIO()
    owned = []
    try:
        with redirect_stdout(log):
            labels = run_lpa(full, spark, max_iter=5, checkpoint_dir=checkpoint / "full")
            owned.append(labels)
            _, summary = analyze_communities(labels, full, top_n=8)
            summary = summary.cache()
            owned.append(summary)
            overview = summary.orderBy(F.desc("member_count"), F.asc("label")).limit(50)
            amounts = full.edges.join(labels.select(F.col("id").alias("src"), "label"), "src").groupBy(
                "label", "payment_currency"
            ).agg(F.count("*").alias("total_tx_count"), F.sum("amount").alias("total_tx_amount")).cache()
            owned.append(amounts)
            metrics = verify_community_frames(full, labels, summary, overview, amounts)
            if metrics["internal_edges"] + metrics["cross_edges"] != metrics["edges"]:
                raise AssertionError("Community edge counts do not reconcile")
            size_distribution = summary.groupBy("member_count").count().orderBy("member_count").toPandas()
            top = overview.limit(8).toPandas()
            usd_amounts = amounts.where(F.col("payment_currency") == "US Dollar").orderBy(
                F.desc("total_tx_amount")).limit(8).toPandas()
            sample = load_graph(spark, str(repo / "data/processed/sample/ibm_aml"))
            first = run_lpa(sample, spark, max_iter=5, checkpoint_dir=checkpoint / "sample_1")
            owned.append(first)
            second = run_lpa(sample, spark, max_iter=5, checkpoint_dir=checkpoint / "sample_2")
            owned.append(second)
            for assignments in (first, second):
                unique_keys(assignments, ["id"], "sample assignments")
                same_keys(assignments, sample.vertices, ["id"], "sample coverage")
                numeric(assignments, ["label"])
            stability = compare_partition_frames(second, first)
        return LPAReview(pd.DataFrame([metrics]), top, size_distribution, usd_amounts, pd.DataFrame([stability]), log.getvalue())
    finally:
        for frame in owned:
            frame.unpersist(blocking=True)


def pagerank_probability(adjacency,damping=0.85,iterations=30,repair_dangling=True):
    # adjacency[v,u] đếm cạnh v→u; chuyển vị để dùng vector cột.
    adjacency = np.asarray(adjacency,dtype=float)
    assert adjacency.ndim == 2 and adjacency.shape[0] == adjacency.shape[1]
    assert (adjacency >= 0).all() and 0 <= damping <= 1
    n = adjacency.shape[0]
    out_degree = adjacency.sum(axis=1)
    transition = np.divide(adjacency,out_degree[:,None],out=np.zeros_like(adjacency),
                           where=out_degree[:,None]>0).T
    if repair_dangling:
        transition[:,out_degree==0] = 1/n
    google = damping*transition + (1-damping)*np.ones((n,n))/n
    rank = np.ones(n)/n
    history = [rank.copy()]
    for _ in range(iterations):
        rank = google @ rank
        history.append(rank.copy())
    return np.asarray(history)


def review_pagerank():
    chain = np.array([[0,1,0],[0,0,1],[0,0,0]])
    trap = chain.copy()
    trap[2,2] = 1
    raw_chain = pagerank_probability(chain,1,repair_dangling=False)
    fixed_chain = pagerank_probability(chain,0.85)
    trapped = pagerank_probability(trap,1)
    escapable = pagerank_probability(trap,0.85)
    assert np.allclose(raw_chain[:4].sum(axis=1),[1,2/3,1/3,0])
    assert np.allclose(fixed_chain.sum(axis=1),1)
    assert np.allclose(trapped[-1],[0,0,1])
    assert np.allclose(escapable[-1],[0.05,0.0925,0.8575])
    return {"table": pd.DataFrame({'account':['A','B','T'],'d=1':trapped[-1],'d=0.85':escapable[-1]}),
            "raw_chain": raw_chain, "fixed_chain": fixed_chain, "trapped": trapped, "escapable": escapable}


def expect_rejection(label,operation):
    try:
        operation()
    except ValueError as error:
        return {'case':label,'status':'PASS: rejected','reason':str(error)}
    raise AssertionError('Checker không từ chối: '+label)


def review_checker_guardrails(spark):
    # Phản ví dụ currency đi qua chính checker đầy đủ, không chỉ qua một assert riêng.
    review_vertices = spark.sql("SELECT * FROM VALUES ('A','1',0.0),('B','1',0.0) AS v(id,bank_id,balance)")
    review_edges = spark.sql("SELECT 'A' AS src,'B' AS dst,0 AS isFraud,10.0 AS amount,'US Dollar' AS payment_currency")
    review_graph = GraphFrame(review_vertices,review_edges)
    review_assignments = review_vertices.select('id').withColumn('label',F.lit(1).cast('long'))
    review_summary = spark.sql("SELECT CAST(1 AS BIGINT) AS label,2 AS member_count,1 AS unique_banks_count,"
        "0.0 AS avg_balance,1 AS total_tx_count,0 AS laundering_tx_count,1 AS internal_tx_count,"
        "0 AS internal_laundering_count,0.0 AS laundering_rate")
    review_amounts = spark.sql("SELECT CAST(1 AS BIGINT) AS label,'US Dollar' AS payment_currency,"
        "1 AS total_tx_count,10.0 AS total_tx_amount")

    one = spark.sql("SELECT 'A' AS id,'1' AS label")
    two = spark.sql("SELECT * FROM VALUES ('A','1'),('B','2') AS t(id,label)")
    rejections = [
        expect_rejection('duplicate account',lambda:unique_keys(one.unionByName(one),['id'],'assignments')),
        expect_rejection('missing account',lambda:same_keys(one,two,['id'],'assignments')),
        expect_rejection('null label',lambda:numeric(spark.sql("SELECT CAST(NULL AS STRING) AS label"),['label'])),
        expect_rejection('fractional label',lambda:numeric(spark.sql("SELECT '1.5' AS label"),['label'])),
        expect_rejection('NaN amount',lambda:numeric(spark.sql("SELECT 'NaN' AS amount"),['amount'],integral=False)),
        expect_rejection('mixed-currency summary field',lambda:verify_community_frames(
            review_graph,review_assignments,review_summary.withColumn('total_tx_amount',F.lit(10.0)),
            review_summary,review_amounts)),
    ]
    assert 'payment_currency' in rejections[-1]['reason']
    return pd.DataFrame(rejections)
