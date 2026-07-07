# -*- coding: utf-8 -*-
"""불변식 검증 (레거시 test_invariants 관례 이식).

1. PROP + VIC off (clean) → Q(CHECK) == 0.000 정확히 (전 셀) — ZCA 구조 사실
2. PROP + VIC fixed-5     → Q(CHECK) ≠ 0 셀 존재 — 고정점 해제
3. PURE                   → Q(CHECK) ≠ 0 셀 존재 — 말단보상 수령

usage: python tests/test_invariants.py   (~1분, 30k 에피소드 × 3)
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actions import Action
from cards import make_cards
from game import play_train_episode
from personas import PERSONA_POLICIES
from qtable import QTable
from train import temperature_at

EPISODES = 30_000


def run(credit, vic, amount):
    random.seed(42)
    cards = make_cards('legacy8')
    qt = QTable(cards.n_states)
    policy = PERSONA_POLICIES['tag']
    for i in range(1, EPISODES + 1):
        play_train_episode(qt, cards, policy, temperature_at(i, EPISODES),
                           credit, vic, amount, learner_id=i % 2)
    checks = [qt.q[r][p][s][pa][Action.CHECK.value]
              for r in range(4) for p in range(2)
              for s in range(cards.n_states) for pa in range(4)]
    return checks


def main():
    c1 = run('prop', 'off', 0)
    assert all(v == 0.0 for v in c1), \
        f"FAIL: prop+off 인데 Q(CHECK)!=0 셀 {sum(1 for v in c1 if v != 0)}개"
    print(f"PASS 1: prop+off+clean -> Q(CHECK)==0.000 전 셀 ({len(c1)}셀)")

    c2 = run('prop', 'fixed', 5)
    nz = sum(1 for v in c2 if v != 0.0)
    assert nz > 0, "FAIL: fixed-5 인데 Q(CHECK) 전부 0"
    print(f"PASS 2: prop+fixed5 -> Q(CHECK)!=0 셀 {nz}개 (고정점 해제)")

    c3 = run('pure', 'off', 0)
    nz = sum(1 for v in c3 if v != 0.0)
    assert nz > 0, "FAIL: pure 인데 Q(CHECK) 전부 0"
    print(f"PASS 3: pure -> Q(CHECK)!=0 셀 {nz}개 (말단보상 수령)")
    print("ALL PASS")


if __name__ == '__main__':
    main()
