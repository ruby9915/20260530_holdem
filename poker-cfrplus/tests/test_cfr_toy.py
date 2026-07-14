# -*- coding: utf-8 -*-
"""CFR+ 솔버 정답 대조 (검증 체인 1·2단계).

1. Kuhn: 평균 전략 게임가치 → 해석해 −1/18 ≈ −0.05556 (정답 대조)
   + exploitability → 0 수렴
2. Leduc: exploitability 단조 하강 → 문턱 이하 (문헌엔 P0 가치 ≈ −0.08대)

usage: python tests/test_cfr_toy.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from cfr import CFRPlus
from games_toy import Kuhn, Leduc


def run(game, iters, checkpoints, label):
    s = CFRPlus(game, avg_delay=max(1, iters // 20))
    t0 = time.time()
    for t in range(1, iters + 1):
        s.iterate()
        if t in checkpoints:
            ex = s.exploitability()
            print(f"  [{label}] iter {t:>6} | value(P0) {s.game_value():+.5f} "
                  f"| exploitability {ex:.6f} | {time.time()-t0:.0f}s", flush=True)
    return s


def main():
    print("=== 1. Kuhn poker (해석해 대조) ===")
    s = run(Kuhn(), 50000, {5000, 20000, 50000}, 'kuhn')  # 감쇠 ~O(1/√T), 이론 보장 내
    v, ex = s.game_value(), s.exploitability()
    assert abs(v - (-1 / 18)) < 0.003, f"FAIL: Kuhn 가치 {v:.5f} ≠ −1/18"
    assert ex < 1e-3, f"FAIL: Kuhn exploitability {ex:.5f}"
    print(f"PASS: value {v:+.5f} ≈ −1/18({-1/18:+.5f}), exploitability {ex:.2e}\n")

    print("=== 2. Leduc hold'em (수렴 벤치마크) ===")
    s = run(Leduc(), 50000, {10000, 30000, 50000}, 'leduc')
    ex = s.exploitability()
    assert ex < 0.01, f"FAIL: Leduc exploitability {ex:.5f} ≥ 0.01"
    print(f"PASS: value(P0) {s.game_value():+.5f}, exploitability {ex:.5f} < 0.01")
    print("\nALL PASS — CFR+ 솔버 정답 대조 통과")


if __name__ == '__main__':
    main()
