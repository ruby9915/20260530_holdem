# -*- coding: utf-8 -*-
"""행동축. 버전을 명시적으로 정의한다 — 플래그 누적 금지.

A8  = 레거시 8행동 (0단·1단): FOLD/CHECK/CALL + 팟비례 레이즈 4종 + ALLIN
A12 = 2단 예정: 레이즈 8종 {0.25,0.5,0.75,1,1.5,2,3,4} (35절 개정 v2)
"""
from enum import Enum


class Action(Enum):
    FOLD        = 0
    CHECK       = 1
    CALL        = 2
    RAISE_25    = 3
    RAISE_50    = 4
    RAISE_75    = 5
    RAISE_100   = 6
    RAISE_ALLIN = 7

    def is_raise(self) -> bool:
        return self.value >= Action.RAISE_25.value


_RAISE_PCT = {
    Action.RAISE_25:  0.25,
    Action.RAISE_50:  0.50,
    Action.RAISE_75:  0.75,
    Action.RAISE_100: 1.00,
}

ACTION_VERSION = 'A8'
N_ACTIONS = len(Action)


def legal_actions(pk_state) -> list[Action]:
    result = []
    if pk_state.can_fold():
        result.append(Action.FOLD)
    if pk_state.can_check_or_call():
        if pk_state.checking_or_calling_amount == 0:
            result.append(Action.CHECK)
        else:
            result.append(Action.CALL)
    if pk_state.can_complete_bet_or_raise_to():
        result.extend([Action.RAISE_25, Action.RAISE_50, Action.RAISE_75,
                       Action.RAISE_100, Action.RAISE_ALLIN])
    return result


def execute_action(pk_state, action: Action) -> None:
    if action == Action.FOLD:
        pk_state.fold()
    elif action in (Action.CHECK, Action.CALL):
        pk_state.check_or_call()
    elif action == Action.RAISE_ALLIN:
        pk_state.complete_bet_or_raise_to(
            pk_state.max_completion_betting_or_raising_to_amount)
    else:
        pct = _RAISE_PCT[action]
        total_pot = (sum(pot.amount for pot in pk_state.pots)
                     + sum(pk_state.bets))
        raise_size = max(1, int(total_pot * pct))
        current_max_bet = max(pk_state.bets) if pk_state.bets else 0
        target = current_max_bet + raise_size
        target = max(target, pk_state.min_completion_betting_or_raising_to_amount)
        target = min(target, pk_state.max_completion_betting_or_raising_to_amount)
        pk_state.complete_bet_or_raise_to(target)
