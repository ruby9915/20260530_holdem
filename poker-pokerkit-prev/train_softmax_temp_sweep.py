"""
train_softmax_temp_sweep.py  (25번 실험)
─────────────────────────────────────────────────────────────────────
19번 알고리즘(Prop MC + Softmax + PrevAction + CHECK=1chip)을
**온도 스케줄만 바꿔** 2,000,000 에피소드 학습한다.

목적 (실험일지 21절 1순위 문제 검증):
  베팅 직면 미탐색 동률(FOLD=CALL=0) 셀을 softmax 탐색 강화로 줄일 수 있는가?
  온도(시작/하한/감소구간)를 4조건으로 나눠 각각 별도 CPU 코어에서 병렬 학습하고,
  매 평가 시 raw greedy mbb/g(=어댑터 없는 best_action, 본 파이프라인 evaluate)를
  기록해 "탐색↑ → 미탐색 셀↓ → raw mbb↑" 전이를 본다.

19번 대비 변경:
  - temperature_at 를 CLI 인자(TS/TE/DECAY)로 파라미터화 (19 = 10/0.5/0.8)
  - EVAL_EVERY = 8,000  (평가비율 0.4% = 8000/2,000,000; 24번 0.625%에서 하향)
  - 상대 = random 고정 (19 baseline과 동일 — 온도 외 변수 통제)

주의:
  - 본 파이프라인 evaluate()/best_action()은 어댑터(FOLD 회피)가 없다.
    best_action = max(legal, key=Q)이고 FOLD가 legal 첫 원소라 0.000 동률 시 FOLD 승.
    따라서 여기 mbb/g 는 이미 raw greedy 지표이며 17.7 게이트와 동일하다.

CLI:
  argv[1] = out_dir
  argv[2] = temp_start    (default 10.0)
  argv[3] = temp_end      (default 0.5)
  argv[4] = temp_decay_end(default 0.8)
"""
import csv
import math
import random
import sys
import time
from pathlib import Path

import train_eval_mc_prop_softmax_2000k as base
from abstraction import (
    Round, State, Action, PrevAction,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action,
)
from qlearning import QLearning

STARTING_STACK       = base.STARTING_STACK
BIG_BLIND            = base.BIG_BLIND
CHECK_VIRTUAL_INVEST = base.CHECK_VIRTUAL_INVEST
ALPHA                = base.ALPHA
GAMMA                = base.GAMMA

TOTAL_EPISODES = 2_000_000
EVAL_EVERY     = 8_000     # 평가비율 0.4% (= 8000 / 2,000,000)
EVAL_GAMES     = 200

_make_game     = base._make_game
_step_opponent = base._step_opponent
evaluate       = base.evaluate
_fmt_time      = base._fmt_time
EvalResult     = base.EvalResult


def make_temperature_at(ts: float, te: float, decay_end: float):
    """온도 스케줄 클로저: episode → temperature."""
    def temperature_at(episode: int) -> float:
        progress = min(1.0, episode / (TOTAL_EPISODES * decay_end))
        return ts + (te - ts) * progress
    return temperature_at


def play_train_episode(ql: QLearning, temperature: float,
                       learner_id: int = 0) -> float:
    pk_state = _make_game()
    trace: list[tuple[Round, State, PrevAction, Action, float]] = []
    pos    = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round: dict = {}

    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()
        elif pk_state.can_deal_board():
            pk_state.deal_board()
        elif pk_state.actor_index is not None:
            pid = pk_state.actor_index
            if pid == learner_id:
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
                _step_opponent(pk_state, opp_id, 'random', prev_action_by_round)
        else:
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


def main(out_dir: str, ts: float, te: float, decay_end: float):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "eval_results.csv"

    temperature_at = make_temperature_at(ts, te, decay_end)

    ql = QLearning(alpha=ALPHA, gamma=GAMMA, ucb_c=50.0)
    results = []

    hdr = (f"{'episode':>9} {'pct':>5} {'temp':>5} |"
           f" {'rand%':>6} {'mbb/g_r':>10} |"
           f" {'rule%':>6} {'mbb/g_rl':>10} |"
           f" {'ep/s':>6} {'elapsed':>9} {'ETA':>9}")
    sep = "-" * len(hdr)
    print(sep, flush=True)
    print(f"  25번 TEMP-SWEEP  |  TS={ts} TE={te} DECAY={decay_end}  |  vs Random  |  {TOTAL_EPISODES:,} ep", flush=True)
    print(f"  out: {out}", flush=True)
    print(sep, flush=True)
    print(hdr, flush=True)
    print(sep, flush=True)

    t_start = time.perf_counter()
    t_last  = t_start
    ep_last = 0

    wr, mr, sr, wrb, mrb, srb = evaluate(ql, EVAL_GAMES)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    print(f"{0:>9} {'0.0%':>5} {ts:>5.1f} |"
          f" {wr*100:>5.1f}% {mr:>+9.0f} |"
          f" {wrb*100:>5.1f}% {mrb:>+9.0f} |"
          f" {'-':>6} {_fmt_time(time.perf_counter()-t_start):>9} {'-':>9}", flush=True)

    ep = 0
    while ep < TOTAL_EPISODES:
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)
        for i in range(ep + 1, next_eval + 1):
            temp = temperature_at(i)
            play_train_episode(ql, temp, learner_id=i % 2)
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
    print(f"Q-table markdown saved: {ql.save_qtable_markdown(str(qmd_path))}", flush=True)
    print(f"pickle saved: {ql.save(str(out / 'eval_results.pkl'))}", flush=True)


if __name__ == '__main__':
    out_dir   = sys.argv[1] if len(sys.argv) > 1 else "../results/25a_temp_baseline_2000k"
    ts        = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    te        = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    decay_end = float(sys.argv[4]) if len(sys.argv) > 4 else 0.8
    random.seed(42)
    main(out_dir, ts, te, decay_end)
