"""Small interpretable risk models and exact score-histogram evaluation.

This is supervised scoring of label-blind motif features, not an unsupervised
claim that a motif proves fraud. The transaction-only ablation is always fitted
and evaluated under exactly the same temporal protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd
from pyspark.ml import Pipeline
from pyspark.ml.classification import DecisionTreeClassifier
from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import DataFrame, functions as F

from src.motif.config import AnalysisConfig, CENTRALITY_COLUMNS, COMMUNITY_COLUMNS, SYSTEM_FAMILY_GROUPS
from src.motif.evaluation import binary_metrics, require_unlabelled
from src.motif.features import motif_numeric_columns


FAMILIES = ("transaction_only", "motif_assisted")


@dataclass
class RiskModel:
    family: str
    pipeline: object
    scales: DataFrame
    feature_names: list[str]
    training: dict

    def importance(self) -> pd.DataFrame:
        if self.pipeline is None:
            return pd.DataFrame(columns=["feature", "importance"])
        values = self.pipeline.stages[-1].featureImportances.toArray()
        return pd.DataFrame({"feature": self.feature_names, "importance": values}).sort_values(
            "importance", ascending=False).reset_index(drop=True)


def _prepare_amounts(features: DataFrame, scales: DataFrame) -> DataFrame:
    """Use training q90 of each currency/type; never compare nominal currencies."""
    joined = features.join(scales, ["payment_currency", "type"], "left")
    denominator = F.greatest(F.coalesce(F.col("training_q90"), F.lit(1.0)), F.lit(1e-12))
    return joined.withColumn("scaled_amount", F.log1p(F.least(F.col("amount") / denominator, F.lit(1e12)))).withColumn(
        "unseen_amount_group", F.col("training_q90").isNull().cast("double")
    ).withColumn("fx_payment", (F.col("payment_currency") != F.col("receiving_currency")).cast("double"))


def fit_risk_model(features: DataFrame, truth: DataFrame, train_end: int, family: str, config: AnalysisConfig, *, spill_training: bool = False) -> RiskModel:
    """Fit only on the prefix, including preprocessing and class weights.

    sqrt(negative/positive) reduces imbalance without duplicating rows. The
    weighted leaf score is a ranking score, not a calibrated fraud probability.
    """
    require_unlabelled(features)
    if family not in SYSTEM_FAMILY_GROUPS:
        raise ValueError(f"Unknown model family: {family}")
    train = features.where(F.col("step") <= train_end)
    scales = train.where(F.col("amount") > 0).groupBy("payment_currency", "type").agg(
        F.percentile_approx("amount", 0.9, 10_000).alias("training_q90")
    ).localCheckpoint(eager=True)
    names = ["type_index", "currency_index", "scaled_amount", "unseen_amount_group", "fx_payment"]
    numeric = []
    for group in SYSTEM_FAMILY_GROUPS[family]:
        numeric += {"motif": motif_numeric_columns(config.windows_hours),
                    "centrality": CENTRALITY_COLUMNS, "community": COMMUNITY_COLUMNS, "novelty": ["src_seen", "dst_seen"]}[group]
    names += numeric
    available = ["event_id", "step", "type", "payment_currency", "receiving_currency", "amount", *numeric]
    labelled = _prepare_amounts(train.select(available), scales).join(
        truth.select("event_id", "isFraud"), "event_id"
    )
    support = labelled.agg(F.count("*").alias("n"), F.sum("isFraud").alias("p")).first()
    n, p = int(support.n), int(support.p or 0)
    weight = math.sqrt((n - p) / p) if 0 < p < n else 1.0
    metadata = {"train_end": int(train_end), "rows": n, "fraud": p,
                "positive_class_weight": weight, "status": "fitted" if 0 < p < n else "abstain: one training class"}
    if not 0 < p < n:
        return RiskModel(family, None, scales, names, metadata)
    from pyspark import StorageLevel
    labelled = labelled.withColumn("_weight", F.when(F.col("isFraud") == 1, weight).otherwise(1.0)).persist(
        StorageLevel.DISK_ONLY if spill_training else StorageLevel.MEMORY_AND_DISK)
    indexer = StringIndexer(inputCols=["type", "payment_currency"], outputCols=["type_index", "currency_index"],
                            stringOrderType="alphabetAsc", handleInvalid="keep")
    assembler = VectorAssembler(inputCols=names, outputCol="features", handleInvalid="error")
    tree = DecisionTreeClassifier(labelCol="isFraud", featuresCol="features", weightCol="_weight",
        maxDepth=config.tree_depth, maxBins=64, minInstancesPerNode=config.minimum_leaf_rows, seed=config.seed)
    try:
        fitted = Pipeline(stages=[indexer, assembler, tree]).fit(labelled)
    finally:
        labelled.unpersist(blocking=True)
    return RiskModel(family, fitted, scales, names, metadata)


def score_transactions(model: RiskModel, features: DataFrame) -> DataFrame:
    """One score per original transaction. Ground truth never enters inference."""
    require_unlabelled(features)
    if model.pipeline is None:
        return features.withColumn("risk_score", F.lit(0.0))
    prepared = _prepare_amounts(features, model.scales)
    scored = model.pipeline.transform(prepared)
    return scored.select(*features.columns, vector_to_array("probability")[1].alias("risk_score"))


def score_histogram(scores: DataFrame, truth: DataFrame, start: int | None, end: int | None) -> pd.DataFrame:
    """Collect at most two rows per tree leaf, not millions of predictions."""
    interval = scores
    if start is not None:
        interval = interval.where(F.col("step") > start)
    if end is not None:
        interval = interval.where(F.col("step") <= end)
    return interval.select("event_id", "risk_score").join(
        truth.select("event_id", "isFraud"), "event_id"
    ).groupBy("risk_score", "isFraud").count().toPandas()


def metrics_at_threshold(histogram: pd.DataFrame, threshold: float) -> dict:
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Score threshold must be finite and inside [0,1]")
    if histogram.empty:
        return binary_metrics(0, 0, 0, 0)
    n = int(histogram["count"].sum())
    positives = int(histogram.loc[histogram.isFraud == 1, "count"].sum())
    chosen = histogram.risk_score >= threshold
    tp = int(histogram.loc[chosen & (histogram.isFraud == 1), "count"].sum())
    fp = int(histogram.loc[chosen & (histogram.isFraud == 0), "count"].sum())
    return binary_metrics(n, positives, tp, fp)


def wilson_interval(successes: int, trials: int) -> tuple[float | None, float | None]:
    """95% Wilson interval; undefined when the denominator is zero."""
    if trials == 0:
        return None, None
    if not 0 <= successes <= trials:
        raise ValueError("Invalid binomial counts")
    z = 1.959963984540054
    p = successes / trials
    scale = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / scale
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / scale
    return max(0.0, center - half), min(1.0, center + half)


def precision_recall_curve(histogram: pd.DataFrame) -> tuple[pd.DataFrame, float | None]:
    """Exact average precision over the tree's discrete score levels, including ties."""
    if histogram.empty:
        return pd.DataFrame(), None
    bins = histogram.assign(positives=histogram.isFraud * histogram["count"]).groupby("risk_score").agg(
        positives=("positives", "sum"), transactions=("count", "sum")
    ).sort_index(ascending=False)
    p = int(bins.positives.sum())
    bins["precision"] = bins.positives.cumsum() / bins.transactions.cumsum()
    bins["recall"] = bins.positives.cumsum() / p if p else float("nan")
    average_precision = float((bins.precision * bins.positives / p).sum()) if p else None
    return bins.reset_index(), average_precision


