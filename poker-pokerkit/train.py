"""
train.py
─────────────────────────────────────────────────────────────────────
PokerKit `NoLimitTexasHoldem` 환경에서 테이블 Q-러닝을 학습.

poker-rlcard/train.py 와 동일한 조건:
  - 20,000 에피소드
  - α=0.1, γ=0.9, ε 1.0→0.05 (진행률 80% 시점 도달)
  - 학습자(0번) vs RandomAgent(1번)
  - 2인 No-Limit Texas Hold'em, 스택 200칩, 블라인드 1/2

RLCard 버전과의 핵심 차이:
  - RAISE_25/50/75/100을 팟 대비 정확한 % 금액으로 베팅 가능
  - 게임 루프를 직접 제어 (딜 → 베팅 → 딜 → ... → 쇼다운)
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

# ── 하이퍼파라미터 (poker-rlcard 와 동일) ─────────────
NUM_EPISODES   = 20_000
ALPHA          = 0.1
GAMMA          = 0.9
EPS_START      = 1.0
EPS_END        = 0.05
EPS_DECAY_END  = 0.8    # 진행률 80% 시점에 EPS_END 도달
PRINT_EVERY    = 2_000

# PokerKit 자동화 항목
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


# ── 유틸리티 ──────────────────────────────────────────
def epsilon_at(episode: int) -> float:
    """선형 감소 epsilon"""
    progress = min(1.0, episode / (NUM_EPISODES * EPS_DECAY_END))
    return EPS_START + (EPS_END - EPS_START) * progress


def _make_game():
    """새 2인 No-Limit Texas Hold'em 게임 상태 생성"""
    return NoLimitTexasHoldem.create_state(
        _AUTOMATIONS,
        True,                              # ante_trimming_status
        0,                                 # antes
        (SMALL_BLIND, BIG_BLIND),          # blinds
        BIG_BLIND,                         # min_bet
        (STARTING_STACK, STARTING_STACK),  # 초기 스택
        2,                                 # 플레이어 수
    )


def _random_action(pk_state) -> None:
    """상대 플레이어: 랜덤 행동 (FOLD/CHECK_CALL/RAISE 중 균등 선택)"""
    choices = []
    if pk_state.can_fold():
        choices.append('fold')
    if pk_state.can_check_or_call():
        choices.append('check_call')
    if pk_state.can_complete_bet_or_raise_to():
        choices.append('raise')

    choice = random.choice(choices)
    if choice == 'fold':
        pk_state.fold()
    elif choice == 'check_call':
        pk_state.check_or_call()
    else:
        lo = pk_state.min_completion_betting_or_raising_to_amount
        hi = pk_state.max_completion_betting_or_raising_to_amount
        pk_state.complete_bet_or_raise_to(random.randint(lo, hi))


# ── 에피소드 1회 실행 ──────────────────────────────────
def play_one_episode(ql: QLearning, epsilon: float,
                     learner_id: int = 0) -> float:
    """
    한 게임 진행 + Q-테이블 업데이트.

    게임 루프 흐름:
        while 게임 진행 중:
            홀카드 딜 필요 → deal_hole()        (1장씩)
            보드카드 딜 필요 → deal_board()     (1회 = 해당 스트리트 전체)
            행동 필요:
                학습자 → ε-greedy + Q 업데이트
                상대방 → 랜덤

    비터미널 업데이트: 이전 (r,s,a) → reward=0, bootstrap 다음 (r',s')
    터미널 업데이트 : 마지막 (r,s,a) → 최종 payoff
    """
    pk_state = _make_game()
    learner_trace: list[tuple[Round, State, Action]] = []
    pos = pk_to_position(learner_id)

    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()

        elif pk_state.can_deal_board():
            # 한 번 호출로 해당 스트리트의 모든 카드 딜 (flop=3, turn/river=1)
            pk_state.deal_board()

        elif pk_state.actor_index is not None:
            pid = pk_state.actor_index

            if pid == learner_id:
                # ── 학습자 차례 ──────────────────────
                r     = pk_to_round(pk_state)
                s     = pk_to_state(pk_state, learner_id)
                legal = legal_our_actions(pk_state)
                a     = ql.epsilon_greedy(r, pos, s, legal, epsilon)

                # 비터미널 업데이트: 이전 액션의 Q값 갱신
                if learner_trace:
                    pr, ps, pa = learner_trace[-1]
                    ql.update_q(pr, pos, ps, pa, reward=0.0,
                                next_r=r, next_s=s, terminal=False)

                learner_trace.append((r, s, a))
                execute_action(pk_state, a)

            else:
                # ── 상대 차례 ────────────────────────
                _random_action(pk_state)

        else:
            # 자동 처리 중인 상태 (쇼다운, 칩 분배 등)
            # 모든 자동화가 활성화되어 있으므로 이 분기는 거의 발생하지 않음
            break

    # ── 게임 종료: 최종 보상으로 터미널 업데이트 ─────
    payoff = float(pk_state.stacks[learner_id] - STARTING_STACK)
    if learner_trace:
        lr, ls, la = learner_trace[-1]
        ql.update_q(lr, ls, la, reward=payoff, terminal=True)

    return payoff


# ── 메인 학습 루프 ────────────────────────────────────
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

    # ── 학습 완료 후 Q-테이블 출력 ───────────────────
    print("\n=== 학습 완료 Q-테이블 ===")
    ql.print_q_table()

    # ── 최선 행동 요약 ────────────────────────────────
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
