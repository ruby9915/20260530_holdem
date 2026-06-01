"""
train_eval_mc_prop.py  (비례 배분 MC)
─────────────────────────────────────────────────────────────────────
탐색 정책: UCB1

MC 업데이트: 각 액션이 다년안 칩의 비율만큼 최종 payoff를 나눠갖는다.
    invest_i = |stack_after - stack_before|   (액션 시 낸 칩, CHECK은 0)
    total = Σ invest_i
    R_i   = (invest_i / total) * payoff   (total > 0일 때)
    Q(s, a) ← Q(s, a) + α [ R_i - Q(s, a) ]

설계 의도: 승패가 대칭 (승 +R, 패 -R, R은 다년안 액션 구조에 비례) →
50% 승률 핸드의 기댓값이 모든 액션에서 0 → 폴드 수렴 구조 제거.

CHECK/FOLD는 invest=0 → R=0 (포트 그대로, 장대적으로는 0으로 수렴).
FOLD의 경우 invest=0이면 이전 액션들도 될 수 있으므로, 다른 액션이 있으면 그들에 배분됨.
"""
import csv
import math
import random
import statistics
from dataclasses import dataclass

from pokerkit import Automation, NoLimitTexasHoldem

from abstraction import (
    Round, State, Action,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action,
)
from qlearning import QLearning


# ── 게임 설정 ──────────────────────────────────────────
STARTING_STACK = 200
SMALL_BLIND    = 1
BIG_BLIND      = 2

# ── 학습 하이퍼파라미터 ───────────────────────────────
TOTAL_EPISODES  = 40_000
ALPHA           = 0.1
GAMMA           = 0.9
UCB_C           = 50.0   # UCB 탐색 계수 (보상 스케일: ±200칩)

# ── 평가 설정 ─────────────────────────────────────────
EVAL_EVERY      = 200
EVAL_GAMES      = 200
CSV_PATH        = "eval_results_mc_prop.csv"

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


# ─────────────────────────────────────────────────────
# 게임 생성
# ─────────────────────────────────────────────────────
def _make_game():
    return NoLimitTexasHoldem.create_state(
        _AUTOMATIONS,
        True, 0,
        (SMALL_BLIND, BIG_BLIND),
        BIG_BLIND,
        (STARTING_STACK, STARTING_STACK),
        2,
    )


# ─────────────────────────────────────────────────────
# 상대 에이전트
# ─────────────────────────────────────────────────────
def _random_action(pk_state) -> None:
    """균등 랜덤 에이전트"""
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


# 룰 기반 에이전트 정책: (Round, facing_bet) → State → Action
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
    """라운드 × facing-bet × 핸드 강도 기반 고정 정책 에이전트"""
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
# 에피소드 실행 (학습용 — 비례 배분 MC)
# ─────────────────────────────────────────────────────
def play_train_episode(ql: QLearning, learner_id: int = 0) -> float:
    """
    UCB로 행동 선택, 종료 후 각 액션의 투자 비율만큼 payoff를 배분해 업데이트.
    """
    pk_state = _make_game()
    trace: list[tuple[Round, State, Action, float]] = []  # (r, s, a, invest)
    pos = pk_to_position(learner_id)

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
                legal = legal_our_actions(pk_state)
                a     = ql.ucb_action(r, pos, s, legal)
                ql.increment_n(r, pos, s, a)

                stack_before = pk_state.stacks[learner_id]
                execute_action(pk_state, a)
                stack_after  = pk_state.stacks[learner_id]
                invest = float(stack_before - stack_after)  # 낸 칩 (>=0)

                trace.append((r, s, a, invest))
            else:
                _random_action(pk_state)
        else:
            break

    payoff = float(pk_state.stacks[learner_id] - STARTING_STACK)
    total_invest = sum(inv for (_, _, _, inv) in trace)

    if total_invest > 0:
        for (r, s, a, inv) in trace:
            R = (inv / total_invest) * payoff
            ql.update_mc(r, pos, s, a, R)
    else:
        # 전부 CHECK/FOLD로 투자액 0 → 굠이 구분 못 함. 귀속을 위해 payoff를 균등 배분.
        n = len(trace)
        if n > 0:
            R = payoff / n
            for (r, s, a, _inv) in trace:
                ql.update_mc(r, pos, s, a, R)

    return payoff


