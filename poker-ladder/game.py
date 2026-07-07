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
                       learner_id: int) -> float:
    """1 핸드 학습. credit ∈ {prop, pure}, vic ∈ {off, fixed, checktime}."""
    pk = make_game()
    pos = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev: dict = {}
    trace = []                                     # (r, s, pa, a, invest)

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
                legal = legal_actions(pk)
                stack_before = pk.stacks[learner_id]
                a = qt.softmax_action(r, pos, s, pa, legal, temperature)
                execute_action(pk, a)
                invest = float(stack_before - pk.stacks[learner_id])
                if credit == 'prop' and a == Action.CHECK and invest == 0:
                    if vic == 'fixed':
                        invest = float(vic_amount)
                    elif vic == 'checktime':
                        invest = vic_amount * pot_size(pk)
                trace.append((r, s, pa, a, invest))
            else:
                step_opponent(pk, opp_id, opponent_policy, prev)
        else:
            break

    payoff = float(pk.stacks[learner_id] - STARTING_STACK)

    if credit == 'pure':
        g = payoff
        for (r, s, pa, a, _inv) in reversed(trace):
            qt.update_mc(r, pos, s, pa, a, g)
            g = qt.gamma * g
    else:                                          # prop (clean)
        total = sum(inv for (_, _, _, _, inv) in trace)
        if total > 0:
            for (r, s, pa, a, inv) in trace:
                qt.update_mc(r, pos, s, pa, a, (inv / total) * payoff)
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
