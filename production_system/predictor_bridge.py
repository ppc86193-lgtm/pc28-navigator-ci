"""Predictor integration utilities bridging Navigator and predictor models.

This module is designed to capture the practical ideas from the dedicated
``pc28-predictor`` project and expose them inside the Navigator code base.
It focuses on lightweight analytics that do not require network calls unless
explicitly requested, making it safe to import in unit tests.

The bridge offers two primary capabilities:

* ``build_snapshot`` – accepts an in-memory draw history and returns
  probability bands plus qualitative alerts.
* ``generate_snapshot`` – optional helper that fetches the latest production
  draws (via BigQuery when credentials are available) before delegating to
  ``build_snapshot``.

The implementation intentionally keeps dependencies minimal so that it can
run in offline CI environments.  When BigQuery credentials or the SDK are
not available the helper simply returns an informative ``unavailable``
payload instead of raising errors.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, MutableMapping, Optional, Sequence, Tuple


@dataclass
class ProbabilityBand:
    """Aggregated probabilities within a rolling window."""

    label: str
    window: int
    sample_size: int
    big_probability: float
    small_probability: float
    odd_probability: float
    even_probability: float
    tail_distribution: Dict[str, float]
    dominant_tail: Optional[Dict[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the band into a JSON friendly dictionary."""

        payload = asdict(self)
        # Round floating point values for readability without losing accuracy.
        for key in (
            "big_probability",
            "small_probability",
            "odd_probability",
            "even_probability",
        ):
            payload[key] = round(payload[key], 4)

        payload["tail_distribution"] = {
            str(tail): round(prob, 4)
            for tail, prob in payload["tail_distribution"].items()
        }

        if payload["dominant_tail"]:
            payload["dominant_tail"] = {
                "tail": payload["dominant_tail"]["tail"],
                "probability": round(payload["dominant_tail"]["probability"], 4),
            }

        return payload


