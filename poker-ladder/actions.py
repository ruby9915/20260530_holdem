# -*- coding: utf-8 -*-
"""행동축. 버전을 명시적으로 정의한다 — 플래그 누적 금지.

A8  = 레거시 8행동 (0단·1단): FOLD/CHECK/CALL + 팟비례 레이즈 4종 + ALLIN
A12 = 2단 (35절 개정 v2): + 오버벳 레이즈 4종 {1.5, 2, 3, 4}×팟 = 12행동
     (enum 인덱스는 A8 뒤에 연속 추가 — A8 Q-테이블과 인덱스 호환)
상대(페르소나)는 항상 A8 부분집합에서만 행동 — 학습자 행동축 변경에도 상대 불변.
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
    RAISE_150   = 8    # A12 전용 ↓
    RAISE_200   = 9
    RAISE_300   = 10
    RAISE_400   = 11

    def is_raise(self) -> bool:
        return self.value >= Action.RAISE_25.value


_RAISE_PCT = {
    Action.RAISE_25:  0.25,
    Action.RAISE_50:  0.50,
    Action.RAISE_75:  0.75,
    Action.RAISE_100: 1.00,
    Action.RAISE_150: 1.50,
    Action.RAISE_200: 2.00,
    Action.RAISE_300: 3.00,
    Action.RAISE_400: 4.00,
}

_RAISES = {
    'A8':  [Action.RAISE_25, Action.RAISE_50, Action.RAISE_75,
            Action.RAISE_100, Action.RAISE_ALLIN],
    'A12': [Action.RAISE_25, Action.RAISE_50, Action.RAISE_75,
            Action.RAISE_100, Action.RAISE_150, Action.RAISE_200,
            Action.RAISE_300, Action.RAISE_400, Action.RAISE_ALLIN],
}
N_ACTIONS_OF = {'A8': 8, 'A12': 12}    # Q-테이블 행 길이 (최대 인덱스+1)


def legal_actions(pk_state, version: str = 'A8') -> list[Action]:
    result = []
    if pk_state.can_fold():
        result.append(Action.FOLD)
    if pk_state.can_check_or_call():
        if pk_state.checking_or_calling_amount == 0:
            result.append(Action.CHECK)
        else:
            result.append(Action.CALL)
    if pk_state.can_complete_bet_or_raise_to():
        result.extend(_RAISES[version])
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
