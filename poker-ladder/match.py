# -*- coding: utf-8 -*-
"""에이전트 상호대국(head-to-head) — 두 학습 Q-테이블을 직접 맞붙인다.

각 에이전트는 자기 런의 카드축(meta['card'])·행동축(meta['actions'])으로 greedy 플레이.
좌석은 게임마다 교대(i%2 — 포지션 편향 상쇄). PrevAction 은 좌석별 관점으로 추적.

usage: python match.py RUN_A RUN_B N_GAMES [seed]
  보고: A 관점 mbb/g ± SE (BB=2 기준 ×500), 승률.
"""
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from actions import legal_actions, execute_action
from cards import make_cards
from defs import PrevAction, classify_opp_action, pk_to_position, pk_to_round, pot_size
from game import BIG_BLIND, STARTING_STACK, make_game
from qtable import QTable


def load_agent(run_dir: str):
    qt = QTable.load(Path(run_dir) / 'qtable.pkl')
    return (qt, make_cards(qt.meta['card']), qt.meta.get('actions', 'A8'))


def play_h2h_episode(agents: dict, a_seat: int) -> float:
    """agents: {seat: (qt, cards, actions_version)}. 반환 = A(=a_seat) payoff(칩)."""
    pk = make_game()
    prev_view = {0: {}, 1: {}}          # seat → {Round: 상대의 직전 행동}

    while pk.status:
        if pk.can_deal_hole():
            pk.deal_hole()
        elif pk.can_deal_board():
            pk.deal_board()
        elif pk.actor_index is not None:
            p = pk.actor_index
            qt, cards, ver = agents[p]
            r = pk_to_round(pk)
            pot_before = pot_size(pk)
            cca_before = pk.checking_or_calling_amount
            stack_before = pk.stacks[p]
            max_to = pk.max_completion_betting_or_raising_to_amount
            s = cards.state_of(pk, p)
            pa = prev_view[p].get(r, PrevAction.NONE)
            a = qt.best_action(r, pk_to_position(p), s, pa,
                               legal_actions(pk, ver))
            execute_action(pk, a)
            # 이 행동을 상대 관점 PrevAction 으로 분류 (동일 규칙)
            stack_after = pk.stacks[p]
            invest = stack_before - stack_after
            was_allin = (stack_after == 0 and invest > cca_before + 1e-9) \
                        or (max_to == stack_before
                            and invest > cca_before + 1e-9)
            pa2 = classify_opp_action(stack_before, stack_after, cca_before,
                                      pot_before, was_allin=was_allin)
            if pa2 is not None:
                prev_view[1 - p][r] = pa2
        else:
            break
    return float(pk.stacks[a_seat] - STARTING_STACK)


def main():
    run_a, run_b = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
    A = load_agent(run_a)
    B = load_agent(run_b)
    la = f"{Path(run_a).parent.name}/{Path(run_a).name}"
    lb = f"{Path(run_b).parent.name}/{Path(run_b).name}"
    random.seed(seed)

    pays = []
    for i in range(n):
        a_seat = i % 2
        agents = {a_seat: A, 1 - a_seat: B}
        pays.append(play_h2h_episode(agents, a_seat))
    mean = sum(pays) / n
    sd = statistics.stdev(pays)
    scale = 1000.0 / BIG_BLIND
    win = sum(1 for p in pays if p > 0) / n
    print(f"==> H2H {la} vs {lb} n={n} | A {mean*scale:+.1f}±{sd/math.sqrt(n)*scale:.1f} mbb/g "
          f"| win {win*100:.1f}%", flush=True)


if __name__ == '__main__':
    main()
