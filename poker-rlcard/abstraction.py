"""
abstraction.py
─────────────────────────────────────────────────────────────────────
RLCard의 raw_obs(원시 관측) → 우리 Q-테이블 인덱스(Round, State, Action)로
변환하는 추상화 계층.

Java 프로젝트(poker-qlearning)의 enum 3종을 그대로 옮겨오고,
추가로 변환 함수를 제공한다.
"""
from enum import Enum
from treys import Card as TreysCard, Evaluator


# ── 베팅 라운드 (4개) ─────────────────────────────────────
class Round(Enum):
    PREFLOP = 0
    FLOP    = 1
    TURN    = 2
    RIVER   = 3


# ── 핸드 강도 버킷 (5개, 100분율을 5구간으로 나눔) ────────
#   STRONG   : 상위  0~20%  (AA, KK, QQ, AKs ...)
#   GOOD     : 상위 20~40%
#   MARGINAL : 상위 40~60%
#   WEAK     : 상위 60~80%
#   TRASH    : 하위 80~100% (72o 등)
class State(Enum):
    STRONG   = 0
    GOOD     = 1
    MARGINAL = 2
    WEAK     = 3
    TRASH    = 4


# ── 행동 (Java enum과 동일한 8개) ─────────────────────────
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


# ─────────────────────────────────────────────────────────
# 1. 라운드 변환
# ─────────────────────────────────────────────────────────
def obs_to_round(raw_obs) -> Round:
    """
    RLCard의 stage 필드 또는 public_cards 개수로 라운드 판별.
    공개 카드 수: PREFLOP=0, FLOP=3, TURN=4, RIVER=5
    """
    stage = raw_obs.get('stage')
    if stage is not None:
        # stage는 enum (Stage.PREFLOP 등)이므로 name으로 비교
        name = stage.name if hasattr(stage, 'name') else str(stage)
        if 'PREFLOP' in name: return Round.PREFLOP
        if 'FLOP'    in name and 'PRE' not in name: return Round.FLOP
        if 'TURN'    in name: return Round.TURN
        if 'RIVER'   in name: return Round.RIVER

    # fallback: 공개 카드 수로 판별
    n = len(raw_obs.get('public_cards', []))
    if n == 0: return Round.PREFLOP
    if n == 3: return Round.FLOP
    if n == 4: return Round.TURN
    return Round.RIVER


# ─────────────────────────────────────────────────────────
# 2. 상태(핸드 강도 버킷) 변환
# ─────────────────────────────────────────────────────────
# Chen formula로 프리플랍 핸드 강도 평가 (간이 버전)
#   AA = 20점(최강), 72o = -1점(최약) 근방
_RANK_VAL = {'A': 10, 'K': 8, 'Q': 7, 'J': 6, 'T': 5,
            '9': 4.5, '8': 4, '7': 3.5, '6': 3,
            '5': 2.5, '4': 2, '3': 1.5, '2': 1}
_RANK_NUM = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
            'T':10,'J':11,'Q':12,'K':13,'A':14}

def _chen_score(hand: list[str]) -> float:
    """RLCard 카드 표기('C9', 'DT' = 슈트+랭크)에서 Chen 점수 계산"""
    # 카드 포맷: 첫 글자=슈트(C/D/H/S), 둘째 글자=랭크
    s1, r1 = hand[0][0], hand[0][1]
    s2, r2 = hand[1][0], hand[1][1]

    n1, n2 = _RANK_NUM[r1], _RANK_NUM[r2]
    high, low = max(n1, n2), min(n1, n2)
    suited = (s1 == s2)
    pair   = (r1 == r2)

    # 1) 높은 카드 기본 점수
    high_rank = r1 if n1 >= n2 else r2
    score = _RANK_VAL[high_rank]

    # 2) 페어: 점수 2배, 최소 5점(22 → 5)
    if pair:
        score = max(score * 2, 5)

    # 3) 수티드 보너스 +2
    if suited:
        score += 2

    # 4) 갭 페널티
    if not pair:
        gap = high - low - 1   # AK는 갭 0, A2는 갭 11
        if   gap == 0: score += 0
        elif gap == 1: score -= 1
        elif gap == 2: score -= 2
        elif gap == 3: score -= 4
        else:          score -= 5

        # 5) 양쪽 모두 Q 미만 + 갭 0~1 + 페어 아님 → +1 (커넥터 보너스)
        if high < 12 and gap <= 1:
            score += 1

    return score