# ─────────────────────────────────────────────────────
# 평가 (greedy, Q 업데이트 없음)
# ─────────────────────────────────────────────────────
def _play_eval_episode(ql: QLearning, opponent: str,
                       learner_id: int = 0) -> float:
    pk_state = _make_game()
    pos = pk_to_position(learner_id)

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
                legal = legal_our_actions(pk_state)
                a     = ql.best_action(r, pos, s, legal)
                execute_action(pk_state, a)
            else:
                if opponent == 'random':
                    _random_action(pk_state)
                else:
                    opp_id = 1 - learner_id
                    _rulebased_action(pk_state, opp_id)
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
    """n_games씩 두 상대와 대전, (win_r, mbb_r, se_r, win_rb, mbb_rb, se_rb) 반환
    포지션 교대: 절반은 BB(0), 절반은 SB(1)
    """
    payoffs_r:  list[float] = []
    payoffs_rb: list[float] = []

    for i in range(n_games):
        payoffs_r.append(_play_eval_episode(ql, 'random', learner_id=i % 2))
    for i in range(n_games):
        payoffs_rb.append(_play_eval_episode(ql, 'rulebased', learner_id=i % 2))

    win_r  = sum(1 for p in payoffs_r  if p > 0) / n_games
    win_rb = sum(1 for p in payoffs_rb if p > 0) / n_games
    mbb_r,  se_r  = _mbb_and_se(payoffs_r)
    mbb_rb, se_rb = _mbb_and_se(payoffs_rb)
    return win_r, mbb_r, se_r, win_rb, mbb_rb, se_rb


# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────
def main():
    ql      = QLearning(alpha=ALPHA, gamma=GAMMA, ucb_c=UCB_C)
    results: list[EvalResult] = []

    hdr = (f"{'episode':>8} │ {'win%_rand':>9} {'mbb/g_rand':>14} │"
           f" {'win%_rule':>9} {'mbb/g_rule':>14}")
    sep = "─" * len(hdr)
    print(sep)
    print(hdr)
    print(sep)

    # ep=0 기준선 평가
    wr, mr, sr, wrb, mrb, srb = evaluate(ql)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    print(f"{0:>8} │ {wr*100:>8.1f}% {mr:>+8.0f}±{sr:>4.0f} │ {wrb*100:>8.1f}% {mrb:>+8.0f}±{srb:>4.0f}")

    ep = 0
    while ep < TOTAL_EPISODES:
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)
        for i in range(ep + 1, next_eval + 1):
            play_train_episode(ql, learner_id=i % 2)
        ep = next_eval

        wr, mr, sr, wrb, mrb, srb = evaluate(ql)
        results.append(EvalResult(ep, wr, mr, sr, wrb, mrb, srb))
        print(f"{ep:>8} │ {wr*100:>8.1f}% {mr:>+8.0f}±{sr:>4.0f} │ {wrb*100:>8.1f}% {mrb:>+8.0f}±{srb:>4.0f}")

    print(sep)

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['episode',
                         'win%_vs_random', 'mbb/g_vs_random', 'se_vs_random',
                         'win%_vs_rulebased', 'mbb/g_vs_rulebased', 'se_vs_rulebased'])
        for r in results:
            writer.writerow([r.episode,
                             f"{r.win_vs_random:.4f}", f"{r.mbb_vs_random:.2f}", f"{r.se_vs_random:.2f}",
                             f"{r.win_vs_rule:.4f}",   f"{r.mbb_vs_rule:.2f}",   f"{r.se_vs_rule:.2f}"])
    print(f"\nCSV 저장 완료: {CSV_PATH}")

    print("\n=== 학습 완료 Q-테이블 (비례 배분 MC) ===")
    ql.print_q_table()

    pkl_path = CSV_PATH.rsplit('.', 1)[0] + '.pkl' if CSV_PATH.endswith('.csv') else CSV_PATH + '.pkl'
    saved = ql.save(pkl_path)
    print(f"Q-table pickle 저장 완료: {saved}")


if __name__ == '__main__':
    random.seed(42)
    main()
