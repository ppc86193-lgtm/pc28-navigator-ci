from __future__ import annotations

from typing import Any, Dict, List


class ProductionTurningPointModule:
    async def analyze(self, data: List[float]) -> Dict[str, Any]:
        n = len(data)
        if n == 0:
            return {
                "algorithm": "ruptures-Pelt-RBF",
                "change_points": [],
                "big_small_changes": [],
                "odd_even_changes": [],
            }

        # Simple change point detection: boundary where value changes
        change_points: List[int] = []
        for i in range(1, n):
            if data[i] != data[i - 1]:
                change_points.append(i)

        # Build example fields for the first change point if any
        big_small_changes: List[Dict[str, Any]] = []
        odd_even_changes: List[Dict[str, Any]] = []
        if change_points:
            pos = change_points[0]

            # Determine segment stats for the segment after the change
            # Find next change or end
            next_pos = next((cp for cp in change_points[1:] if cp > pos), n)
            segment = data[pos:next_pos]
            seg_len = len(segment)
            seg_avg = sum(segment) / seg_len if seg_len else 0.0

            # Big/Small type heuristic: threshold at 14
            bs_type = "大" if seg_avg >= 14 else "小"
            # Confidence heuristic within [0,1]
            delta = abs(data[pos] - data[pos - 1])
            confidence = max(0.0, min(1.0, delta / (max(abs(x) for x in data) or 1)))
            big_small_changes.append(
                {
                    "position": pos,
                    "type": bs_type,
                    "confidence": confidence,
                    "segment_avg": seg_avg,
                    "segment_length": seg_len,
                }
            )

            # Odd/Even change info for the same point
            val = int(round(data[pos]))
            oe_type = "单" if (val % 2 == 1) else "双"
            odd_even_changes.append(
                {
                    "position": pos,
                    "type": oe_type,
                    "value": val,
                    "confidence": confidence,
                }
            )

        return {
            "algorithm": "ruptures-Pelt-RBF",
            "change_points": change_points,
            "big_small_changes": big_small_changes,
            "odd_even_changes": odd_even_changes,
        }


class ProductionFrequencyModule:
    async def analyze(self, data: List[int]) -> Dict[str, Any]:
        # Windows per test description
        human_window = 5
        ai_window = 50

        def stats(window_size: int) -> Dict[str, float]:
            window = data[-window_size:] if len(data) >= window_size else data
            if not window:
                return {
                    "big_ratio": 0.0,
                    "small_ratio": 0.0,
                    "odd_ratio": 0.0,
                    "even_ratio": 0.0,
                }
            big = sum(1 for x in window if x >= 14)
            small = len(window) - big
            odd = sum(1 for x in window if x % 2 == 1)
            even = len(window) - odd
            total = float(len(window))
            return {
                "big_ratio": big / total,
                "small_ratio": small / total,
                "odd_ratio": odd / total,
                "even_ratio": even / total,
            }

        h = stats(human_window)
        a = stats(ai_window)

        # Gap as absolute difference between ratios
        big_small_gap = abs(h["big_ratio"] - a["big_ratio"]) + abs(h["small_ratio"] - a["small_ratio"])  # type: ignore[index]
        odd_even_gap = abs(h["odd_ratio"] - a["odd_ratio"]) + abs(h["even_ratio"] - a["even_ratio"])  # type: ignore[index]

        trap_analysis = {
            "overall_strength": (
                0
                if (big_small_gap == 0 and odd_even_gap == 0)
                else max(big_small_gap, odd_even_gap)
            ),
            "big_small_contribution": 0 if big_small_gap == 0 else big_small_gap,
            "odd_even_contribution": 0 if odd_even_gap == 0 else odd_even_gap,
        }

        return {
            "trap_analysis": trap_analysis,
        }
