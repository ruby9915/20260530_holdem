"""
train_softmax_2000k_opp.py
─────────────────────────────────────────────────────────────────────
19번(train_eval_mc_prop_softmax_2000k.py)과 동일한 알고리즘
(Prop MC + Softmax τ:10→0.5 + PrevAction + CHECK=1chip)을
**학습 상대(opponent)만 바꿔** 2,000,000 에피소드 학습한다.

사용:
    python train_softmax_2000k_opp.py <opponent> <out_dir>
      opponent ∈ {random, rulebased, selfplay}

평가는 19번과 동일하게 항상 vs random / vs rulebased 두 기준으로 수행하므로
(상대를 바꿔 학습해도) 결과는 같은 잣대로 비교된다.
"""
import csv
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# 19번 학습 모듈에서 공통 자산을 그대로 재사용 (동일성 보장)
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
TOTAL_EPISODES       = base.TOTAL_EPISODES
ALPHA                = base.ALPHA
GAMMA                = base.GAMMA
EVAL_EVERY           = base.EVAL_EVERY          # 1만 에피소드마다 평가
EVAL_GAMES           = 10_000                   # 평가 1회당 1만 게임 (원본 200 -> SE 약 1/7로 축소)

temperature_at = base.temperature_at
_make_game     = base._make_game
_step_opponent = base._step_opponent
evaluate       = base.evaluate
_fmt_time      = base._fmt_time
EvalResult     = base.EvalResult


# ─────────────────────────────────────────────────────
# self-play 상대: 같은 Q-table을 softmax 로 두고, 그 액션을
# 학습자 시점의 PrevAction 으로 분류해 기록한다.
# ─────────────────────────────────────────────────────
def _step_self(pk_state, ql, opp_id, temperature,
               opp_prev_by_round, learner_prev_by_round):
    r_before     = pk_to_round(pk_state)
    pot_before   = (sum(pot.amount for pot in pk_state.pots)
                    + sum(pk_state.bets))
    cca_before   = pk_state.checking_or_calling_amount
    stack_before = pk_state.stacks[opp_id]
    max_to_amt   = pk_state.max_completion_betting_or_raising_to_amount

    pos_o = pk_to_position(opp_id)
    s_o   = pk_to_state(pk_state, opp_id)
    pa_o  = opp_prev_by_round.get(r_before, PrevAction.NONE)
    legal = legal_our_actions(pk_state)
    a     = ql.softmax_action(r_before, pos_o, s_o, pa_o, legal, temperature)
    execute_action(pk_state, a)

    stack_after = pk_state.stacks[opp_id]
    invest      = stack_before - stack_after
    was_allin   = (stack_after == 0 and invest > cca_before + 1e-9) \
                  or (max_to_amt == stack_before
                      and invest > cca_before + 1e-9
                      and stack_before == max_to_amt)
    pa = classify_opp_action(stack_before, stack_after, cca_before,
                             pot_before, was_allin=was_allin)
    if pa is not None:
        learner_prev_by_round[r_before] = pa


def play_train_episode(ql, temperature, opponent, learner_id=0):
    pk_state = _make_game()
    trace = []
    pos    = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    learner_prev: dict = {}   # 학습자가 직면한 (상대의) 마지막 액션
    opp_prev:     dict = {}   # self-play 상대가 직면한 (학습자의) 마지막 액션

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
                pa    = learner_prev.get(r, PrevAction.NONE)
                legal = legal_our_actions(pk_state)

                # self-play: 학습자 액션도 상대 시점 PrevAction 으로 정확히 분류
                pot_before   = (sum(pot.amount for pot in pk_state.pots)
                                + sum(pk_state.bets))
                cca_before   = pk_state.checking_or_calling_amount
                max_to_amt   = pk_state.max_completion_betting_or_raising_to_amount

                a     = ql.softmax_action(r, pos, s, pa, legal, temperature)
                stack_before = pk_state.stacks[learner_id]
                execute_action(pk_state, a)
                stack_after  = pk_state.stacks[learner_id]
                invest       = float(stack_before - stack_after)
                invest_for_trace = (
                    float(CHECK_VIRTUAL_INVEST)
                    if (a == Action.CHECK and invest == 0) else invest
                )
                trace.append((r, s, pa, a, invest_for_trace))

                if opponent == 'selfplay':
                    was_allin = (stack_after == 0 and invest > cca_before + 1e-9) \
                                or (max_to_amt == stack_before
                                    and invest > cca_before + 1e-9
                                    and stack_before == max_to_amt)
                    pa_l = classify_opp_action(stack_before, stack_after,
                                               cca_before, pot_before,
                                               was_allin=was_allin)
                    if pa_l is not None:
                        opp_prev[r] = pa_l
            else:
                if opponent == 'selfplay':
                    _step_self(pk_state, ql, opp_id, temperature,
                               opp_prev, learner_prev)
                else:
                    _step_opponent(pk_state, opp_id, opponent, learner_prev)
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


def main(opponent: str, out_dir: str):
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
    print(f"  TRAIN vs [{opponent.upper()}]  |  Prop MC Softmax + PrevAction + CHECK=1chip  |  2,000,000 ep", flush=True)
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
            temp = temperature_at(i)
            play_train_episode(ql, temp, opponent, learner_id=i % 2)
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
    opponent = sys.argv[1] if len(sys.argv) > 1 else 'random'
    out_dir  = sys.argv[2] if len(sys.argv) > 2 else f"../results/21_{opponent}_2000k"
    assert opponent in ('random', 'rulebased', 'selfplay'), opponent
    random.seed(42)
    main(opponent, out_dir)
