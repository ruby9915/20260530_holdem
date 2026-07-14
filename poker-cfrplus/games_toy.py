# -*- coding: utf-8 -*-
"""검증용 소형 게임 — Kuhn poker(해석해 존재) / Leduc hold'em(문헌 기준치).

히스토리 h = (c0, c1, board, acts) 튜플. acts = 행동 문자열
  'k' 체크 · 'b' 벳 · 'c' 콜 · 'r' 레이즈 · 'f' 폴드 · '/' 라운드 경계(Leduc)
util0 = 플레이어 0 의 순수익(칩).
"""
import itertools


class Kuhn:
    """3장(J=0,Q=1,K=2) 쿤 포커. 안테 1, 벳 1. 내쉬 게임가치(P0) = −1/18."""

    def initial(self):
        return None                              # 찬스(딜) 전

    def is_chance(self, h):
        return h is None

    def chance(self, h):
        deals = list(itertools.permutations([0, 1, 2], 2))
        return [((c0, c1), 1.0 / len(deals)) for c0, c1 in deals]

    def next(self, h, a):
        if h is None:
            return (a[0], a[1], '')
        return (h[0], h[1], h[2] + a)

    def is_terminal(self, h):
        if h is None:
            return False
        acts = h[2]
        return acts in ('kk', 'bc', 'bf', 'kbc', 'kbf')

    def util0(self, h):
        c0, c1, acts = h
        win = 1 if c0 > c1 else -1
        if acts == 'kk':
            return win                            # 안테만
        if acts == 'bf':
            return 1                              # P1 폴드
        if acts == 'kbf':
            return -1                             # P0 폴드
        return 2 * win                            # bc / kbc — 쇼다운(안테+벳)

    def player(self, h):
        return len(h[2]) % 2

    def actions(self, h):
        acts = h[2]
        if acts in ('', 'k'):
            return ['k', 'b']
        return ['c', 'f']                         # 벳 직면

    def infoset(self, h):
        card = h[0] if self.player(h) == 0 else h[1]
        return (card, h[2])


class Leduc:
    """Leduc hold'em: 6장(J,Q,K ×2), 안테 1, 1라운드 벳 2·2라운드 벳 4,
    라운드당 최대 2벳(벳+레이즈). 페어 우선, 동순위 무승부."""

    DECK = [0, 0, 1, 1, 2, 2]                     # 랭크만 (수트 무관 게임)

    def initial(self):
        return None

    def is_chance(self, h):
        if h is None:
            return True
        c0, c1, board, acts = h
        return board is None and self._round_over(acts, 0)

    def chance(self, h):
        if h is None:
            deals = {}
            for i, j in itertools.permutations(range(6), 2):
                key = (self.DECK[i], self.DECK[j])
                deals[key] = deals.get(key, 0) + 1
            tot = sum(deals.values())
            return [((c0, c1, None, ''), n / tot) for (c0, c1), n in deals.items()]
        c0, c1, _, acts = h
        rest = list(self.DECK)
        rest.remove(c0); rest.remove(c1)
        outs = {}
        for b in rest:
            outs[b] = outs.get(b, 0) + 1
        tot = sum(outs.values())
        return [((c0, c1, b, acts + '/'), n / tot) for b, n in outs.items()]

    def next(self, h, a):
        if self.is_chance(h):
            return a                              # chance() 가 후속 h 자체를 반환
        c0, c1, board, acts = h
        return (c0, c1, board, acts + a)

    # ── 라운드 파싱 ────────────────────────────────────────
    @staticmethod
    def _split(acts):
        return acts.split('/') if '/' in acts else [acts]

    @staticmethod
    def _round_over(acts, rd):
        seg = Leduc._split(acts)[rd] if rd < len(Leduc._split(acts)) else ''
        return seg in ('kk', 'bc', 'brc', 'kbc', 'kbrc')

    def is_terminal(self, h):
        if h is None or self.is_chance(h):
            return False
        c0, c1, board, acts = h
        segs = self._split(acts)
        if segs[-1].endswith('f'):
            return True
        return len(segs) == 2 and self._round_over(acts, 1)

    def _invested(self, acts):
        """행동열로부터 (p0, p1) 총 투입 계산 (안테 1 포함)."""
        inv = [1.0, 1.0]
        segs = self._split(acts)
        for rd, seg in enumerate(segs):
            size = 2.0 if rd == 0 else 4.0
            owe = [0.0, 0.0]
            p = 0
            for ch in seg:
                if ch == 'k':
                    pass
                elif ch == 'b':
                    inv[p] += size; owe[1 - p] = size
                elif ch == 'r':
                    inv[p] += owe[p] + size
                    owe[p] = 0; owe[1 - p] = size
                elif ch == 'c':
                    inv[p] += owe[p]; owe[p] = 0
                elif ch == 'f':
                    pass
                p = 1 - p
        return inv

    def util0(self, h):
        c0, c1, board, acts = h
        inv = self._invested(acts)
        segs = self._split(acts)
        if segs[-1].endswith('f'):
            folder = (len(segs[-1]) - 1) % 2      # 접은 플레이어 (라운드 첫 액터=0)
            return inv[1] if folder == 1 else -inv[0]
        r0 = 3 + c0 if c0 == board else c0        # 페어 > 하이카드
        r1 = 3 + c1 if c1 == board else c1
        if r0 == r1:
            return 0.0
        return inv[1] if r0 > r1 else -inv[0]

    def player(self, h):
        seg = self._split(h[3])[-1]
        return len(seg) % 2

    def actions(self, h):
        seg = self._split(h[3])[-1]
        if seg in ('', 'k'):
            return ['k', 'b']
        if seg.endswith('b'):
            return ['c', 'r', 'f']
        return ['c', 'f']                         # 레이즈 직면 (캡 2벳)

    def infoset(self, h):
        card = h[0] if self.player(h) == 0 else h[1]
        return (card, h[2], h[3])
