"""Explicit dataset semantics and a small, predeclared experimental protocol."""

from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    seconds_per_step: int
    input_dir: str
    has_currency: bool


DATASETS = {
    "paysim": DatasetSpec("paysim", 3600, "data/processed/paysim", False),
    "ibm_aml": DatasetSpec("ibm_aml", 1, "data/processed/ibm_aml", True),
}


@dataclass(frozen=True)
class AnalysisConfig:
    """Freeze these choices before inspecting the reused internal test period.

    Walk-forward validation: train <=40%, validate (40,50]; train <=50%,
    validate (50,65]; train <=65%, validate (65,80]. Refit through 80% only
    after selecting family/threshold. Timestamp ties stay together.
    """

    windows_hours: tuple[int, ...] = (24, 168)
    fold_fractions: tuple[float, ...] = (0.4, 0.5, 0.65, 0.8)
    score_thresholds: tuple[float, ...] = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.99)
    tree_depth: int = 5
    minimum_leaf_rows: int = 50
    seed: int = 2026
    example_limit: int = 5
    driver_memory: str = "6g"
    parallelism: int = 2

    def __post_init__(self):
        if (not self.windows_hours or tuple(sorted(set(self.windows_hours))) != self.windows_hours
                or any(type(h) is not int or h <= 0 for h in self.windows_hours)):
            raise ValueError("windows_hours must be sorted, unique positive integers")
        if (len(self.fold_fractions) < 3 or tuple(sorted(set(self.fold_fractions))) != self.fold_fractions
                or any(not math.isfinite(q) or not 0 < q < 1 for q in self.fold_fractions)):
            raise ValueError("At least three increasing fractions strictly inside (0,1) required")
        if (not self.score_thresholds or tuple(sorted(set(self.score_thresholds))) != self.score_thresholds
                or any(not math.isfinite(t) or not 0 < t <= 1 for t in self.score_thresholds)):
            raise ValueError("score_thresholds must increase inside (0,1]")
        if (type(self.tree_depth) is not int or not 1 <= self.tree_depth <= 8
                or type(self.minimum_leaf_rows) is not int or self.minimum_leaf_rows < 1
                or type(self.parallelism) is not int or not 1 <= self.parallelism <= 2
                or type(self.example_limit) is not int or self.example_limit < 1):
            raise ValueError("Invalid tree, resource or example limits")

    def as_dict(self) -> dict:
        return asdict(self)
