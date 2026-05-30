"""
train.py (MC + 즉각 비용 버전)
─────────────────────────────────────────────────────────────────────
PokerKit `NoLimitTexasHoldem` 환경에서 Monte Carlo Q-러닝 학습.

원본 poker-pokerkit/train.py 대비 변경점:
  - TD(0) bootstrap 제거 → 에피소드 종료 후 역방향 G 계산으로 일괄 업데이트
  - 각 액션의 칩 변화량(immediate reward) 을 기록
  - 마지막 액션 직후 스택을 저장해 terminal_reward(팟 수령액) 산출
"""
import random

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

# ── 하이퍼파라미터 ────────────────────────────────────
NUM_EPISODES   = 20_000
ALPHA          = 0.1
GAMMA          = 0.9
EPS_START      = 1.0
EPS_END        = 0.05
EPS_DECAY_END  = 0.8
PRINT_EVERY    = 2_000

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


def epsilon_at(episode: int) -> float:
    progress = min(1.0, episode / (NUM_EPISODES * EPS_DECAY_END))
    return EPS_START + (EPS_END - EPS_START) * progress


def _make_game():
    return NoLimitTexasHoldem.create_state(
        _AUTOMATIONS,
        True, 0,
        (SMALL_BLIND, BIG_BLIND),
        BIG_BLIND,
        (STARTING_STACK, STARTING_STACK),
        2,
    )


def _random_action(pk_state) -> None:
    """상대 플레이어: 균등 랜덤"""
    choices = []
    if pk_state.can_fold():        choices.append('fold')
    if pk_state.can_check_or_call(): choices.append('check_call')
    if pk_state.can_complete_bet_or_raise_to(): choices.append('raise')

    choice = random.choice(choices)
    if choice == 'fold':
        pk_state.fold()
    elif choice == 'check_call':
        pk_state.check_or_call()
    else:
        lo = pk_state.min_completion_betting_or_raising_to_amount
        hi = pk_state.max_completion_betting_or_raising_to_amount
        pk_state.complete_bet_or_raise_to(random.randint(lo, hi))


def play_one_episode(ql: QLearning, epsilon: float,
                     learner_id: int = 0) -> float:
    """
    MC + 즉각 비용 한 게임:
      1. 매 액션마다 (r, s, a, immediate) 를 trace에 누적
      2. 에피소드 종료 후 역방향으로 G 계산 + Q 업데이트
    """
    pk_state = _make_game()
    trace: list[tuple[Round, State, Action, float]] = []
    stack_at_last_action: int = STARTING_STACK
    pos = pk_to_position(learner_id)

    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()

        elif pk_state.can_deal_board():
            pk_state.deal_board()

        elif pk_state.actor_index is not None:
            pid = pk_state.actor_index

            if pid == learner_id:
                # ── 학습자 차례 ──────────────────────
                r     = pk_to_round(pk_state)
                s     = pk_to_state(pk_state, learner_id)
                legal = legal_our_actions(pk_state)
                a     = ql.epsilon_greedy(r, pos, s, legal, epsilon)

                stack_before = pk_state.stacks[learner_id]
                execute_action(pk_state, a)                       # execute 먼저
                stack_after  = pk_state.stacks[learner_id]

                immediate = float(stack_after - stack_before)     # 베팅=음수
                trace.append((r, s, a, immediate))
                stack_at_last_action = stack_after

            else:
                # ── 상대 차례 (랜덤) ─────────────────
                _random_action(pk_state)

        else:
            break

    # ── 게임 종료: MC 역전파 ────────────────────────
    # terminal_reward = 마지막 액션 직후~게임 종료 사이의 스택 변화
    # PokerKit이 자동으로 팟을 지급하므로 양수 (이긴 경우) or 0 (진 경우)
    terminal_reward = float(pk_state.stacks[learner_id] - stack_at_last_action)
    payoff          = float(pk_state.stacks[learner_id] - STARTING_STACK)

    G = terminal_reward
    for (r, s, a, imm) in reversed(trace):
        G = imm + ql.gamma * G
        ql.update_mc(r, pos, s, a, G)

    return payoff


def main():
    ql = QLearning(alpha=ALPHA, gamma=GAMMA)

    total_reward = 0.0
    wins = 0

    for ep in range(1, NUM_EPISODES + 1):
        eps = epsilon_at(ep)
        # 매 에피소드 포지션 교대 (BB / SB)
        r   = play_one_episode(ql, eps, learner_id=ep % 2)
        total_reward += r
        if r > 0:
            wins += 1

        if ep % PRINT_EVERY == 0:
            avg = total_reward / PRINT_EVERY
            wr  = wins / PRINT_EVERY * 100
            print(f"[ep {ep:>6}] eps={eps:.3f}  "
                  f"avg_reward={avg:+.3f}  win%={wr:5.1f}")
            total_reward = 0.0
            wins = 0

    print("\n=== 학습 완료 Q-테이블 (MC) ===")
    ql.print_q_table()

    print("\n=== 라운드·포지션별 최선 행동 (greedy) ===")
    from abstraction import Position
    for r in Round:
        for p in Position:
            print(f"\n[{r.name} · {p.name}]")
            for s in State:
                a  = ql.best_action(r, p, s)
                qv = ql.get_q(r, p, s, a)
                print(f"  {s.name:<10} → {a.name:<12}  (Q={qv:+.3f})")


if __name__ == '__main__':
    random.seed(42)
    main()
