# -*- coding: utf-8 -*-
"""카드축 — K 파라미터화.

- Legacy8 : 레거시와 동일 (preflop Chen 8구간 / postflop treys 완성핸드 순위 백분위 8구간).
            0단 등가성 게이트 + **상대(페르소나) 전용 동결 축**.
- EHS(K)  : percentile E[HS] (Johanson et al. 2013). 경계는 사전계산 JSON
            (data/ehs_buckets_k{K}.json). 포스트플랍은 MC 롤아웃 추정 +
            canonical-key 캐시(키 파생 결정론 seed → 런·프로세스 무관 동일 배정).

주의: E[HS] 런타임 추정의 n_roll은 경계 산출과 동일해야 함(추정량 분포 = 경계 분포).
"""
import json
import random
import zlib
from bisect import bisect_right
from pathlib import Path

from treys import Card as TreysCard, Evaluator

_evaluator = Evaluator()
DATA_DIR = Path(__file__).resolve().parent / 'data'

# ── Legacy8 (레거시 abstraction.py 와 동일 로직) ──────────────────
_RANK_VAL = {'A': 10, 'K': 8, 'Q': 7, 'J': 6, 'T': 5,
             '9': 4.5, '8': 4, '7': 3.5, '6': 3,
             '5': 2.5, '4': 2, '3': 1.5, '2': 1}
_RANK_NUM = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
             '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}


def _chen_score(cards) -> float:
    r1, s1 = str(cards[0].rank), str(cards[0].suit)
    r2, s2 = str(cards[1].rank), str(cards[1].suit)
    n1, n2 = _RANK_NUM[r1], _RANK_NUM[r2]
    high = r1 if n1 >= n2 else r2
    hi_n, lo_n = max(n1, n2), min(n1, n2)
    suited, pair = (s1 == s2), (r1 == r2)
    score = _RANK_VAL[high]
    if pair:
        score = max(score * 2, 5)
    if suited:
        score += 2
    if not pair:
        gap = hi_n - lo_n - 1
        if   gap == 1: score -= 1
        elif gap == 2: score -= 2
        elif gap == 3: score -= 4
        elif gap >= 4: score -= 5
        if hi_n < 12 and gap <= 1:
            score += 1
    return score


def _chen_bucket8(score: float) -> int:
    # 레거시 State enum 순서: 0=PREMIUM(최강) … 7=TRASH(최약)
    if score >= 12: return 0
    if score >= 10: return 1
    if score >=  8: return 2
    if score >=  7: return 3
    if score >=  6: return 4
    if score >=  5: return 5
    if score >=  3: return 6
    return 7


def _treys_cards(pk_cards):
    return [TreysCard.new(repr(c)) for c in pk_cards]


def legacy8_state(pk_state, player_idx: int) -> int:
    """레거시 8버킷 (0=최강). 상대·평가 정책이 사용하는 동결 축."""
    hand = list(pk_state.hole_cards[player_idx])
    pub = [c for grp in pk_state.board_cards for c in grp]
    if not pub:
        return _chen_bucket8(_chen_score(hand))
    score = _evaluator.evaluate(_treys_cards(pub), _treys_cards(hand))
    percentile = score / 7462.0
    return min(7, int(percentile / 0.125))


class _RawCard:
    """'Ah' 같은 원문자열 → .rank/.suit 인터페이스 (Slumbot 어댑터용)."""
    __slots__ = ('rank', 'suit')

    def __init__(self, s: str):
        self.rank, self.suit = s[0], s[1]


class Legacy8:
    name = 'legacy8'
    n_states = 8

    def state_of(self, pk_state, player_idx: int) -> int:
        return legacy8_state(pk_state, player_idx)

    def bucket_raw(self, hole: list[str], board: list[str]) -> int:
        """카드 원문자열 버전 (외부 API 평가용) — state_of 와 동일 규칙."""
        if not board:
            return _chen_bucket8(_chen_score([_RawCard(c) for c in hole]))
        score = _evaluator.evaluate([TreysCard.new(c) for c in board],
                                    [TreysCard.new(c) for c in hole])
        return min(7, int(score / 7462.0 / 0.125))


# ── EHS(K) ────────────────────────────────────────────────────────
_ALL_RANKS = '23456789TJQKA'


