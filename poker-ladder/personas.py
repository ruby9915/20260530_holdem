# -*- coding: utf-8 -*-
"""상대 정책 — **동결 축** (레거시와 동일, 사다리 전 단 불변).

- 학습 상대: PERSONA_POLICIES 5종 (라운드 공통 2행 정책) — 레거시 rulebased_personas.py
- 평가 상대: random + EVAL_TAG(라운드별 정책) — 레거시 base._RULE_POLICY
  ※ 학습 TAG(라운드 공통)와 평가 TAG(라운드별)는 서로 다른 정책 — 레거시 그대로 유지.
- 상대는 항상 legacy8 상태를 사용한다: 학습자 카드축을 바꿔도 상대 행동 불변(단일변수).
"""
import random

from actions import Action, legal_actions, execute_action
from cards import legacy8_state
from defs import Round, classify_opp_action, pk_to_round, pot_size

# legacy8 인덱스: 0=PREMIUM 1=STRONG 2=GOOD 3=DECENT 4=MEDIOCRE 5=WEAK 6=POOR 7=TRASH
_A = Action

PERSONA_POLICIES: dict[str, dict[bool, list[Action]]] = {
    #            PREM        STRONG      GOOD        DECENT      MEDIO       WEAK        POOR        TRASH
    'tag': {
        False: [_A.RAISE_100, _A.RAISE_75, _A.RAISE_50, _A.RAISE_25, _A.CHECK,   _A.CHECK,   _A.CHECK,   _A.CHECK],
        True:  [_A.RAISE_75,  _A.RAISE_50, _A.CALL,     _A.CALL,     _A.FOLD,    _A.FOLD,    _A.FOLD,    _A.FOLD],
    },
    'lag': {
        False: [_A.RAISE_100, _A.RAISE_75, _A.RAISE_75, _A.RAISE_50, _A.RAISE_25, _A.RAISE_25, _A.CHECK,  _A.CHECK],
        True:  [_A.RAISE_75,  _A.RAISE_50, _A.CALL,     _A.CALL,     _A.CALL,     _A.FOLD,     _A.FOLD,   _A.FOLD],
    },
    'man': {
        False: [_A.RAISE_100, _A.RAISE_100, _A.RAISE_75, _A.RAISE_75, _A.RAISE_50, _A.RAISE_50, _A.RAISE_25, _A.RAISE_25],
        True:  [_A.RAISE_100, _A.RAISE_75,  _A.RAISE_50, _A.CALL,     _A.CALL,     _A.CALL,     _A.CALL,     _A.FOLD],
    },
    'sta': {
        False: [_A.CHECK] * 8,
        True:  [_A.CALL, _A.CALL, _A.CALL, _A.CALL, _A.CALL, _A.CALL, _A.FOLD, _A.FOLD],
    },
    'nit': {
        False: [_A.RAISE_75, _A.RAISE_75, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK],
        True:  [_A.RAISE_75, _A.CALL,     _A.FOLD,  _A.FOLD,  _A.FOLD,  _A.FOLD,  _A.FOLD,  _A.FOLD],
    },
}
PERSONA_NAMES = tuple(PERSONA_POLICIES.keys())

# 평가 TAG — 레거시 base._RULE_POLICY (라운드별). vsTAG 수치의 정의.
EVAL_TAG: dict[tuple[Round, bool], list[Action]] = {
    (Round.PREFLOP, False): [_A.RAISE_100, _A.RAISE_75, _A.RAISE_50, _A.RAISE_25, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK],
    (Round.PREFLOP, True):  [_A.RAISE_100, _A.RAISE_75, _A.CALL, _A.CALL, _A.CALL, _A.FOLD, _A.FOLD, _A.FOLD],
    (Round.FLOP,    False): [_A.RAISE_100, _A.RAISE_75, _A.RAISE_50, _A.RAISE_25, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK],
    (Round.FLOP,    True):  [_A.RAISE_100, _A.RAISE_75, _A.CALL, _A.CALL, _A.FOLD, _A.FOLD, _A.FOLD, _A.FOLD],
    (Round.TURN,    False): [_A.RAISE_75, _A.RAISE_75, _A.RAISE_25, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK],
    (Round.TURN,    True):  [_A.RAISE_75, _A.RAISE_50, _A.CALL, _A.CALL, _A.FOLD, _A.FOLD, _A.FOLD, _A.FOLD],
    (Round.RIVER,   False): [_A.RAISE_75, _A.RAISE_50, _A.RAISE_25, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK, _A.CHECK],
    (Round.RIVER,   True):  [_A.RAISE_75, _A.RAISE_50, _A.CALL, _A.CALL, _A.FOLD, _A.FOLD, _A.FOLD, _A.FOLD],
}

_FALLBACK = [Action.CHECK, Action.CALL, Action.FOLD, Action.RAISE_25,
             Action.RAISE_50, Action.RAISE_75, Action.RAISE_100,
             Action.RAISE_ALLIN]


def _exec_policy_action(pk_state, action: Action) -> None:
    legal = legal_actions(pk_state)
    if action not in legal:
        action = next((a for a in _FALLBACK if a in legal), legal[0])
    execute_action(pk_state, action)


def random_action(pk_state) -> None:
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


def step_opponent(pk_state, opp_id: int, kind, prev_action_by_round: dict) -> None:
    """상대 1액션 + PrevAction 갱신. kind: 'random' | 'eval_tag' | persona dict."""
    r_before = pk_to_round(pk_state)
    pot_before = pot_size(pk_state)
    cca_before = pk_state.checking_or_calling_amount
    stack_before = pk_state.stacks[opp_id]
    max_to_amount = pk_state.max_completion_betting_or_raising_to_amount

    if kind == 'random':
        random_action(pk_state)
    else:
        s = legacy8_state(pk_state, opp_id)
        facing = cca_before > 0
        if kind == 'eval_tag':
            action = EVAL_TAG[(r_before, facing)][s]
        else:                                   # persona policy dict
            action = kind[facing][s]
        _exec_policy_action(pk_state, action)

    stack_after = pk_state.stacks[opp_id]
    invest = stack_before - stack_after
    was_allin = (stack_after == 0 and invest > cca_before + 1e-9) \
                or (max_to_amount == stack_before
                    and invest > cca_before + 1e-9
                    and stack_before == max_to_amount)
    pa = classify_opp_action(stack_before, stack_after, cca_before,
                             pot_before, was_allin=was_allin)
    if pa is not None:
        prev_action_by_round[r_before] = pa
