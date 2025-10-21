#!/usr/bin/env python3
"""
Frequency 零 gap 贡献比分支：big_small_contribution/odd_even_contribution 为 0
"""

import pytest

from production_system.modules import ProductionFrequencyModule


@pytest.mark.asyncio
async def test_frequency_zero_gap_contributions():
    fm = ProductionFrequencyModule()
    # 构造人脑窗口=5、AI 窗口=50 两者大小与单双比例完全一致
    # 使用 60 条稳定数据：全部为 14（大、偶），则两个窗口统计相同 → gap=0
    data = [14] * 60
    res = await fm.analyze(data)
    ta = res["trap_analysis"]
    assert ta["overall_strength"] == 0
    assert ta["big_small_contribution"] == 0
    assert ta["odd_even_contribution"] == 0

