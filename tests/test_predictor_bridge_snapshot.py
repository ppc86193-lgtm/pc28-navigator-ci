#!/usr/bin/env python3
"""Unit tests for the predictor bridge integration layer."""

from production_system import PredictorBridge


def test_predictor_bridge_snapshot_with_bias():
    bridge = PredictorBridge()

    # 构造样本：近期明显偏向大/双，尾数聚集在 8/9。
    draws = (
        [16, 17, 18, 19, 20, 21] * 6
        + [14, 15, 16, 17, 18] * 3
        + [5, 6, 7, 8, 9]
    )

    snapshot = bridge.build_snapshot(draws)

    assert snapshot["status"] == "ok"
    assert snapshot["sample_size"] == len(draws)

    bands = snapshot["bands"]
    assert len(bands) >= 2

    required_keys = {
        "label",
        "window",
        "sample_size",
        "big_probability",
        "small_probability",
        "odd_probability",
        "even_probability",
        "tail_distribution",
        "dominant_tail",
    }
    assert required_keys.issubset(bands[0].keys())

    assert 0.0 <= snapshot["predictive_score"] <= 1.0

    momentum = snapshot["momentum"]
    assert momentum["latest_band"] == bands[0]["label"]
    assert momentum["reference_band"] == bands[-1]["label"]

    # 构造的数据应触发至少一条提示
    assert snapshot["alerts"]

