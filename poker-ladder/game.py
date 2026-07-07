# -*- coding: utf-8 -*-
"""에피소드 실행 — 게임 구성·학습/평가 루프 (레거시 의미론 동일).

학습 credit 규약 (전 조건 clean — 누수 폴백 없음):
  PROP      : R(a) = invest(a)/Σinvest × payoff.  Σinvest==0(가상 포함)이면 갱신 생략.
  VIC off   : CHECK invest = 0
  VIC fixed : CHECK invest = K칩 (invest==0인 CHECK에만)
  VIC checktime : CHECK invest = α × (체크 시점 팟)
  PURE      : G = γ^(뒤에서 t번째) × payoff 역전파 (invest 미사용 — VIC inert)
"""
from pokerkit import Automation, NoLimitTexasHoldem

from actions import Action, legal_actions, execute_action
from defs import PrevAction, pk_to_position, pk_to_round, pot_size
from personas import step_opponent

STARTING_STACK = 200
SMALL_BLIND    = 1
BIG_BLIND      = 2

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


def make_game():
    return NoLimitTexasHoldem.create_state(
        _AUTOMATIONS, True, 0, (SMALL_BLIND, BIG_BLIND), BIG_BLIND,
        (STARTING_STACK, STARTING_STACK), 2)


def play_train_episode(qt, cards, opponent_policy, temperature: float,
                       credit: str, vic: str, vic_amount: float,
                       learner_id: int, pot_apply: str = 'all',
                       uniform_penalty: float = 0.0) -> float:
    """1 핸드 학습. credit ∈ {prop, pure}, vic ∈ {off, fixed, checktime, terminal}.

    pot_apply (E1 격리 재현): all | invested_only | allcheck_only
    uniform_penalty (E8-③ 재현): 모든 credit 에서 상수 감산
    """
    pk = make_game()
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev: dict = {}
    trace = []                                     # (r, s, pa, a, invest|None)
    pot_peak = 0.0
    real_total = 0.0                               # 실투자 합 (가상 제외)

    while pk.status:
        if vic == 'terminal':
            pot_peak = max(pot_peak, pot_size(pk))
        if pk.can_deal_hole():
            pk.deal_hole()
        elif pk.can_deal_board():
            pk.deal_board()
        elif pk.actor_index is not None:
            if pk.actor_index == learner_id:
                r = pk_to_round(pk)
                s = cards.state_of(pk, learner_id)
                pa = prev.get(r, PrevAction.NONE)
                legal = legal_actions(pk)
                stack_before = pk.stacks[learner_id]
                a = qt.softmax_action(r, pos, s, pa, legal, temperature)
                execute_action(pk, a)
                invest = float(stack_before - pk.stacks[learner_id])
                real_total += invest
                if credit == 'prop' and a == Action.CHECK and invest == 0:
                    if vic == 'fixed':
                        invest = float(vic_amount)
                    elif vic == 'checktime':
                        invest = vic_amount * pot_size(pk)
                    elif vic == 'terminal':
                        invest = None              # 종료 후 α×최종팟으로 채움
                trace.append((r, s, pa, a, invest))
            else:
                step_opponent(pk, opp_id, opponent_policy, prev)
        else:
            break

    if vic == 'terminal':
        vinv = vic_amount * pot_peak
        trace = [(r, s, pa, a, (vinv if inv is None else inv))
                 for (r, s, pa, a, inv) in trace]

    payoff = float(pk.stacks[learner_id] - STARTING_STACK)

    if credit == 'pure':
        g = payoff
        for (r, s, pa, a, _inv) in reversed(trace):
            qt.update_mc(r, pos, s, pa, a, g)
            g = qt.gamma * g
        return payoff

    # ── prop (clean) ── E1 격리: 올체크-핸드 신호 분리 (레거시 의미론 동일)
    if pot_apply == 'invested_only' and real_total == 0:
        return payoff                              # 올체크 핸드 갱신 생략
    if pot_apply == 'allcheck_only':
        if real_total > 0:                         # 실투자 핸드: CHECK credit 0
            trace = [(r, s, pa, a, (0.0 if a == Action.CHECK else inv))
                     for (r, s, pa, a, inv) in trace]
        else:                                      # 올체크: 균등분배(옛 누수 신호)만
            n = len(trace)
            if n:
                g = payoff / n
                for (r, s, pa, a, _inv) in trace:
                    qt.update_mc(r, pos, s, pa, a, g)
            return payoff

    total = sum(inv for (_, _, _, _, inv) in trace)
    if total > 0:
        for (r, s, pa, a, inv) in trace:
            qt.update_mc(r, pos, s, pa, a,
                         (inv / total) * payoff - uniform_penalty)
    return payoff


def play_eval_episode(qt, cards, opponent_kind: str, learner_id: int) -> float:
    """greedy 1 핸드 (Q 갱신 없음). opponent_kind: 'random' | 'eval_tag'."""
    pk = make_game()
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev: dict = {}

    while pk.status:
        if pk.can_deal_hole():
            pk.deal_hole()
        elif pk.can_deal_board():
            pk.deal_board()
        elif pk.actor_index is not None:
            if pk.actor_index == learner_id:
                r = pk_to_round(pk)
                s = cards.state_of(pk, learner_id)
                pa = prev.get(r, PrevAction.NONE)
                a = qt.best_action(r, pos, s, pa, legal_actions(pk))
                execute_action(pk, a)
            else:
                step_opponent(pk, opp_id, opponent_kind, prev)
        else:
            break
    return float(pk.stacks[learner_id] - STARTING_STACK)
