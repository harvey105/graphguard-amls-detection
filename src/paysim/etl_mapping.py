"""
File: src/utils/etl_mapping.py
Role: Person 2 — ETL Mapping Functions for PaySim -> GraphFrames Schema (Section 4.1)
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def build_vertices_df(raw_df: DataFrame) -> DataFrame:
    """
    Extracts unique vertices (id, account_type, balance) from raw PaySim transactions.

    Performance note:
      Uses a single groupBy + max_by aggregate rather than a window function +
      row_number. max_by resolves the "latest by step" value in one aggregation
      stage (with partial combine before shuffle), which is materially cheaper
      than a full sort-within-partition over ~9.07M account groups.

    Tie-break rule for the 1,769 accounts that appear as both sender and receiver
    (confirmed in Task 2.1): take the balance from each account's most recent
    (max `step`) appearance, using the POST-transaction balance (newbalance*) at
    that event.
      NOTE — flag this to Person 1: the proposal's Section 4.1 table literally
      names oldbalanceOrg/oldbalanceDest as the source columns, but its own
      wording ("most recent available balance") better matches newbalance*,
      since oldbalance* at an account's last event is actually one step BEHIND
      its true final state. This is a genuine ambiguity in the proposal itself,
      not a mistake on our end — document whichever the team settles on in the
      report. Swapping back to oldbalance* is a one-line change (see below).

    account_type is derived once from the `id` prefix after deduplication
    (not per-event), since it's a static property of the account, not of
    which role it happened to play in a given transaction.
    """
    senders = raw_df.select(
        F.col("nameOrig").alias("id"),
        F.col("newbalanceOrig").alias("balance"),   # swap to oldbalanceOrg if team decides otherwise
        F.col("step"),
    )
    receivers = raw_df.select(
        F.col("nameDest").alias("id"),
        F.col("newbalanceDest").alias("balance"),   # swap to oldbalanceDest if team decides otherwise
        F.col("step"),
    )
    all_events = senders.unionByName(receivers)

    vertices_df = (
        all_events.groupBy("id")
        .agg(F.max_by("balance", "step").alias("balance"))
        .withColumn(
            "account_type",
            F.when(F.substring(F.col("id"), 1, 1) == "C", "Customer")
             .when(F.substring(F.col("id"), 1, 1) == "M", "Merchant")
             .otherwise("Unknown"),
        )
        .select("id", "account_type", "balance")
    )
    return vertices_df


def build_edges_df(raw_df: DataFrame) -> DataFrame:
    """
    Extracts the directed Edges DataFrame (Section 4.1) from raw PaySim transactions.

    Columns:
      src      (string)  <- nameOrig (originating account)
      dst      (string)  <- nameDest (destination account)
      amount   (double)  <- amount, direct passthrough
      step     (int)     <- step, kept as a raw simulation-hour proxy (1..744),
                             NOT converted to a fake datetime (Section 7.5 caveat).
                             Flag this to Person 1 and Person 4 so nobody downstream
                             assumes real calendar time when building motif logic.
      type     (string)  <- transaction category (CASH_OUT, TRANSFER, PAYMENT, ...).
                             Not in the literal Section 4.1 table, but kept because
                             Task 2.1's own analysis (task2_1_analysis.md, Section 5,
                             Option 1) recommends redefining Task 3's motif as a 2-hop
                             relay (TRANSFER -> CASH_OUT) instead of a 3-node cycle,
                             since exhaustive 3-node cycles are 0 in PaySim. Person 4
                             needs `type` on the edge to filter that pattern — flag
                             this addition to them explicitly, it's not in the spec.
      isFraud  (short)   <- ground-truth fraud label, kept per the Work Plan's Task
                             2.3 notes, to validate Motif/LPA findings against truth.

    Note: this is a straight column-rename/select with no aggregation or row
    filtering, so edges_df.count() == raw_df.count() holds by construction —
    worth stating in the report, but it can't catch a mapping bug on its own
    (no rows are ever dropped or added). The referential-integrity join against
    vertices_df (see tests/test_task2_3_edges.py) is the check that actually
    verifies the mapping is correct.
    """
    edges_df = raw_df.select(
        F.col("nameOrig").alias("src"),
        F.col("nameDest").alias("dst"),
        F.col("amount").cast("double").alias("amount"),
        F.col("step").cast("integer").alias("step"),
        F.col("type").alias("type"),
        F.col("isFraud").cast("short").alias("isFraud"),
    )
    return edges_df
