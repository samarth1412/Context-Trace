from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from typing import Any, Iterable


_OPERATORS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


@dataclass(frozen=True)
class Threshold:
    metric: str
    operator: str
    value: float

    def evaluate(self, metrics: dict[str, Any]) -> bool:
        if self.metric not in metrics:
            raise ValueError("Metric '%s' is not available for threshold evaluation." % self.metric)
        return bool(_OPERATORS[self.operator](float(metrics[self.metric]), self.value))

    def describe(self, metrics: dict[str, Any]) -> str:
        actual = metrics.get(self.metric)
        return "%s=%s violates %s%s" % (self.metric, actual, self.operator, self.value)


def parse_threshold(value: str) -> Threshold:
    match = re.fullmatch(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<)\s*([0-9]*\.?[0-9]+)\s*", value)
    if not match:
        raise ValueError("Threshold must look like failure_rate>0.25 or citation_support<0.80.")
    metric, op, raw_value = match.groups()
    return Threshold(metric=metric, operator=op, value=float(raw_value))


def parse_thresholds(values: Iterable[str]) -> list[Threshold]:
    return [parse_threshold(value) for value in values]


def threshold_failures(metrics: dict[str, Any], thresholds: Iterable[Threshold]) -> list[str]:
    failures = []
    for threshold in thresholds:
        if threshold.evaluate(metrics):
            failures.append(threshold.describe(metrics))
    return failures