def _chen_to_state(score: float) -> State:
    """Chen 점수를 5버킷으로 매핑"""
    if score >= 10: return State.STRONG
    if score >= 8:  return State.GOOD
    if score >= 6:  return State.MARGINAL
    if score >= 4:  return State.WEAK
    return State.TRASH


# 포스트플랍은 treys 라이브러리로 핸드 강도 평가
_evaluator = Evaluator()

def _rlcard_to_treys(card: str) -> int:
    """'C9' (슈트+랭크) → treys '9c' (랭크+소문자슈트)"""
    suit, rank = card[0], card[1]
    return TreysCard.new(rank + suit.lower())


def _postflop_to_state(hand: list[str], pub: list[str]) -> State:
    """
    treys.evaluate()는 1(로열플러시)~7462(하이카드 최약)의 정수를 반환.
    1.0 / 7462 ≈ 0.0(강) ~ 1.0(약)로 정규화 후 5버킷 매핑.
    """
    h = [_rlcard_to_treys(c) for c in hand]
    p = [_rlcard_to_treys(c) for c in pub]
    score = _evaluator.evaluate(p, h)
    percentile = score / 7462.0
    if percentile < 0.20: return State.STRONG
    if percentile < 0.40: return State.GOOD
    if percentile < 0.60: return State.MARGINAL
    if percentile < 0.80: return State.WEAK
    return State.TRASH


def obs_to_state(raw_obs) -> State:
    """라운드에 따라 분기: PREFLOP은 Chen, 그 외는 treys"""
    hand = raw_obs['hand']
    pub  = raw_obs.get('public_cards', [])

    if len(pub) == 0:
        return _chen_to_state(_chen_score(hand))
    return _postflop_to_state(hand, pub)


# ─────────────────────────────────────────────────────────
# 3. 액션 매핑 (우리 8개 ↔ RLCard 5개)
# ─────────────────────────────────────────────────────────
# RLCard no-limit-holdem 액션 정수값:
#   0 = FOLD, 1 = CHECK_CALL, 2 = RAISE_HALF_POT,
#   3 = RAISE_POT, 4 = ALL_IN
RLCARD_FOLD       = 0
RLCARD_CHECK_CALL = 1
RLCARD_RAISE_HALF = 2
RLCARD_RAISE_POT  = 3
RLCARD_ALL_IN     = 4

# 우리 Action → RLCard 정수
#   RAISE_25/50 → HALF, RAISE_75/100 → POT으로 묶어서 매핑
#   (RLCard는 정확한 % 베팅을 지원하지 않으므로 가장 가까운 옵션 사용)
ACTION_TO_RLCARD = {
    Action.FOLD       : RLCARD_FOLD,
    Action.CHECK      : RLCARD_CHECK_CALL,
    Action.CALL       : RLCARD_CHECK_CALL,
    Action.RAISE_25   : RLCARD_RAISE_HALF,
    Action.RAISE_50   : RLCARD_RAISE_HALF,
    Action.RAISE_75   : RLCARD_RAISE_POT,
    Action.RAISE_100  : RLCARD_RAISE_POT,
    Action.RAISE_ALLIN: RLCARD_ALL_IN,
}


def legal_our_actions(raw_obs) -> list[Action]:
    """
    RLCard가 알려주는 합법 행동(legal_actions) → 우리 Action 리스트로 변환.
    CHECK_CALL은 현재 베팅 콜 액수에 따라 CHECK 또는 CALL 둘 다 등록 가능.
    """
    legal_set = {int(a.value) if hasattr(a, 'value') else int(a)
                for a in raw_obs['legal_actions']}

    # 콜할 금액이 있는지 확인 (my_chips < max(all_chips)면 콜이 필요)
    my_chips  = raw_obs.get('my_chips', 0)
    all_chips = raw_obs.get('all_chips', [my_chips])
    need_call = max(all_chips) > my_chips

    result = []
    for our_a, rl_a in ACTION_TO_RLCARD.items():
        if rl_a not in legal_set:
            continue
        # CHECK_CALL 분기: 콜 금액 유무에 따라 CHECK/CALL 둘 중 하나만 유효
        if rl_a == RLCARD_CHECK_CALL:
            if our_a == Action.CHECK and need_call:
                continue
            if our_a == Action.CALL and not need_call:
                continue
        result.append(our_a)
    return result
