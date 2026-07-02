# -*- coding: utf-8 -*-
"""홀드아웃 다중 OOD 평가 (E2) — 학습된 pkl을 미학습 페르소나 상대로 100k×N 평가.

eval_persona_100k.py와 동일 프로토콜(rep마다 random.seed(BASE_SEED+k), learner_id=i%2,
raw greedy=ql.best_action)이되 상대만 rulebased_personas 정책으로 교체.
α는 사전 고정(여기서 튜닝 금지 — 순환성 방지가 목적).

argv: run_dir(results/ 기준) persona [persona ...]
env : N_GAMES(100000) N_REPEAT(5) BASE_SEED(1000)
출력: "==> {run} vs{P} mean {m} (회차SD {sd})" — 집계 파서와 호환.
"""
import os
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_eval_mc_prop_softmax_2000k as base
import rulebased_personas as personas
from abstraction import (Round, PrevAction, pk_to_round, pk_to_state,
                         pk_to_position, legal_our_actions, execute_action)
from qlearning import QLearning

N_GAMES   = int(os.environ.get("N_GAMES", "100000"))
N_REPEAT  = int(os.environ.get("N_REPEAT", "5"))
BASE_SEED = int(os.environ.get("BASE_SEED", "1000"))
RESULTS   = Path(__file__).resolve().parent.parent / "results"
STARTING_STACK = base.STARTING_STACK


def play_episode(ql: QLearning, policy: dict, learner_id: int) -> float:
    pk_state = base._make_game()
    pos    = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round: dict = {}
    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()
        elif pk_state.can_deal_board():
            pk_state.deal_board()
        elif pk_state.actor_index is not None:
            if pk_state.actor_index == learner_id:
                r  = pk_to_round(pk_state)
                s  = pk_to_state(pk_state, learner_id)
                pa = prev_action_by_round.get(r, PrevAction.NONE)
                legal = legal_our_actions(pk_state)
                a = ql.best_action(r, pos, s, pa, legal)
                execute_action(pk_state, a)
            else:
                personas.step_persona_opponent(
                    pk_state, opp_id, policy, prev_action_by_round)
        else:
            break
    return float(pk_state.stacks[learner_id] - STARTING_STACK)


def main():
    run = sys.argv[1]
    names = sys.argv[2:] or ['lag', 'man', 'sta', 'nit']
    pkl = RESULTS / run / "eval_results.pkl"
    ql = QLearning.load(str(pkl))
    for name in names:
        policy = personas.PERSONA_POLICIES[name]
        means = []
        for k in range(N_REPEAT):
            random.seed(BASE_SEED + k)
            t0 = time.perf_counter()
            payoffs = [play_episode(ql, policy, i % 2) for i in range(N_GAMES)]
            mbb = statistics.mean(payoffs) * 500          # mbb/g = payoff×500
            means.append(mbb)
            print(f"  [{run}] vs{name.upper()} rep{k+1}/{N_REPEAT} "
                  f"{mbb:>+9.1f} | {time.perf_counter()-t0:5.1f}s", flush=True)
        mu = statistics.mean(means)
        sd = statistics.stdev(means) if N_REPEAT > 1 else 0.0
        print(f"  ==> {run} vs{name.upper()} mean {mu:>+9.1f} (회차SD {sd:6.1f})", flush=True)


if __name__ == '__main__':
    main()
