"""
abstraction.py  (PrevAction 확장 버전)
─────────────────────────────────────────────────────────────────────
poker-pokerkit-ucb/abstraction.py 의 모든 기능을 그대로 유지하면서
**PrevAction** enum 과 분류 헬퍼 `classify_opp_action()` 을 추가했다.

추가 차원:
  ▸ PrevAction = 학습자가 결정을 내리기 직전, 같은 라운드에서 상대가
    마지막으로 한 액션의 4단계 압축 표현.
        NONE        : 라운드 첫 액션 (상대가 아직 안 움직임)
        CHECK_CALL  : check 또는 call (소극적)
        SMALL_RAISE : 추가 베팅 ≤ pot_before_action × 0.5
        BIG_RAISE   : 추가 베팅 >  pot_before_action × 0.5  또는 ALL-IN

분류 규약:
  ▸ classify_opp_action(stack_before, stack_after, cca_before,
                        pot_before, max_bet_after_threshold=None)
    상대가 한 액션 직전/직후의 스택, 콜 콜 액수, 팟 사이즈를 받아
    PrevAction 4종 중 하나를 반환한다.
  ▸ FOLD 는 라운드가 그대로 종료되므로 PrevAction 으로 인코딩하지 않는다
    (학습자가 다시 결정할 일이 없다).
"""
from enum import Enum
from treys import Card as TreysCard, Evaluator


# ── 베팅 라운드 (4개) ─────────────────────────────────────
class Round(Enum):
    PREFLOP = 0
    FLOP    = 1
    TURN    = 2
    RIVER   = 3


# ── 핸드 강도 버킷 (8개, 구간은 균등 12.5%) ──────
class State(Enum):
    PREMIUM  = 0
    STRONG   = 1
    GOOD     = 2
    DECENT   = 3
    MEDIOCRE = 4
    WEAK     = 5
    POOR     = 6
    TRASH    = 7


# ── 포지션 (2개 · 헤즈업: player 0 = BB, player 1 = SB) ──
class Position(Enum):
    BB = 0
    SB = 1


def pk_to_position(player_idx: int) -> Position:
    return Position.BB if player_idx == 0 else Position.SB


# ── 행동 (8개) ─────────────────────────────────────────
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


# ── PrevAction (4개) — 상대의 라운드 내 직전 액션 압축 ──
class PrevAction(Enum):
    NONE        = 0   # 라운드 시작, 상대 아직 미행동
    CHECK_CALL  = 1   # check 또는 call
    SMALL_RAISE = 2   # 추가 베팅 ≤ pot * 0.5
    BIG_RAISE   = 3   # 추가 베팅 >  pot * 0.5 또는 ALL-IN


# ─────────────────────────────────────────────────────────
# 1. 라운드 변환
# ─────────────────────────────────────────────────────────
def pk_to_round(pk_state) -> Round:
    idx = pk_state.street_index
    if idx is None or idx == 0: return Round.PREFLOP
    if idx == 1: return Round.FLOP
    if idx == 2: return Round.TURN
    return Round.RIVER


# ─────────────────────────────────────────────────────────
# 2. 핸드 강도 버킷
# ─────────────────────────────────────────────────────────
_RANK_VAL = {'A': 10, 'K': 8, 'Q': 7, 'J': 6, 'T': 5,
             '9': 4.5, '8': 4, '7': 3.5, '6': 3,
             '5': 2.5, '4': 2, '3': 1.5, '2': 1}
_RANK_NUM = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
             '7': 7, '8': 8, '9': 9, 'T': 10,
             'J': 11, 'Q': 12, 'K': 13, 'A': 14}


def _chen_score(cards) -> float:
    r1, s1 = str(cards[0].rank), str(cards[0].suit)
    r2, s2 = str(cards[1].rank), str(cards[1].suit)

    n1, n2  = _RANK_NUM[r1], _RANK_NUM[r2]
    high    = r1 if n1 >= n2 else r2
    hi_n, lo_n = max(n1, n2), min(n1, n2)
    suited  = (s1 == s2)
    pair    = (r1 == r2)

    score = _RANK_VAL[high]

    if pair:
        score = max(score * 2, 5)

    if suited:
        score += 2

    if not pair:
        gap = hi_n - lo_n - 1
        if   gap == 0: pass
        elif gap == 1: score -= 1
        elif gap == 2: score -= 2
        elif gap == 3: score -= 4
        else:          score -= 5

        if hi_n < 12 and gap <= 1:
            score += 1

    return score


def _chen_to_state(score: float) -> State:
    if score >= 12: return State.PREMIUM
    if score >= 10: return State.STRONG
    if score >=  8: return State.GOOD
    if score >=  7: return State.DECENT
    if score >=  6: return State.MEDIOCRE
    if score >=  5: return State.WEAK
    if score >=  3: return State.POOR
    return State.TRASH


