"""Temporal, transaction-level evaluation for explainable motif alerts.

Feature builders receive no ground-truth columns. Thresholds come from training
features, rule selection uses validation labels, and test is evaluated afterwards.
An alert means investigate; an unalerted transaction is not proven legitimate.
"""

from __future__ import annotations

import math

import pandas as pd
from pyspark.sql import DataFrame, functions as F


def require_unlabelled(frame: DataFrame) -> None:
    """Fail closed if a feature/query path accidentally receives ground truth."""
    from pyspark.sql.types import ArrayType, MapType, StructType

    forbidden = {"isfraud", "islaundering", "isflaggedfraud", "label", "target"}
    leaked = []

    def inspect_type(dtype, prefix=""):
        if isinstance(dtype, StructType):
            for field in dtype.fields:
                path = f"{prefix}.{field.name}" if prefix else field.name
                if field.name.lower().replace("_", "") in forbidden:
                    leaked.append(path)
                inspect_type(field.dataType, path)
        elif isinstance(dtype, ArrayType):
            inspect_type(dtype.elementType, prefix + "[]")
        elif isinstance(dtype, MapType):
            inspect_type(dtype.valueType, prefix + "{}")

    inspect_type(frame.schema)
    if leaked:
        raise ValueError(f"Ground truth in feature builder: {sorted(leaked)}")


def index_transactions(edges: DataFrame) -> DataFrame:
    """Assign one run-local ID per physical row, including identical records.

    Materializing once freezes IDs before self-joins. These are not persistent
    transaction IDs and must not be compared across independent Spark runs.
    """
    if "event_id" in edges.columns:
        raise ValueError("event_id already exists")
    return edges.withColumn("event_id", F.monotonically_increasing_id()).localCheckpoint(eager=True)


def temporal_cutoffs(features: DataFrame) -> tuple[int, int]:
    """Approximately 60/20/20 by row count; keep timestamp ties in one split."""
    require_unlabelled(features)
    cuts = features.approxQuantile("step", [0.6, 0.8], 0.001)
    if len(cuts) != 2 or cuts[0] >= cuts[1]:
        raise ValueError("Need two distinct timestamp boundaries")
    return int(cuts[0]), int(cuts[1])


def split_expression(cutoffs: tuple[int, int]):
    """The same predicate is used for features and ground-truth denominators."""
    first, second = cutoffs
    if first >= second:
        raise ValueError("Temporal boundaries must increase")
    return F.when(F.col("step") <= first, "train").when(
        F.col("step") <= second, "validation"
    ).otherwise("test")


def binary_metrics(total: int, positives: int, tp: int, fp: int) -> dict:
    """No accuracy shortcut; undefined precision/recall remain explicitly None."""
    values = (total, positives, tp, fp)
    if any(not math.isfinite(v) or int(v) != v or v < 0 for v in values):
        raise ValueError("Confusion counts must be finite nonnegative integers")
    if positives > total or tp > positives or fp > total - positives:
        raise ValueError("Inconsistent confusion matrix")
    fn, tn = int(positives - tp), int(total - positives - fp)
    alerts = int(tp + fp)
    return {
        "transactions": int(total), "fraud": int(positives),
        "alerts": alerts, "TP": int(tp), "FP": int(fp), "FN": fn, "TN": tn,
        "precision": tp / alerts if alerts else None,
        "recall": tp / positives if positives else None,
        "F1": 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else None,
        "prevalence": positives / total if total else None,
        "alert_rate": alerts / total if total else None,
    }


def evaluate_alerts(alerts: DataFrame, truth: DataFrame) -> pd.DataFrame:
    """One prediction per transaction, never one per motif combination.

    truth has event_id, split, isFraud. Denominators include *all* transactions,
    including types/currencies that a particular motif cannot reach.
    """
    ids = alerts.select("event_id").distinct().withColumn("alert", F.lit(1))
    counts = truth.join(ids, "event_id", "left").groupBy("split").agg(
        F.count("*").alias("total"), F.sum("isFraud").alias("positives"),
        F.sum(F.when((F.col("alert") == 1) & (F.col("isFraud") == 1), 1).otherwise(0)).alias("tp"),
        F.sum(F.when((F.col("alert") == 1) & (F.col("isFraud") == 0), 1).otherwise(0)).alias("fp"),
    ).collect()
    records = [{"split": row.split, **binary_metrics(row.total, row.positives, row.tp, row.fp)}
               for row in counts]
    return pd.DataFrame(records).set_index("split").reindex(["train", "validation", "test"]).reset_index()


def select_validation_rule(scores: pd.DataFrame) -> dict:
    """Maximize validation F1, then precision, fewer FP, stable rule ID.

    The caller passes only validation scores. No supported true positive means
    abstain, rather than selecting an arbitrary rule merely to emit alerts.
    """
    if scores.empty or not (scores["TP"] > 0).any():
        return {"rule_id": "abstain", "reason": "No validation true positive; no supported threshold"}
    ranked = scores.assign(
        _f1=scores["F1"].fillna(-1), _precision=scores["precision"].fillna(-1)
    ).sort_values(["_f1", "_precision", "FP", "rule_id"], ascending=[False, False, True, True])
    return ranked.iloc[0].drop(labels=["_f1", "_precision"]).to_dict()
