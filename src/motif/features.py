"""Causal temporal motif features, computed by JVM SQL without Python UDFs.

    fan-in:   A -> B <- C       fan-out: A <- B -> C
    relay:    A -> B -> C       reciprocal: A -> B -> A

The current transaction closes the motif. Historical witnesses must have a
strictly smaller timestamp; equal-time rows never supply one another's history.
Expiry events and unbounded prefix sums avoid bounded-window hub rescans.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window, functions as F

from src.motif.config import DatasetSpec
from src.motif.evaluation import require_unlabelled


def normalize_edges(edges: DataFrame, spec: DatasetSpec) -> DataFrame:
    """Validate physical rows once; project a dataset-independent edge contract."""
    needed = {"src", "dst", "step", "amount", "type", "isFraud"}
    if spec.has_currency:
        needed |= {"payment_currency", "receiving_currency"}
    missing = needed.difference(edges.columns)
    if missing:
        raise ValueError(f"Missing edge columns: {sorted(missing)}")
    projected = edges.select(
        F.col("src").cast("string"), F.col("dst").cast("string"),
        F.col("step").cast("long"), F.col("amount").cast("double"),
        F.col("type").cast("string"), F.col("isFraud").cast("double"),
        (F.col("payment_currency") if spec.has_currency else F.lit("PaySim unit")).alias("payment_currency"),
        (F.col("receiving_currency") if spec.has_currency else F.lit("PaySim unit")).alias("receiving_currency"),
    )
    # Validate before casts can conceal malformed labels or fractional timestamps.
    invalid_original = edges.where(
        F.col("step").isNull() | (F.col("step").cast("double") != F.col("step").cast("long"))
        | F.col("isFraud").isNull() | ~F.col("isFraud").cast("double").isin(0.0, 1.0)
    ).limit(1).count()
    invalid = projected.where(
        F.col("amount").isNull() | F.isnan("amount") | (F.abs("amount") == float("inf"))
        | (F.col("amount") < 0) | F.col("step").isNull() | F.col("isFraud").isNull()
        | F.col("src").isNull() | F.col("dst").isNull()
        | (F.trim("src") == "") | (F.trim("dst") == "")
        | F.col("type").isNull() | (F.trim("type") == "")
        | F.col("payment_currency").isNull() | F.col("receiving_currency").isNull()
        | (F.trim("payment_currency") == "") | (F.trim("receiving_currency") == "")
    ).limit(1).count()
    if invalid_original or invalid:
        raise ValueError("Invalid transaction: require finite amount >=0, integer time, nonblank keys and binary labels")
    # Content keys are stable, but identical source records deliberately share a
    # content key. event_id assigned by index_transactions preserves multiplicity.
    key_columns = sorted(needed.difference({"isFraud"}) | {"payment_currency", "receiving_currency"})
    return projected.withColumn("event_key", F.sha2(F.to_json(F.struct(*key_columns)), 256))


def _sweep_counts(buckets: DataFrame, keys: list[str], values: list[str],
                  spec: DatasetSpec, windows_hours: tuple[int, ...]) -> DataFrame:
    """Exact rolling counts using +count / -count expiry events and prefix sums.

    A transaction at integer time s contributes at query t iff s<t<=s+H.
    Thus activate at s+1, expire at s+H+1. Query markers have zero delta.
    All ties are aggregated before the unbounded cumulative sum. This avoids
    Spark's bounded SlidingWindowFunctionFrame rescanning high-degree buffers.
    A key observed at only one timestamp has zero strict-past counts at every
    query. Omit those keys before expanding markers; callers fill missing zero
    histories after their left join. This saves most PaySim account/pair work.
    """
    active_keys = buckets.groupBy(*keys).count().where(F.col("count") > 1).select(*keys)
    buckets = buckets.join(active_keys, keys, "left_semi")
    columns = [f"{value}_{hours}h" for hours in windows_hours for value in values]
    zero = F.lit(0).cast("long")
    entries = [F.struct(F.col("step").cast("long").alias("_time"), F.lit(1).alias("_query"),
                        *[zero.alias(name) for name in columns])]
    for hours in windows_hours:
        steps = hours * 3600 // spec.seconds_per_step
        for shift, sign in ((1, 1), (steps + 1, -1)):
            deltas = [(F.col(value) * sign if h == hours else zero).alias(f"{value}_{h}h")
                      for h in windows_hours for value in values]
            entries.append(F.struct((F.col("step").cast("long") + shift).alias("_time"),
                                    F.lit(0).alias("_query"), *deltas))
    expanded = buckets.select(*keys, F.explode(F.array(*entries)).alias("_marker")).select(*keys, "_marker.*")
    grid = expanded.groupBy(*keys, "_time").agg(F.max("_query").alias("_query"),
                                               *[F.sum(name).alias(name) for name in columns])
    prefix = Window.partitionBy(*keys).orderBy("_time").rowsBetween(Window.unboundedPreceding, Window.currentRow)
    # Select creates a single WindowExec for every cumulative sum.
    cumulative = grid.select(*keys, "_time", "_query", *[F.sum(name).over(prefix).alias(name) for name in columns])
    return cumulative.where(F.col("_query") == 1).select(*keys, F.col("_time").alias("step"), *columns)


def build_star_features(features: DataFrame, spec: DatasetSpec, windows_hours: tuple[int, ...]) -> DataFrame:
    """Role volumes before subtracting same-partner paths in build_motif_features.

    Star witnesses are resolved on demand with resolve_star_witness; computing
    min/max partner in every bounded frame is quadratic at large IBM hubs.
    """
    require_unlabelled(features)
    eligible = features.where((F.col("src") != F.col("dst")) & (F.col("amount") > 0)
                              & (F.col("payment_currency") == F.col("receiving_currency")))
    outgoing = eligible.select("event_id", "step", "type", "payment_currency",
        F.col("src").alias("account"), F.lit(0).alias("direction"))
    incoming = eligible.select("event_id", "step", "type", "payment_currency",
        F.col("dst").alias("account"), F.lit(1).alias("direction"))
    roles = outgoing.unionByName(incoming)
    is_in = F.col("direction") == 1
    relay_type = (F.col("type") == "TRANSFER") if spec.name == "paysim" else F.lit(True)
    keys = ["account", "payment_currency"]
    buckets = roles.groupBy(*keys, "step").agg(
        F.sum(F.when(is_in, 1).otherwise(0)).alias("incoming"),
        F.sum(F.when(~is_in, 1).otherwise(0)).alias("outgoing"),
        F.sum(F.when(is_in & relay_type, 1).otherwise(0)).alias("relay_incoming"))
    counts = _sweep_counts(buckets, keys, ["incoming", "outgoing", "relay_incoming"], spec, windows_hours)
    joined = roles.join(counts, [*keys, "step"])
    is_sender = F.col("direction") == 0
    relay_current = is_sender & ((F.col("type") == "CASH_OUT") if spec.name == "paysim" else F.lit(True))
    expressions = {}
    for hours in windows_hours:
        inc, out = F.col(f"incoming_{hours}h"), F.col(f"outgoing_{hours}h")
        expressions.update({
            f"sender_in_{hours}h": F.when(is_sender, inc),
            f"sender_out_{hours}h": F.when(is_sender, out),
            f"receiver_in_{hours}h": F.when(~is_sender, inc),
            f"receiver_out_{hours}h": F.when(~is_sender, out),
            f"fanin_{hours}h": F.when(~is_sender, inc),
            f"fanout_{hours}h": F.when(is_sender, out),
            f"relay_{hours}h": F.when(relay_current, F.col(f"relay_incoming_{hours}h")),
        })
    projected = joined.select("event_id", *[expression.alias(name) for name, expression in expressions.items()])
    return projected.groupBy("event_id").agg(*[F.max(name).alias(name) for name in expressions])


def build_reciprocal_features(features: DataFrame, spec: DatasetSpec, windows_hours: tuple[int, ...]) -> DataFrame:
    """Counts from expiry-prefix sums; latest opposite witness from one prefix max."""
    require_unlabelled(features)
    pairs = features.where((F.col("src") != F.col("dst")) & (F.col("amount") > 0)
                            & (F.col("payment_currency") == F.col("receiving_currency")))
    pairs = pairs.withColumn("_low", F.least("src", "dst")).withColumn("_high", F.greatest("src", "dst"))
    direction = F.col("src") == F.col("_low")
    relay_type = (F.col("type") == "TRANSFER") if spec.name == "paysim" else F.lit(True)
    keys = ["_low", "_high", "payment_currency"]
    buckets = pairs.groupBy(*keys, "step").agg(
        F.sum(F.when(direction, 1).otherwise(0)).alias("forward"),
        F.sum(F.when(~direction, 1).otherwise(0)).alias("backward"),
        F.sum(F.when(direction & relay_type, 1).otherwise(0)).alias("forward_relay"),
        F.sum(F.when(~direction & relay_type, 1).otherwise(0)).alias("backward_relay"))
    counts = _sweep_counts(buckets, keys, ["forward", "backward", "forward_relay", "backward_relay"], spec, windows_hours)
    history = Window.partitionBy(*keys).orderBy("step").rangeBetween(Window.unboundedPreceding, -1)
    # Remove one-timestamp pairs before sorting witness histories too. All
    # timestamps of a retained pair remain present, including its first event.
    active_pairs = pairs.join(counts, [*keys, "step"])
    latest = active_pairs.withColumn("_forward_event", F.max(F.when(direction, F.struct("step", "event_id"))).over(history))
    latest = latest.withColumn("_backward_event", F.max(F.when(~direction, F.struct("step", "event_id"))).over(history))
    result = latest
    opposite = F.when(direction, F.col("_backward_event")).otherwise(F.col("_forward_event"))
    names = []
    for hours in windows_hours:
        fields = {
            f"same_partner_count_{hours}h": F.when(direction, F.col(f"forward_{hours}h")).otherwise(F.col(f"backward_{hours}h")),
            f"reverse_relay_count_{hours}h": F.when(direction, F.col(f"backward_relay_{hours}h")).otherwise(F.col(f"forward_relay_{hours}h")),
            f"reciprocal_{hours}h": F.when(direction, F.col(f"backward_{hours}h")).otherwise(F.col(f"forward_{hours}h")).cast("double"),
            f"reciprocal_witness_{hours}h": F.when(
                F.col("step") - opposite["step"] <= hours * 3600 // spec.seconds_per_step, opposite["event_id"]),
        }
        for name, expression in fields.items():
            result = result.withColumn(name, expression)
            names.append(name)
    return result.select("event_id", *names)


def resolve_star_witness(features: DataFrame, event_id: int, spec: DatasetSpec,
                         family: str, hours: int) -> DataFrame:
    """Query real past evidence for one event, without dense edge-pair expansion.

    The returned DataFrame may contain multiple valid witnesses; callers can
    order/limit it for a figure. This API also works with exported feature Parquet.
    """
    require_unlabelled(features)
    if family not in {"fanin", "fanout", "relay"} or type(hours) is not int or hours <= 0:
        raise ValueError("Unknown star family or invalid hours")
    rows = features.where(F.col("event_id") == event_id).limit(2).collect()
    if len(rows) != 1:
        raise ValueError("event_id must identify exactly one transaction")
    current = rows[0]
    eligible = features.where((F.col("src") != F.col("dst")) & (F.col("amount") > 0)
                              & (F.col("payment_currency") == F.col("receiving_currency")))
    if current.src == current.dst or current.amount <= 0 or current.payment_currency != current.receiving_currency:
        return eligible.where(F.lit(False))
    eligible = eligible.where((F.col("payment_currency") == current.payment_currency)
        & (F.col("step") < current.step)
        & (F.col("step") >= current.step - hours * 3600 // spec.seconds_per_step))
    if family == "fanin":
        return eligible.where((F.col("dst") == current.dst) & (F.col("src") != current.src))
    if family == "fanout":
        return eligible.where((F.col("src") == current.src) & (F.col("dst") != current.dst))
    if spec.name == "paysim":
        if current.type != "CASH_OUT":
            return eligible.where(F.lit(False))
        eligible = eligible.where(F.col("type") == "TRANSFER")
    return eligible.where((F.col("dst") == current.src) & (F.col("src") != current.dst))


def build_motif_features(features: DataFrame, vertices: DataFrame, spec: DatasetSpec, windows_hours: tuple[int, ...]) -> DataFrame:
    """Unified label-blind API: stars + reciprocal + causal three-account cycles."""
    require_unlabelled(features)
    from src.ibm_aml.motif_finding import build_temporal_cycle_features, find_topological_cycles

    owned = []
    try:
        print("Features: star histories via expiry-prefix sums", flush=True)
        stars = build_star_features(features, spec, windows_hours).localCheckpoint(eager=True)
        owned.append(stars)
        print("Features: reciprocal and same-partner histories", flush=True)
        reciprocal = build_reciprocal_features(features, spec, windows_hours).localCheckpoint(eager=True)
        owned.append(reciprocal)
        combined = features.join(stars, "event_id", "left").join(reciprocal, "event_id", "left")
        for hours in windows_hours:
            # Subtract same-partner paths so reciprocal A->B->A is not counted
            # as a three-account relay. Every count remains a physical-row count.
            for family, subtract in (("fanin", "same_partner_count"), ("fanout", "same_partner_count"),
                                     ("relay", "reverse_relay_count")):
                combined = combined.withColumn(f"{family}_{hours}h", F.greatest(
                    F.coalesce(F.col(f"{family}_{hours}h"), F.lit(0))
                    - F.coalesce(F.col(f"{subtract}_{hours}h"), F.lit(0)), F.lit(0)))
        print("Features: directed topology and chronological cycle evidence", flush=True)
        topology = find_topological_cycles(vertices, features).localCheckpoint(eager=True)
        owned.append(topology)
        evidence = build_temporal_cycle_features(topology, features).withColumn(
            "gap_seconds", F.col("gap_seconds") * spec.seconds_per_step
        ).where(F.col("gap_seconds") <= max(windows_hours) * 3600)
        cycles = evidence.groupBy("event_id").agg(
            F.count("*").cast("double").alias("cycle3_count"),
            F.max("amount_ratio").alias("cycle3_best_ratio"),
            F.min("gap_seconds").alias("cycle3_min_gap_seconds"),
            F.min(F.struct("first_event_id", "second_event_id")).alias("cycle3_witness"),
        )
        # Ratio/gap are separate aggregates; witness is one real path, not a
        # certificate that both extrema came from the same transaction triple.
        numeric = motif_numeric_columns(windows_hours)
        return combined.join(cycles, "event_id", "left").fillna(0, subset=numeric).localCheckpoint(eager=True)
    finally:
        for frame in owned:
            frame.unpersist(blocking=True)


def motif_numeric_columns(windows_hours: tuple[int, ...]) -> list[str]:
    """Allowlist: witness IDs, account names, labels and absolute time stay out."""
    names = [f"{family}_{hours}h" for hours in windows_hours for family in (
        "sender_in", "sender_out", "receiver_in", "receiver_out", "fanin", "fanout", "relay", "reciprocal")]
    return [*names, "cycle3_count", "cycle3_best_ratio", "cycle3_min_gap_seconds"]