def _canonical_label(hand) -> str:
    """홀카드 → 169 canonical 라벨 (예: 'AKs', 'T9o', 'QQ')."""
    r1, s1 = str(hand[0].rank), str(hand[0].suit)
    r2, s2 = str(hand[1].rank), str(hand[1].suit)
    if _RANK_NUM[r1] < _RANK_NUM[r2]:
        r1, r2 = r2, r1
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ('s' if s1 == s2 else 'o')


class EHS:
    """percentile E[HS] K버킷. 반환 버킷: 0=최약 … K-1=최강."""
    # 경계 산출과 동일 추정량 (precompute_ehs_buckets.py 기본값)
    N_ROLL = {3: 150, 4: 150, 5: 200}

    def __init__(self, k: int):
        path = DATA_DIR / f'ehs_buckets_k{k}.json'
        d = json.loads(path.read_text(encoding='utf-8'))
        assert d['meta']['K'] == k
        self.name = f'ehs{k}'
        self.n_states = k
        self._pre = {lbl: v['bucket'] for lbl, v in d['preflop'].items()}
        self._cuts = {3: d['flop']['cuts'], 4: d['turn']['cuts'],
                      5: d['river']['cuts']}
        self._cache: dict[tuple, float] = {}

    def state_of(self, pk_state, player_idx: int) -> int:
        hand = list(pk_state.hole_cards[player_idx])
        pub = [c for grp in pk_state.board_cards for c in grp]
        if not pub:
            return self._pre[_canonical_label(hand)]
        nb = len(pub)
        ehs = self._ehs(_treys_cards(hand), _treys_cards(pub))
        return bisect_right(self._cuts[nb], ehs)

    def bucket_raw(self, hole: list[str], board: list[str]) -> int:
        """카드 원문자열 버전 (외부 API 평가용) — state_of 와 동일 규칙."""
        if not board:
            return self._pre[_canonical_label([_RawCard(c) for c in hole])]
        ehs = self._ehs([TreysCard.new(c) for c in hole],
                        [TreysCard.new(c) for c in board])
        return bisect_right(self._cuts[len(board)], ehs)

    # canonical suit-패턴 키 (정수 압축: 카드당 6비트) + 키 파생 결정론 seed.
    # 캐시는 플랍(재사용률 高)에만 — 턴·리버는 키 공간이 넓어 히트 이득 < 메모리 비용.
    # 캐시 없이도 같은 키 → 같은 seed → 같은 E[HS] (배정 일관성 유지).
    @staticmethod
    def _canon_key(hand_t, board_t) -> int:
        cards = sorted(hand_t) + sorted(board_t)
        suit_map, key = {}, len(board_t)
        for c in cards:
            r = TreysCard.get_rank_int(c)
            s = TreysCard.get_suit_int(c)
            if s not in suit_map:
                suit_map[s] = len(suit_map)
            key = (key << 6) | (r << 2) | suit_map[s]
        return key

    def _ehs(self, hand_t, board_t) -> float:
        key = self._canon_key(hand_t, board_t)
        cacheable = (len(board_t) == 3)
        if cacheable:
            hit = self._cache.get(key)
            if hit is not None:
                return hit
        n_roll = self.N_ROLL[len(board_t)]
        rng = random.Random(zlib.crc32(key.to_bytes(8, 'big')) ^ 0x5EED)
        used = set(hand_t) | set(board_t)
        rest = [c for c in _FULL_TREYS if c not in used]
        need = 5 - len(board_t)
        acc = 0.0
        for _ in range(n_roll):
            draw = rng.sample(rest, 2 + need)
            board = board_t + draw[2:]
            sh = _evaluator.evaluate(board, hand_t)
            so = _evaluator.evaluate(board, draw[:2])
            acc += 1.0 if sh < so else (0.5 if sh == so else 0.0)
        v = acc / n_roll
        if cacheable:
            self._cache[key] = v
        return v


_FULL_TREYS = [TreysCard.new(r + s) for r in _ALL_RANKS for s in 'shdc']


def make_cards(name: str):
    if name == 'legacy8':
        return Legacy8()
    if name.startswith('ehs'):
        return EHS(int(name[3:]))
    raise SystemExit(f"unknown card axis '{name}' (legacy8 | ehs20 | ehs50)")
