"""
train_eval_td.py  (UCB 탐색 버전 — TD Q-러닝)
─────────────────────────────────────────────────────────────────────
학습 흐름:
    [TRAIN N episodes] → [EVAL vs Random 200게임] → [EVAL vs RuleBased 200게임]
    → 반복

탐색 정책: UCB1  (ε-greedy 대신)
    a = argmax_a [ Q(s,a) + UCB_C * sqrt(ln(N_s) / N(s,a)) ]
    미방문 행동 → 즉시 선택

평가 시 순수 greedy (UCB 보너스 없음) 고정 → 학습된 정책만 사용.
결과는 콘솔 테이블 + CSV 파일로 출력.

상대 종류:
    RandomAgent   : FOLD/CHECK_CALL/RAISE 균등 랜덤
    RuleBasedAgent: 핸드 강도(State)에 따라 고정 정책
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
CSV_PATH        = "eval_results_td_ucb.csv"

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
# 에피소드 실행 (학습용 — UCB 탐색)
# ─────────────────────────────────────────────────────
def play_train_episode(ql: QLearning, learner_id: int = 0) -> float:
    """
    TD(0) 업데이트 + UCB 탐색.
    각 행동 선택 후 방문 카운트 increment_n 호출.
    중간 전환: reward=0, 마지막 스텝: reward=최종 payoff.
    """
    pk_state = _make_game()
    trace: list[tuple[Round, State, Action]] = []
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
                if trace:
                    pr, ps, pa = trace[-1]
                    ql.update_q(pr, pos, ps, pa, reward=0.0,
                                next_r=r, next_s=s, terminal=False)
                trace.append((r, s, a))
                execute_action(pk_state, a)
            else:
                _random_action(pk_state)
        else:
            break

    payoff = float(pk_state.stacks[learner_id] - STARTING_STACK)
    if trace:
        lr, ls, la = trace[-1]
        ql.update_q(lr, pos, ls, la, reward=payoff, terminal=True)
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

    print("\n=== 학습 완료 Q-테이블 (TD-UCB) ===")
    ql.print_q_table()

    pkl_path = CSV_PATH.rsplit('.', 1)[0] + '.pkl' if CSV_PATH.endswith('.csv') else CSV_PATH + '.pkl'
    saved = ql.save(pkl_path)
    print(f"Q-table pickle 저장 완료: {saved}")


if __name__ == '__main__':
    random.seed(42)
    main()
