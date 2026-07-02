# -*- coding: utf-8 -*-
"""행동 프로파일 (E4b) — off vs pot-VIC 정책이 vs Random에서 '어디서' 이기고 지는가.
행동 빈도(라운드별), 승리/패배 핸드의 payoff 분포(팟 크기 비대칭)를 측정해
"win% 4%p vs mbb +1700" 괴리를 해명한다.
usage: python _profile_behavior.py RUN_DIR [n_games=20000]
"""
import os
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import train_eval_mc_prop_softmax_2000k as base
from abstraction import (Round, PrevAction, pk_to_round, pk_to_state,
                         pk_to_position, legal_our_actions, execute_action)
from qlearning import QLearning

RESULTS = Path(__file__).resolve().parent.parent / "results"


def main():
    run = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    ql = QLearning.load(str(RESULTS / run / "eval_results.pkl"))
    random.seed(1000)
    freq = Counter()          # (round, action) 빈도
    wins, losses = [], []     # payoff 분포
    for i in range(n):
        pk_state = base._make_game()
        lid = i % 2
        pos = pk_to_position(lid)
        prev: dict = {}
        while pk_state.status:
            if pk_state.can_deal_hole():
                pk_state.deal_hole()
            elif pk_state.can_deal_board():
                pk_state.deal_board()
            elif pk_state.actor_index is not None:
                if pk_state.actor_index == lid:
                    r = pk_to_round(pk_state)
                    s = pk_to_state(pk_state, lid)
                    pa = prev.get(r, PrevAction.NONE)
                    legal = legal_our_actions(pk_state)
                    a = ql.best_action(r, pos, s, pa, legal)
                    freq[(r.name, a.name)] += 1
                    execute_action(pk_state, a)
                else:
                    base._step_opponent(pk_state, 1 - lid, 'random', prev)
            else:
                break
        p = float(pk_state.stacks[lid] - base.STARTING_STACK)
        (wins if p > 0 else losses).append(p)

    total = sum(freq.values())
    print(f"=== {run} | {n} games vs Random ===")
    print(f"win {len(wins)/n*100:.1f}% | mbb/g {statistics.mean(wins+losses)*500:+.1f}")
    print(f"승리핸드: n={len(wins)} 평균 +{statistics.mean(wins):.1f}칩 (중앙값 {statistics.median(wins):.0f})")
    print(f"패배핸드: n={len(losses)} 평균 {statistics.mean(losses):.1f}칩 (중앙값 {statistics.median(losses):.0f})")
    print("행동 빈도(라운드별 상위):")
    for rd in ['PREFLOP', 'FLOP', 'TURN', 'RIVER']:
        row = [(a, c) for (r, a), c in freq.items() if r == rd]
        row.sort(key=lambda x: -x[1])
        tot = sum(c for _, c in row) or 1
        top = '  '.join(f"{a}:{c/tot*100:.0f}%" for a, c in row[:4])
        print(f"  {rd:8} {top}")


if __name__ == '__main__':
    main()