def choose_walk_forward_rule(fold_scores: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Select across ALL families, including the transaction-only ablation.

    Mean fold F1 is the objective; worst-fold F1 and lower alert volume break
    ties. Missing/empty validation folds are an error, not silently discarded.
    """
    if fold_scores.empty:
        return {"family": "abstain", "threshold": 1.0, "reason": "No validation support"}, pd.DataFrame()
    if (fold_scores.transactions <= 0).any() or fold_scores.F1.isna().any():
        raise ValueError("Every validation fold must contain transactions and positive labels")
    leaderboard = fold_scores.groupby(["family", "threshold"], as_index=False).agg(
        mean_F1=("F1", "mean"), worst_F1=("F1", "min"), std_F1=("F1", "std"),
        mean_precision=("precision", "mean"), TP=("TP", "sum"), FP=("FP", "sum"),
        FN=("FN", "sum"), transactions=("transactions", "sum"), folds=("fold", "nunique"),
    )
    expected_folds = fold_scores.fold.nunique()
    if (leaderboard.folds != expected_folds).any():
        raise ValueError("Incomplete walk-forward candidate")
    # A structural rule must improve over its simpler baseline, including
    # temporal component pilots where novelty is the no-graph baseline.
    leaderboard["_complexity"] = leaderboard.family.map(lambda name: 0 if name in ("novelty", "transaction_only") else (1 if name == "transaction_novelty" else 1+len(SYSTEM_FAMILY_GROUPS.get(name, ("signal",)))))
    leaderboard = leaderboard.sort_values(
        ["mean_F1", "worst_F1", "FP", "_complexity", "threshold"], ascending=[False, False, True, True, False]
    ).drop(columns="_complexity").reset_index(drop=True)
    if leaderboard.TP.max() == 0:
        return {"family": "abstain", "threshold": 1.0, "reason": "No validation true positives"}, leaderboard
    return leaderboard.iloc[0].to_dict(), leaderboard
