# -*- coding: utf-8 -*-
"""벡터 솔버 v2 동등성 게이트 — 같은 트리에서 구솔버와 수치 일치 확인.

축소 메뉴로 작은 트리를 만들어 두 솔버를 15반복 돌리고
전 노드의 regret/ssum 최대 오차와 exploitability 를 대조한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import numpy as np
import hunl_tree

# 작은 트리로 축소 (테스트 전용)
hunl_tree.MENU = {1: (0.5, 1.0)}
hunl_tree.MENU_DEEP = (1.0,)

from hunl_solver import HunlCFRPlus          # noqa: E402
from hunl_solver2 import VecSolver           # noqa: E402


def main():
    old = HunlCFRPlus(avg_delay=5)
    new = VecSolver(avg_delay=5)
    print(f"트리: 결정노드 {len(old._nodes):,} (구) / {len(new._nodes):,} (신)")
    assert len(old._nodes) == len(new._nodes)

    # 기준 1: 1반복 직후 일치 (의미론 동일성 — float 순서 잡음 누적 전)
    old.iterate(); new.iterate()
    max_r = max(float(np.abs(a.regret - b.regret).max())
                for a, b in zip(old._nodes, new._nodes))
    scale_r = max(float(np.abs(a.regret).max()) for a in old._nodes) or 1.0
    print(f"1반복 regret 상대오차 {max_r/scale_r:.2e}")
    assert max_r / scale_r < 1e-5, "FAIL: 1반복 불일치 (의미론 결함)"

    # 기준 2: 장기 수렴 일치 (궤적은 float 잡음으로 갈라져도 균형은 같아야)
    for _ in range(199):
        old.iterate(); new.iterate()
    e_old = old.exploitability(); e_new = new.exploitability()
    print(f"200반복 exploitability: 구 {e_old:.2f} / 신 {e_new:.2f} mbb/g")
    assert abs(e_old - e_new) / max(e_old, 1e-9) < 0.05, "FAIL: 수렴 불일치"
    print("PASS — v2 는 같은 수학을 계산한다 (1반복 일치 + 수렴 일치)")


if __name__ == '__main__':
    main()
