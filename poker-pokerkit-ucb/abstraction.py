"""
abstraction.py
─────────────────────────────────────────────────────────────────────
PokerKit game state → Q-테이블 인덱스(Round, State, Action)로 변환하는
추상화 계층.

poker-rlcard/abstraction.py 와 동일한 enum 구조를 유지하되,
RLCard 의존성을 완전히 제거하고 PokerKit 네이티브 API를 사용.

핵심 차이:
  ▸ RLCard : 베팅 5종(FOLD/CHECK_CALL/HALF/POT/ALLIN) — RAISE_25/50/75/100 구분 불가
  ▸ PokerKit: complete_bet_or_raise_to(amount) — 팟 % 금액을 직접 계산해 전달
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
    PREMIUM  = 0   # 상위   0~12.5%
    STRONG   = 1   # 상위 12.5~25%
    GOOD     = 2   # 상위 25~37.5%
    DECENT   = 3   # 상위 37.5~50%
    MEDIOCRE = 4   # 상위 50~62.5%
    WEAK     = 5   # 상위 62.5~75%
    POOR     = 6   # 상위 75~87.5%
    TRASH    = 7   # 하위 87.5~100%


# ── 포지션 (2개 · PokerKit 헤즈업: player 0 = BB, player 1 = SB) ──
class Position(Enum):
    BB = 0
    SB = 1


def pk_to_position(player_idx: int) -> Position:
    """PokerKit 헤즈업 규약: player 0 = BB, player 1 = button/SB."""
    return Position.BB if player_idx == 0 else Position.SB


# ── 행동 (Java enum · RLCard 버전과 동일한 8개) ───────────
class Action(Enum):
    FOLD        = 0
    CHECK       = 1
    CALL        = 2
    RAISE_25    = 3   # 팟의 25% 베팅  ← PokerKit에서 정확히 지원
    RAISE_50    = 4   # 팟의 50% 베팅
    RAISE_75    = 5   # 팟의 75% 베팅
    RAISE_100   = 6   # 팟의 100% 베팅 (팟 베팅)
    RAISE_ALLIN = 7   # 올인

    def is_raise(self) -> bool:
        return self.value >= Action.RAISE_25.value


# ─────────────────────────────────────────────────────────
# 1. 라운드 변환
# ─────────────────────────────────────────────────────────
def pk_to_round(pk_state) -> Round:
    """
    PokerKit state.street_index 로 라운드 판별.
    0 = PREFLOP, 1 = FLOP, 2 = TURN, 3 = RIVER
    """
    idx = pk_state.street_index
    if idx is None or idx == 0: return Round.PREFLOP
    if idx == 1: return Round.FLOP
    if idx == 2: return Round.TURN
    return Round.RIVER


# ─────────────────────────────────────────────────────────
# 2. 상태(핸드 강도 버킷) 변환
# ─────────────────────────────────────────────────────────
# Chen formula 상수 — 랭크 문자 기준 (PokerKit repr 과 동일)
_RANK_VAL = {'A': 10, 'K': 8, 'Q': 7, 'J': 6, 'T': 5,
             '9': 4.5, '8': 4, '7': 3.5, '6': 3,
             '5': 2.5, '4': 2, '3': 1.5, '2': 1}
_RANK_NUM = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
             '7': 7, '8': 8, '9': 9, 'T': 10,
             'J': 11, 'Q': 12, 'K': 13, 'A': 14}


def _chen_score(cards) -> float:
    """
    PokerKit Card 객체 2장에서 Chen 점수 계산.
    card.rank = 'A'/'K'/..'2', card.suit = 'c'/'d'/'h'/'s'
    """
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
    # Chen 점수 범위는 대략 -1 ~ 20. 8구간 임계값을 경험적으로 설정.
    if score >= 12: return State.PREMIUM
    if score >= 10: return State.STRONG
    if score >=  8: return State.GOOD
    if score >=  7: return State.DECENT
    if score >=  6: return State.MEDIOCRE
    if score >=  5: return State.WEAK
    if score >=  3: return State.POOR
    return State.TRASH


# 포스트플랍 평가기
_evaluator = Evaluator()


def _postflop_to_state(hand, pub) -> State:
    """
    PokerKit Card 객체 리스트 → treys 변환 후 8버킷 매핑 (균등 12.5% 구간).
    repr(card) 는 'Ac', '9h' 처럼 rank+suit(소문자) 포맷 → treys 와 동일.
    """
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
    """
    라운드에 따라 분기:
      PREFLOP → Chen formula
      FLOP/TURN/RIVER → treys 7-card evaluator
    """
    hand = list(pk_state.hole_cards[player_idx])
    # board_cards: [[c1,c2,c3], [c4], [c5]] 구조를 평탄화
    pub = [c for grp in pk_state.board_cards for c in grp]

    if len(pub) == 0:
        return _chen_to_state(_chen_score(hand))
    return _postflop_to_state(hand, pub)


# ─────────────────────────────────────────────────────────
# 3. 합법 행동 목록
# ─────────────────────────────────────────────────────────
def legal_our_actions(pk_state) -> list[Action]:
    """
    현재 상태에서 가능한 우리 Action 리스트 반환.
    PokerKit can_fold / can_check_or_call / can_complete_bet_or_raise_to 활용.
    """
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
# 4. 액션 실행 (PokerKit 네이티브 호출)
# ─────────────────────────────────────────────────────────
# 팟 % 베팅 비율 매핑
_RAISE_PCT = {
    Action.RAISE_25:  0.25,
    Action.RAISE_50:  0.50,
    Action.RAISE_75:  0.75,
    Action.RAISE_100: 1.00,
}


def execute_action(pk_state, action: Action) -> None:
    """
    우리 Action → PokerKit 네이티브 함수 실행.

    팟 % 계산:
        total_pot  = 수집된 팟 합계 + 현재 라운드 베팅 합계
        raise_size = int(total_pot * pct)   (최소: 1칩)
        target     = max(min_raise, current_max_bet + raise_size)
        target     = min(target, all_in_amount)
    """
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