class PredictorBridge:
    """Bridge analytics that align Navigator with the predictor project."""

    def __init__(self, navigator_config: Optional[Any] = None) -> None:
        self._config = navigator_config

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def build_snapshot(self, draws: Sequence[int]) -> Dict[str, Any]:
        """Build a probability snapshot using an in-memory draw history."""

        if not draws:
            return {
                "status": "unavailable",
                "reason": "no draw history available",
            }

        windows = self._determine_windows(len(draws))
        bands: List[ProbabilityBand] = [
            self._compute_band(draws, window, label)
            for label, window in windows
        ]

        if not bands:
            return {
                "status": "unavailable",
                "reason": "insufficient data to build bands",
            }

        momentum = self._compute_momentum(bands)
        alerts = self._generate_alerts(bands, momentum)
        predictive_score = self._compute_predictive_score(bands)

        return {
            "status": "ok",
            "sample_size": len(draws),
            "bands": [band.to_dict() for band in bands],
            "momentum": momentum,
            "predictive_score": round(predictive_score, 4),
            "alerts": alerts,
            "metadata": {
                "windows": [band.window for band in bands],
            },
        }

    async def generate_snapshot(self, limit: int = 120) -> Dict[str, Any]:
        """Fetch recent draws (when possible) and build a snapshot.

        The function intentionally swallows most BigQuery related errors so
        that a missing credential does not stop emergency diagnostics.
        """

        draws = await self._fetch_recent_draws(limit=limit)
        if not draws:
            return {
                "status": "unavailable",
                "reason": "unable to fetch production draw history",
            }

        return self.build_snapshot(draws)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _determine_windows(self, sample_size: int) -> List[Tuple[str, int]]:
        """Pick representative rolling windows while avoiding duplicates."""

        if sample_size <= 0:
            return []

        candidates = [10, 30, 60, 120]
        windows: List[Tuple[str, int]] = []
        seen: set[int] = set()

        for candidate in candidates:
            actual = min(sample_size, candidate)
            if actual < 5 or actual in seen:
                continue
            label = f"last_{actual}"
            windows.append((label, actual))
            seen.add(actual)

        if sample_size not in seen:
            windows.append(("full_history", sample_size))

        # Ensure the most recent (smallest window) comes first.
        windows.sort(key=lambda item: item[1])
        return windows

    def _compute_band(self, draws: Sequence[int], window: int, label: str) -> ProbabilityBand:
        """Compute probability statistics for the specified window."""

        window_data = list(draws[-window:]) if window else list(draws)
        sample_size = len(window_data)
        if sample_size == 0:
            # Fallback: represent an empty band; callers should filter it out.
            return ProbabilityBand(
                label=label,
                window=0,
                sample_size=0,
                big_probability=0.0,
                small_probability=0.0,
                odd_probability=0.0,
                even_probability=0.0,
                tail_distribution={},
                dominant_tail=None,
            )

        big = sum(1 for value in window_data if value >= 14)
        odd = sum(1 for value in window_data if value % 2 == 1)
        tail_counter = Counter(value % 10 for value in window_data)

        tail_distribution = {
            str(tail): count / sample_size for tail, count in sorted(tail_counter.items())
        }

        dominant_tail = None
        if tail_counter:
            tail_value, tail_count = max(tail_counter.items(), key=lambda item: item[1])
            dominant_tail = {
                "tail": str(tail_value),
                "probability": tail_count / sample_size,
            }

        return ProbabilityBand(
            label=label,
            window=sample_size,
            sample_size=sample_size,
            big_probability=big / sample_size,
            small_probability=(sample_size - big) / sample_size,
            odd_probability=odd / sample_size,
            even_probability=(sample_size - odd) / sample_size,
            tail_distribution=tail_distribution,
            dominant_tail=dominant_tail,
        )

    def _compute_momentum(self, bands: Sequence[ProbabilityBand]) -> Dict[str, Any]:
        """Compare the smallest window against the full history."""

        if not bands:
            return {
                "latest_band": None,
                "reference_band": None,
                "big_small_shift": 0.0,
                "odd_even_shift": 0.0,
            }

        latest = bands[0]
        reference = bands[-1]

        return {
            "latest_band": latest.label,
            "reference_band": reference.label,
            "big_small_shift": round(latest.big_probability - reference.big_probability, 4),
            "odd_even_shift": round(latest.odd_probability - reference.odd_probability, 4),
        }

    def _generate_alerts(
        self, bands: Sequence[ProbabilityBand], momentum: MutableMapping[str, Any]
    ) -> List[str]:
        """Generate qualitative alerts based on probability extremes."""

        alerts: List[str] = []
        thresholds = {
            "bias": 0.68,
            "tail": 0.32,
            "momentum": 0.15,
        }

        for band in bands:
            if band.big_probability > thresholds["bias"]:
                alerts.append(
                    f"{band.label}: 大号概率达到 {band.big_probability:.0%}，关注大势。"
                )
            if band.small_probability > thresholds["bias"]:
                alerts.append(
                    f"{band.label}: 小号概率达到 {band.small_probability:.0%}，关注小势。"
                )
            if band.odd_probability > thresholds["bias"]:
                alerts.append(
                    f"{band.label}: 单数概率达到 {band.odd_probability:.0%}，偏向单数。"
                )
            if band.even_probability > thresholds["bias"]:
                alerts.append(
                    f"{band.label}: 双数概率达到 {band.even_probability:.0%}，偏向双数。"
                )

            if band.dominant_tail and band.dominant_tail["probability"] > thresholds["tail"]:
                alerts.append(
                    f"{band.label}: 尾数{band.dominant_tail['tail']} 占比 {band.dominant_tail['probability']:.0%}，出现聚集。"
                )

        big_shift = abs(momentum.get("big_small_shift", 0.0) or 0.0)
        odd_shift = abs(momentum.get("odd_even_shift", 0.0) or 0.0)
        if big_shift > thresholds["momentum"]:
            alerts.append(
                f"大小动量偏移 {big_shift:.0%}，短期走势与长期统计差异明显。"
            )
        if odd_shift > thresholds["momentum"]:
            alerts.append(
                f"单双动量偏移 {odd_shift:.0%}，短期单双走势发生变化。"
            )

        return alerts

    def _compute_predictive_score(self, bands: Sequence[ProbabilityBand]) -> float:
        """Aggregate band biases into a 0-1 predictive confidence score."""

        if not bands:
            return 0.0

        biases: List[float] = []
        for band in bands:
            big_bias = abs(band.big_probability - 0.5)
            odd_bias = abs(band.odd_probability - 0.5)
            biases.append(max(big_bias, odd_bias) * 2)  # normalize to [0, 1]

        return max(0.0, min(1.0, sum(biases) / len(biases)))

    async def _fetch_recent_draws(self, limit: int) -> List[int]:
        """Fetch recent draw sums from BigQuery if possible."""

        project = getattr(self._config, "gcp_project", None)
        dataset = getattr(self._config, "bigquery_dataset", None)
        if not project or not dataset:
            return []

        try:
            from google.cloud import bigquery  # type: ignore
        except Exception:
            return []

        def _query() -> List[int]:
            client = bigquery.Client(project=project)
            query = f"""
                SELECT (a + b + c) AS total
                FROM `{project}.{dataset}.draws_clean`
                ORDER BY timestamp DESC
                LIMIT {int(limit)}
            """
            result = client.query(query).result()
            return [int(row.total) for row in result if row.total is not None]

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, _query)
        except Exception:
            return []

