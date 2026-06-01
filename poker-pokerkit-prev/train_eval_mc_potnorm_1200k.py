"""
train_eval_mc_potnorm_1200k.py  (팟 정규화 MC + ε-greedy + PrevAction + CHECK=1chip)
─────────────────────────────────────────────────────────────────────
16번 실험(train_eval_mc_prop_check1_1200k.py) 기반, 변경 사항 1가지:

  ▸ 보상 신호: payoff → payoff / total_pot (팟 정규화)
        total_pot = 에이전트 투자액 합 + 상대 투자액 합
        R = (inv / total_invest_learner) × (payoff / total_pot)

  목적: 팟 크기 편향 제거.
        작은 팟과 큰 팟이 동일한 수익률이면 동일한 학습 신호를 가짐.
        payoff/total_pot ≈ ±0.5 범위로 자동 정규화됨.

  나머지 (CHECK=1chip, ε 스케줄, α·γ, PrevAction 차원) 는 16번과 동일.

에피소드: 1,200,000
평가 주기: 5,000 에피소드마다 (240 체크포인트)
"""
import csv
import math
import random
import statistics
import time
from dataclasses import dataclass

from pokerkit import Automation, NoLimitTexasHoldem

from abstraction import (
    Round, State, Action, PrevAction,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action,
    classify_opp_action,
)
from qlearning import QLearning


# ── 게임 설정 ──────────────────────────────────────────
STARTING_STACK = 200
SMALL_BLIND    = 1
BIG_BLIND      = 2

# ── CHECK 가상 invest (16번과 동일) ────────────────────
CHECK_VIRTUAL_INVEST = 1   # 1 chip (half bb)

# ── 학습 하이퍼파라미터 ───────────────────────────────
TOTAL_EPISODES  = 1_200_000
ALPHA           = 0.1
GAMMA           = 0.9
UCB_C           = 50.0   # 미사용 (ε-greedy 전용)
EPS_START       = 1.0
EPS_END         = 0.05
EPS_DECAY_END   = 0.8    # 전체의 80% 구간에서 선형 감소

# ── 평가 설정 ─────────────────────────────────────────
EVAL_EVERY      = 5_000
EVAL_GAMES      = 200
CSV_PATH        = "eval_results_mc_potnorm_1200k.csv"

_AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
    Automation.CARD_BURNING,
)


def _make_game():
    return NoLimitTexasHoldem.create_state(
        _AUTOMATIONS,
        True, 0,
        (SMALL_BLIND, BIG_BLIND),
        BIG_BLIND,
        (STARTING_STACK, STARTING_STACK),
        2,
    )


def epsilon_at(episode: int) -> float:
    progress = min(1.0, episode / (TOTAL_EPISODES * EPS_DECAY_END))
    return EPS_START + (EPS_END - EPS_START) * progress


# ─────────────────────────────────────────────────────
# 상대 에이전트
# ─────────────────────────────────────────────────────
def _random_action(pk_state) -> None:
    choices = []
    if pk_state.can_fold():                      choices.append('fold')
    if pk_state.can_check_or_call():             choices.append('check_call')
    if pk_state.can_complete_bet_or_raise_to():  choices.append('raise')

    choice = random.choice(choices)
    if choice == 'fold':
        pk_state.fold()
    elif choice == 'check_call':
        pk_state.check_or_call()
    else:
        lo = pk_state.min_completion_betting_or_raising_to_amount
        hi = pk_state.max_completion_betting_or_raising_to_amount
        pk_state.complete_bet_or_raise_to(random.randint(lo, hi))


_RULE_POLICY = {
    (Round.PREFLOP, False): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.RAISE_50,    State.DECENT: Action.RAISE_25,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.PREFLOP, True): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.CALL,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
    (Round.FLOP, False): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.RAISE_50,    State.DECENT: Action.RAISE_25,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.FLOP, True): {
        State.PREMIUM: Action.RAISE_100, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.FOLD,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
    (Round.TURN, False): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_75,
        State.GOOD: Action.RAISE_25,    State.DECENT: Action.CHECK,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.TURN, True): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_50,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.FOLD,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
    (Round.RIVER, False): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_50,
        State.GOOD: Action.RAISE_25,    State.DECENT: Action.CHECK,
        State.MEDIOCRE: Action.CHECK,   State.WEAK: Action.CHECK,
        State.POOR: Action.CHECK,       State.TRASH: Action.CHECK,
    },
    (Round.RIVER, True): {
        State.PREMIUM: Action.RAISE_75, State.STRONG: Action.RAISE_50,
        State.GOOD: Action.CALL,         State.DECENT: Action.CALL,
        State.MEDIOCRE: Action.FOLD,     State.WEAK: Action.FOLD,
        State.POOR: Action.FOLD,         State.TRASH: Action.FOLD,
    },
}


