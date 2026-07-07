# -*- coding: utf-8 -*-
"""공통 정의: Round / Position / PrevAction + pokerkit 변환·상대행동 분류.

레거시 poker-pokerkit-prev/abstraction.py 와 의미 동일(0단 등가성의 전제).
이 축들은 사다리 전 단에서 불변이다.
"""
from enum import Enum


class Round(Enum):
    PREFLOP = 0
    FLOP    = 1
    TURN    = 2
    RIVER   = 3


class Position(Enum):
    BB = 0   # 헤즈업: player 0 = BB
    SB = 1


class PrevAction(Enum):
    NONE        = 0   # 라운드 시작, 상대 미행동
    CHECK_CALL  = 1
    SMALL_RAISE = 2   # 추가 베팅 ≤ pot×0.5
    BIG_RAISE   = 3   # 초과 또는 ALL-IN


def pk_to_round(pk_state) -> Round:
    idx = pk_state.street_index
    if idx is None or idx == 0: return Round.PREFLOP
    if idx == 1: return Round.FLOP
    if idx == 2: return Round.TURN
    return Round.RIVER


def pk_to_position(player_idx: int) -> Position:
    return Position.BB if player_idx == 0 else Position.SB


def classify_opp_action(stack_before, stack_after, cca_before, pot_before,
                        was_allin: bool = False):
    """상대의 액션 1건 → PrevAction (FOLD은 None: 학습자 재결정 없음)."""
    invest = float(stack_before - stack_after)
    if invest == 0 and cca_before > 0:
        return None                       # FOLD
    if invest <= cca_before + 1e-9:
        return PrevAction.CHECK_CALL
    extra = invest - cca_before
    if was_allin or pot_before <= 0:
        return PrevAction.BIG_RAISE
    return (PrevAction.SMALL_RAISE if extra / pot_before <= 0.5
            else PrevAction.BIG_RAISE)


def pot_size(pk_state) -> float:
    return sum(p.amount for p in pk_state.pots) + sum(pk_state.bets)
