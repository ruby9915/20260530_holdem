"""
train_softmax_persona_2000k.py  (26번 실험 — 성향별 단독 학습)
─────────────────────────────────────────────────────────────────────
19번 알고리즘(Prop MC + Softmax + PrevAction + CHECK=1chip)을
**학습 상대만 1종 성향(rulebased persona)으로 고정**해 2,000,000 에피소드
학습한다. 온도 스케줄/하이퍼파라미터는 19 baseline 과 동일하게 둔다.

목적 (실험일지 21절 결론 = 병목은 전이분포 / 25번 후속 A):
  각 성향이 어떤 셀 영역을 채우는지 격리 측정한다.
    lag → 베팅직면 FOLD=CALL=0 셀 자연 도달로 채워지나?
    man → BIG_RAISE(PrevAction=3) 컨텍스트 도달률↑?
    sta → 턴·리버 깊은 라운드 도달률↑?
    nit → FOLD=정답 케이스 학습되나?
    tag → 19 baseline 재현(상대=random 아닌 rulebased 단독 버전)

평가는 19번과 동일: 항상 vs random / vs (고정 TAG)rulebased.
  → 학습 상대와 평가 상대를 분리해 비교 일관성 유지(21번 mixed 과적합 교훈).
  base.evaluate() 는 어댑터 없는 raw greedy mbb/g 를 보고하므로 17.7 게이트와 동일.

19번 대비 변경:
  - 학습 상대 = random → rulebased persona (CLI 인자)
  - EVAL_EVERY = 8,000  (평가비율 0.4%, 25번과 동일)

CLI:
  argv[1] = out_dir
  argv[2] = persona  (tag | lag | man | sta | nit, default 'lag')
"""
import csv
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
import rulebased_personas as personas

STARTING_STACK       = base.STARTING_STACK
BIG_BLIND            = base.BIG_BLIND
CHECK_VIRTUAL_INVEST = base.CHECK_VIRTUAL_INVEST
# True면 total_invest==0(올체크) 핸드에서 모든 행동 invest=0 → 0-credit → 업데이트 생략.
# 기본 False(현행 equal-split payoff/n 유지). clean VIC-off 검증 전용 토글(누수 제거).
CLEAN_ZERO_INVEST = False

# α%×팟 VIC: CHECK 가상 invest = CHECK_POT_FRAC × pot (팟=sum(pots)+sum(bets)).
# POT_MODE='off'면 기존 CHECK_VIRTUAL_INVEST 사용. 'checktime'=체크시점 팟, 'terminal'=핸드 최종 팟.
CHECK_POT_FRAC = 0.0          # α/100 (예: 0.05 = 5%)
POT_MODE = 'off'              # 'off' | 'checktime' | 'terminal'
ALPHA                = base.ALPHA
GAMMA                = base.GAMMA

TOTAL_EPISODES = 2_000_000
EVAL_EVERY     = 8_000     # 평가비율 0.4%
EVAL_GAMES     = 200

_make_game      = base._make_game
evaluate        = base.evaluate
_fmt_time       = base._fmt_time
EvalResult      = base.EvalResult
temperature_at  = base.temperature_at   # 19 baseline 스케줄 (10.0→0.5, 80%)


def play_train_episode(ql: QLearning, temperature: float,
                       policy: dict, learner_id: int = 0) -> float:
    pk_state = _make_game()
    trace: list = []
    pot_peak = 0.0
    pos    = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round: dict = {}

    while pk_state.status:
        if POT_MODE == 'terminal':
            pot_peak = max(pot_peak,
                           sum(p.amount for p in pk_state.pots) + sum(pk_state.bets))
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
                if a == Action.CHECK and invest == 0:
                    if POT_MODE == 'checktime':
                        invest_for_trace = CHECK_POT_FRAC * (
                            sum(p.amount for p in pk_state.pots) + sum(pk_state.bets))
                    elif POT_MODE == 'terminal':
                        invest_for_trace = None        # 종료 후 CHECK_POT_FRAC×terminal_pot로 채움
                    else:
                        invest_for_trace = float(CHECK_VIRTUAL_INVEST)
                else:
                    invest_for_trace = invest
                trace.append((r, s, pa, a, invest_for_trace))
            else:
                personas.step_persona_opponent(
                    pk_state, opp_id, policy, prev_action_by_round)
        else:
            break

    if POT_MODE == 'terminal':                         # CHECK 가상 invest = α%×최종팟
        vinv = CHECK_POT_FRAC * pot_peak
        trace = [(r, s, pa, a, (vinv if inv is None else inv))
                 for (r, s, pa, a, inv) in trace]

    payoff       = float(pk_state.stacks[learner_id] - STARTING_STACK)
    total_invest = sum(inv for (_, _, _, _, inv) in trace)
    if total_invest > 0:
        for (r, s, pa, a, inv) in trace:
            ql.update_mc(r, pos, s, pa, a, (inv / total_invest) * payoff)
    elif not CLEAN_ZERO_INVEST:
        n = len(trace)
        if n > 0:
            R = payoff / n
            for (r, s, pa, a, _inv) in trace:
                ql.update_mc(r, pos, s, pa, a, R)
    # CLEAN_ZERO_INVEST=True: total_invest==0 이면 0-invest → 0-credit → 업데이트 생략(누수 제거)
    return payoff


def main(out_dir: str, persona: str):
    if persona not in personas.PERSONA_POLICIES:
        raise SystemExit(f"unknown persona '{persona}'. "
                         f"choose from {personas.PERSONA_NAMES}")
    policy = personas.PERSONA_POLICIES[persona]

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
    print(f"  26번 PERSONA  |  학습상대={persona.upper()}  |  평가 vs Random / 고정TAG  |  {TOTAL_EPISODES:,} ep", flush=True)
    print(f"  out: {out}", flush=True)
    print(sep, flush=True)
    print(hdr, flush=True)
    print(sep, flush=True)

    t_start = time.perf_counter()
    t_last  = t_start
    ep_last = 0

    wr, mr, sr, wrb, mrb, srb = evaluate(ql, EVAL_GAMES)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    print(f"{0:>9} {'0.0%':>5} {temperature_at(0):>5.1f} |"
          f" {wr*100:>5.1f}% {mr:>+9.0f} |"
          f" {wrb*100:>5.1f}% {mrb:>+9.0f} |"
          f" {'-':>6} {_fmt_time(time.perf_counter()-t_start):>9} {'-':>9}", flush=True)

    ep = 0
    while ep < TOTAL_EPISODES:
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)
        for i in range(ep + 1, next_eval + 1):
            temp = temperature_at(i)
            play_train_episode(ql, temp, policy, learner_id=i % 2)
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
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "../results/26_persona_lag_2000k"
    persona = sys.argv[2] if len(sys.argv) > 2 else "lag"
    random.seed(42)
    main(out_dir, persona)