def _rulebased_action(pk_state, player_idx: int) -> None:
    r          = pk_to_round(pk_state)
    s          = pk_to_state(pk_state, player_idx)
    facing_bet = pk_state.checking_or_calling_amount > 0
    action     = _RULE_POLICY[(r, facing_bet)][s]
    legal      = legal_our_actions(pk_state)

    if action not in legal:
        fallback_order = [Action.CHECK, Action.CALL, Action.FOLD,
                          Action.RAISE_25, Action.RAISE_50,
                          Action.RAISE_75, Action.RAISE_100, Action.RAISE_ALLIN]
        action = next((a for a in fallback_order if a in legal), legal[0])

    execute_action(pk_state, action)


# ─────────────────────────────────────────────────────
# 헬퍼: 상대 액션 처리 → PrevAction 갱신 + invest 반환
# ─────────────────────────────────────────────────────
def _step_opponent(pk_state, opp_id: int, opponent: str,
                   prev_action_by_round: dict) -> float:
    """상대 액션을 실행하고 실제 투자액(chips)을 반환한다."""
    r_before      = pk_to_round(pk_state)
    pot_before    = (sum(pot.amount for pot in pk_state.pots)
                     + sum(pk_state.bets))
    cca_before    = pk_state.checking_or_calling_amount
    stack_before  = pk_state.stacks[opp_id]
    max_to_amount = pk_state.max_completion_betting_or_raising_to_amount

    if opponent == 'random':
        _random_action(pk_state)
    else:
        _rulebased_action(pk_state, opp_id)

    stack_after = pk_state.stacks[opp_id]
    invest      = stack_before - stack_after
    was_allin   = (stack_after == 0 and invest > cca_before + 1e-9) \
                  or (max_to_amount == stack_before
                      and invest > cca_before + 1e-9
                      and stack_before == max_to_amount)

    pa = classify_opp_action(stack_before, stack_after, cca_before,
                             pot_before, was_allin=was_allin)
    if pa is not None:
        prev_action_by_round[r_before] = pa

    return max(0.0, float(invest))  # 상대 투자액 반환 (팟 추적용)


# ─────────────────────────────────────────────────────
# 학습 에피소드 — 팟 정규화 보상
# ─────────────────────────────────────────────────────
def play_train_episode(ql: QLearning, epsilon: float,
                       learner_id: int = 0) -> float:
    pk_state = _make_game()
    trace: list[tuple[Round, State, PrevAction, Action, float]] = []
    pos    = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round: dict = {}
    total_opp_invest = 0.0  # 상대 총 투자액 (팟 계산용)

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
                a     = ql.epsilon_greedy(r, pos, s, pa, legal, epsilon)

                stack_before = pk_state.stacks[learner_id]
                execute_action(pk_state, a)
                stack_after  = pk_state.stacks[learner_id]
                invest       = float(stack_before - stack_after)

                # CHECK → 1chip 가상 invest (흡수 상태 방지)
                invest_for_trace = (
                    float(CHECK_VIRTUAL_INVEST)
                    if (a == Action.CHECK and invest == 0)
                    else invest
                )

                trace.append((r, s, pa, a, invest_for_trace))
            else:
                opp_inv = _step_opponent(pk_state, opp_id, 'random',
                                         prev_action_by_round)
                total_opp_invest += opp_inv
        else:
            break

    payoff       = float(pk_state.stacks[learner_id] - STARTING_STACK)
    total_invest = sum(inv for (_, _, _, _, inv) in trace)

    # ── 핵심 변경: payoff → payoff / total_pot ────────
    # total_pot = 에이전트 투자 + 상대 투자 (실제 팟 크기)
    total_pot = total_invest + total_opp_invest

    if total_invest > 0 and total_pot > 0:
        norm_payoff = payoff / total_pot
        for (r, s, pa, a, inv) in trace:
            R = (inv / total_invest) * norm_payoff
            ql.update_mc(r, pos, s, pa, a, R)
    elif total_invest > 0:
        # total_pot == 0 는 사실상 불가능하나 안전망
        for (r, s, pa, a, inv) in trace:
            R = (inv / total_invest) * payoff
            ql.update_mc(r, pos, s, pa, a, R)
    else:
        n = len(trace)
        if n > 0:
            R = (payoff / total_pot / n) if total_pot > 0 else 0.0
            for (r, s, pa, a, _inv) in trace:
                ql.update_mc(r, pos, s, pa, a, R)

    return payoff


# ─────────────────────────────────────────────────────
# 평가 에피소드 (greedy, Q 미갱신)
# ─────────────────────────────────────────────────────
def _play_eval_episode(ql: QLearning, opponent: str,
                       learner_id: int = 0) -> float:
    pk_state = _make_game()
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
                a     = ql.best_action(r, pos, s, pa, legal)
                execute_action(pk_state, a)
            else:
                _step_opponent(pk_state, opp_id, opponent,
                               prev_action_by_round)
        else:
            break

    return float(pk_state.stacks[learner_id] - STARTING_STACK)


@dataclass
class EvalResult:
    episode:       int
    win_vs_random: float
    mbb_vs_random: float
    se_vs_random:  float
    win_vs_rule:   float
    mbb_vs_rule:   float
    se_vs_rule:    float


