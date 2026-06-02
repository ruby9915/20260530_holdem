"""
train_softmax_8000k_mixed.py
─────────────────────────────────────────────────────────────────────
19번 알고리즘(Prop MC + Softmax τ:10→0.5 + PrevAction + CHECK=1chip)을
학습 상대를 에피소드마다 Random/RuleBased 번갈아 사용하는 'mixed' 방식으로
8,000,000 에피소드 학습한다.

목적:
  - Random: 넓은 커버리지 (얕은 셀 포화)
  - RuleBased: 깊은 셀(턴·리버×레이즈직면) 도달 보강
  - 번갈아 사용 → 신호 충돌 타협안, 상대 특화 과적합 방지

변경 사항 (train_softmax_2000k_opp.py 대비):
  TOTAL_EPISODES = 8,000,000 (4배)
  EVAL_EVERY     = 50,000    (160 체크포인트, 추세 추적용)
  EVAL_GAMES     = 200       (빠른 추세 확인; 최종 정밀 평가는 별도)
  opponent       = 'mixed'   (짝수 ep=random, 홀수 ep=rulebased)
"""
import csv
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import train_eval_mc_prop_softmax_2000k as base
from abstraction import (
    Round, State, Action, PrevAction,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action, classify_opp_action,
)
from qlearning import QLearning

STARTING_STACK       = base.STARTING_STACK
BIG_BLIND            = base.BIG_BLIND
CHECK_VIRTUAL_INVEST = base.CHECK_VIRTUAL_INVEST
ALPHA                = base.ALPHA
GAMMA                = base.GAMMA

TOTAL_EPISODES = 8_000_000
EVAL_EVERY     = 50_000    # 160 체크포인트
EVAL_GAMES     = 200       # 빠른 추세 확인

temperature_at = base.temperature_at
_make_game     = base._make_game
_step_opponent = base._step_opponent
evaluate       = base.evaluate
_fmt_time      = base._fmt_time
EvalResult     = base.EvalResult


def play_train_episode(ql: QLearning, temperature: float,
                       opponent: str, learner_id: int = 0) -> float:
    pk_state = _make_game()
    trace: list[tuple[Round, State, PrevAction, Action, float]] = []
    pos    = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round: dict = {}

    while not pk_state.status:
        actor = pk_state.actor_index
        if actor == learner_id:
            r     = pk_to_round(pk_state)
            s     = pk_to_state(pk_state, learner_id)
            pa    = prev_action_by_round.get(r, PrevAction.NONE)
            legal = legal_our_actions(pk_state)

            stack_before = pk_state.stacks[learner_id]
            a = ql.softmax_action(r, pos, s, pa, legal, temperature)
            execute_action(pk_state, a)
            stack_after  = pk_state.stacks[learner_id]
            invest       = float(stack_before - stack_after)
            invest_for_trace = (
                float(CHECK_VIRTUAL_INVEST)
                if (a == Action.CHECK and invest == 0) else invest
            )
            trace.append((r, s, pa, a, invest_for_trace))
        else:
            _step_opponent(pk_state, opp_id, opponent, prev_action_by_round)
        if pk_state.status:
            break

    payoff       = float(pk_state.stacks[learner_id] - STARTING_STACK)
    total_invest = sum(inv for (_, _, _, _, inv) in trace)
    if total_invest > 0:
        for (r, s, pa, a, inv) in trace:
            ql.update_mc(r, pos, s, pa, a, (inv / total_invest) * payoff)
    else:
        n = len(trace)
        if n > 0:
            R = payoff / n
            for (r, s, pa, a, _inv) in trace:
                ql.update_mc(r, pos, s, pa, a, R)
    return payoff


def main(out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "eval_results.csv"

    ql = QLearning(alpha=ALPHA, gamma=GAMMA, ucb_c=50.0)
    results = []

    hdr = (f"{'episode':>9} {'pct':>5} {'temp':>5} |"
           f" {'rand%':>6} {'mbb/g_r':>10} |"
           f" {'rule%':>6} {'mbb/g_rl':>10} |"
           f" {'ep/s':>6} {'elapsed':>9} {'ETA':>9}")
    sep = "-" * len(hdr)
    print(sep, flush=True)
    print(f"  TRAIN vs [MIXED: Random↔RuleBased]  |  Prop MC Softmax + PrevAction + CHECK=1chip  |  8,000,000 ep", flush=True)
    print(f"  out: {out}", flush=True)
    print(sep, flush=True)
    print(hdr, flush=True)
    print(sep, flush=True)

    t_start = time.perf_counter()
    t_last  = t_start
    ep_last = 0

    wr, mr, sr, wrb, mrb, srb = evaluate(ql, EVAL_GAMES)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    print(f"{0:>9} {'0.0%':>5} {base.TEMP_START:>5.1f} |"
          f" {wr*100:>5.1f}% {mr:>+9.0f} |"
          f" {wrb*100:>5.1f}% {mrb:>+9.0f} |"
          f" {'-':>6} {_fmt_time(time.perf_counter()-t_start):>9} {'-':>9}", flush=True)

    ep = 0
    while ep < TOTAL_EPISODES:
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)
        for i in range(ep + 1, next_eval + 1):
            temp    = temperature_at(i)
            # 짝수 에피소드 → random, 홀수 → rulebased (1:1 번갈아)
            eff_opp = 'random' if i % 2 == 0 else 'rulebased'
            play_train_episode(ql, temp, eff_opp, learner_id=i % 2)
        ep = next_eval

        t_now    = time.perf_counter()
        interval = t_now - t_last
        speed    = (ep - ep_last) / interval if interval > 0 else 0.0
        eta      = (TOTAL_EPISODES - ep) / speed if speed > 0 else 0.0
        t_last, ep_last = t_now, ep

        wr, mr, sr, wrb, mrb, srb = evaluate(ql, EVAL_GAMES)
        results.append(EvalResult(ep, wr, mr, sr, wrb, mrb, srb))
        print(f"{ep:>9} {ep/TOTAL_EPISODES*100:>4.1f}% {temperature_at(ep):>5.2f} |"
              f" {wr*100:>5.1f}% {mr:>+9.0f} |"
              f" {wrb*100:>5.1f}% {mrb:>+9.0f} |"
              f" {speed:>6.0f} {_fmt_time(t_now-t_start):>9} {_fmt_time(eta):>9}", flush=True)

    print(sep, flush=True)
    total = time.perf_counter() - t_start
    print(f"  Total: {_fmt_time(total)}  |  Avg: {TOTAL_EPISODES/total:.0f} ep/s", flush=True)
    print(sep, flush=True)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['episode',
                    'win%_vs_random', 'mbb/g_vs_random', 'se_vs_random',
                    'win%_vs_rulebased', 'mbb/g_vs_rulebased', 'se_vs_rulebased'])
        for r in results:
            w.writerow([r.episode,
                        f"{r.win_vs_random:.4f}", f"{r.mbb_vs_random:.2f}", f"{r.se_vs_random:.2f}",
                        f"{r.win_vs_rule:.4f}",   f"{r.mbb_vs_rule:.2f}",   f"{r.se_vs_rule:.2f}"])
    print(f"CSV saved: {csv_path}", flush=True)

    qmd_path = out / "qtable.md"
    saved_qmd = ql.save_qtable_markdown(str(qmd_path))
    print(f"Q-table markdown saved: {saved_qmd}", flush=True)

    saved = ql.save(str(out / "eval_results.pkl"))
    print(f"pickle saved: {saved}", flush=True)


if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "../results/24_softmax_mixed_8000k"
    random.seed(42)
    main(out_dir)