_evaluator = Evaluator()


def _postflop_to_state(hand, pub) -> State:
    h = [TreysCard.new(repr(c)) for c in hand]
    p = [TreysCard.new(repr(c)) for c in pub]
    score      = _evaluator.evaluate(p, h)
    percentile = score / 7462.0
    if percentile < 0.125: return State.PREMIUM
    if percentile < 0.250: return State.STRONG
    if percentile < 0.375: return State.GOOD
    if percentile < 0.500: return State.DECENT
    if percentile < 0.625: return State.MEDIOCRE
    if percentile < 0.750: return State.WEAK
    if percentile < 0.875: return State.POOR
    return State.TRASH


def pk_to_state(pk_state, player_idx: int) -> State:
    hand = list(pk_state.hole_cards[player_idx])
    pub = [c for grp in pk_state.board_cards for c in grp]

    if len(pub) == 0:
        return _chen_to_state(_chen_score(hand))
    return _postflop_to_state(hand, pub)


# ─────────────────────────────────────────────────────────
# 3. 합법 행동 목록
# ─────────────────────────────────────────────────────────
def legal_our_actions(pk_state) -> list[Action]:
    result = []

    if pk_state.can_fold():
        result.append(Action.FOLD)

    if pk_state.can_check_or_call():
        if pk_state.checking_or_calling_amount == 0:
            result.append(Action.CHECK)
        else:
            result.append(Action.CALL)

    if pk_state.can_complete_bet_or_raise_to():
        result.extend([
            Action.RAISE_25,
            Action.RAISE_50,
            Action.RAISE_75,
            Action.RAISE_100,
            Action.RAISE_ALLIN,
        ])

    return result


# ─────────────────────────────────────────────────────────
# 4. 액션 실행
# ─────────────────────────────────────────────────────────
_RAISE_PCT = {
    Action.RAISE_25:  0.25,
    Action.RAISE_50:  0.50,
    Action.RAISE_75:  0.75,
    Action.RAISE_100: 1.00,
}


def execute_action(pk_state, action: Action) -> None:
    if action == Action.FOLD:
        pk_state.fold()

    elif action in (Action.CHECK, Action.CALL):
        pk_state.check_or_call()

    elif action == Action.RAISE_ALLIN:
        pk_state.complete_bet_or_raise_to(
            pk_state.max_completion_betting_or_raising_to_amount
        )

    else:
        pct       = _RAISE_PCT[action]
        total_pot = (sum(pot.amount for pot in pk_state.pots)
                     + sum(pk_state.bets))
        raise_size      = max(1, int(total_pot * pct))
        current_max_bet = max(pk_state.bets) if pk_state.bets else 0
        target = current_max_bet + raise_size
        target = max(target, pk_state.min_completion_betting_or_raising_to_amount)
        target = min(target, pk_state.max_completion_betting_or_raising_to_amount)
        pk_state.complete_bet_or_raise_to(target)


# ─────────────────────────────────────────────────────────
# 5. PrevAction 분류
# ─────────────────────────────────────────────────────────
def classify_opp_action(stack_before: float,
                        stack_after: float,
                        cca_before: float,
                        pot_before: float,
                        was_allin: bool = False) -> "PrevAction | None":
    """
    상대가 막 행한 액션 한 건을 PrevAction 4종으로 분류.

    인자:
      stack_before / stack_after : 상대 스택 (액션 직전/직후)
      cca_before                 : 액션 직전 상대가 콜로 맞춰야 했던 금액
                                   (상대 시점의 checking_or_calling_amount)
      pot_before                 : 액션 직전 총 팟 = sum(pots) + sum(bets)
                                   (상대의 이번 추가 베팅은 미포함)
      was_allin                  : 상대가 자신의 가용 스택을 모두 밀었는지

    반환:
      PrevAction (NONE 제외) 또는 None (FOLD 인 경우).
      FOLD 후에는 학습자가 그 라운드에 다시 결정하지 않으므로 None 반환.
    """
    invest = float(stack_before - stack_after)

    # FOLD: 콜이 필요한 상황(cca_before>0)에서 칩을 안 냈으면 폴드
    if invest == 0 and cca_before > 0:
        return None

    # CHECK / CALL: 콜 액수만 정확히 냈거나(>0=call) 0(=check)
    if invest <= cca_before + 1e-9:
        return PrevAction.CHECK_CALL

    # RAISE: 콜 위에 추가 베팅한 금액이 있다
    extra = invest - cca_before  # 라이즈로 더 얹은 칩
    if was_allin or pot_before <= 0:
        return PrevAction.BIG_RAISE
    pct = extra / pot_before
    return PrevAction.SMALL_RAISE if pct <= 0.5 else PrevAction.BIG_RAISE