def _mbb_and_se(payoffs: list[float]) -> tuple[float, float]:
    n    = len(payoffs)
    mean = sum(payoffs) / n
    std  = statistics.stdev(payoffs) if n > 1 else 0.0
    scale = 1000.0 / BIG_BLIND
    return mean * scale, (std / math.sqrt(n)) * scale


def evaluate(ql: QLearning, n_games: int = EVAL_GAMES):
    payoffs_r:  list[float] = []
    payoffs_rb: list[float] = []
    for i in range(n_games):
        payoffs_r.append(_play_eval_episode(ql, 'random',    learner_id=i % 2))
    for i in range(n_games):
        payoffs_rb.append(_play_eval_episode(ql, 'rulebased', learner_id=i % 2))
    win_r  = sum(1 for p in payoffs_r  if p > 0) / n_games
    win_rb = sum(1 for p in payoffs_rb if p > 0) / n_games
    mbb_r,  se_r  = _mbb_and_se(payoffs_r)
    mbb_rb, se_rb = _mbb_and_se(payoffs_rb)
    return win_r, mbb_r, se_r, win_rb, mbb_rb, se_rb


def _fmt_time(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    if m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def main():
    ql      = QLearning(alpha=ALPHA, gamma=GAMMA, ucb_c=UCB_C)
    results: list[EvalResult] = []

    hdr = (f"{'episode':>9} {'pct':>5} {'eps':>5} │"
           f" {'rand%':>6} {'mbb/g_r':>10} │"
           f" {'rule%':>6} {'mbb/g_rl':>10} │"
           f" {'ep/s':>6} {'elapsed':>9} {'ETA':>9}")
    sep = "─" * len(hdr)
    print(sep)
    print(f"  팟 정규화 보상  │  (inv/total)×(payoff/total_pot)  │  MC ε-greedy + PrevAction + CHECK=1chip  │  1,200,000 ep")
    print(sep)
    print(hdr)
    print(sep)

    t_start    = time.perf_counter()
    t_last_log = t_start
    ep_last    = 0

    # 초기 평가 (ep=0)
    wr, mr, sr, wrb, mrb, srb = evaluate(ql)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    elapsed = time.perf_counter() - t_start
    print(f"{0:>9} {'0.0%':>5} {'1.00':>5} │"
          f" {wr*100:>5.1f}% {mr:>+9.0f} │"
          f" {wrb*100:>5.1f}% {mrb:>+9.0f} │"
          f" {'—':>6} {_fmt_time(elapsed):>9} {'—':>9}")

    ep = 0
    while ep < TOTAL_EPISODES:
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)

        for i in range(ep + 1, next_eval + 1):
            eps = epsilon_at(i)
            play_train_episode(ql, eps, learner_id=i % 2)

        ep = next_eval

        t_now    = time.perf_counter()
        elapsed  = t_now - t_start
        interval = t_now - t_last_log
        eps_done = ep - ep_last
        speed    = eps_done / interval if interval > 0 else 0.0
        remain   = TOTAL_EPISODES - ep
        eta      = remain / speed if speed > 0 else 0.0

        t_last_log = t_now
        ep_last    = ep

        wr, mr, sr, wrb, mrb, srb = evaluate(ql)
        results.append(EvalResult(ep, wr, mr, sr, wrb, mrb, srb))

        pct    = ep / TOTAL_EPISODES * 100
        cur_ep = epsilon_at(ep)
        print(f"{ep:>9} {pct:>4.1f}% {cur_ep:>5.2f} │"
              f" {wr*100:>5.1f}% {mr:>+9.0f} │"
              f" {wrb*100:>5.1f}% {mrb:>+9.0f} │"
              f" {speed:>6.0f} {_fmt_time(elapsed):>9} {_fmt_time(eta):>9}")

    print(sep)
    total_time = time.perf_counter() - t_start
    print(f"  총 학습 시간: {_fmt_time(total_time)}  │  평균 속도: {TOTAL_EPISODES / total_time:.0f} ep/s")
    print(sep)

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['episode',
                         'win%_vs_random', 'mbb/g_vs_random', 'se_vs_random',
                         'win%_vs_rulebased', 'mbb/g_vs_rulebased', 'se_vs_rulebased'])
        for r in results:
            writer.writerow([r.episode,
                             f"{r.win_vs_random:.4f}",  f"{r.mbb_vs_random:.2f}",  f"{r.se_vs_random:.2f}",
                             f"{r.win_vs_rule:.4f}",    f"{r.mbb_vs_rule:.2f}",    f"{r.se_vs_rule:.2f}"])
    print(f"CSV 저장 완료: {CSV_PATH}")

    print("\n=== 학습 완료 Q-테이블 (팟 정규화 MC + PrevAction) ===")
    ql.print_q_table()

    pkl_path = CSV_PATH.replace('.csv', '.pkl')
    saved = ql.save(pkl_path)
    print(f"Q-table pickle 저장 완료: {saved}")


if __name__ == '__main__':
    random.seed(42)
    main()
