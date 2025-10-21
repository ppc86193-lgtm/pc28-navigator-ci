#!/usr/bin/env python3
"""
TurningPoint 专业路径字段级断言：segment_length/position/type/confidence
"""

import pytest

try:
    import ruptures as _rpt  # noqa: F401
    HAS_RUPTURES = True
except Exception:
    HAS_RUPTURES = False

from production_system.modules import ProductionTurningPointModule


@pytest.mark.skipif(not HAS_RUPTURES, reason="ruptures not installed")
@pytest.mark.asyncio
async def test_turning_point_fields_and_change_points():
    tp = ProductionTurningPointModule()
    data = [1] * 20 + [25] * 20 + [5] * 20
    res = await tp.analyze(data)
    assert res["algorithm"] == "ruptures-Pelt-RBF"

    # change_points 至少包含 1 个分割点（最后一项是 n，已在实现中去掉）
    cps = res.get("change_points", [])
    assert isinstance(cps, list)
    assert len(cps) >= 1

    # 大小变点字段
    bsc = res.get("big_small_changes", [])
    if bsc:
        item = bsc[0]
        assert set(["position", "type", "confidence", "segment_avg", "segment_length"]) - item.keys() == set()
        assert isinstance(item["position"], int) and item["position"] > 0
        assert item["type"] in {"大", "小"}
        assert 0 <= item["confidence"] <= 1
        assert item["segment_length"] > 0

    # 单双变点字段
    oec = res.get("odd_even_changes", [])
    if oec:
        it = oec[0]
        assert set(["position", "type", "value", "confidence"]) - it.keys() == set()
        assert isinstance(it["position"], int) and it["position"] > 0
        assert it["type"] in {"单", "双"}
        assert 0 <= it["confidence"] <= 1
