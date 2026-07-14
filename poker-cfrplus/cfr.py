# -*- coding: utf-8 -*-
"""CFR+ 솔버 — 스칼라형·교대 갱신·regret matching+ (Tammelin 2014 원형).

게임 인터페이스 (games_toy.py 참조):
  is_terminal(h) / util0(h)      : 종단 판정 / 플레이어 0 기준 payoff
  is_chance(h) / chance(h)       : 찬스 노드 / [(outcome, prob)]
  player(h) / actions(h)         : 행동할 플레이어(0/1) / 합법 행동
  next(h, a)                     : 후속 히스토리
  infoset(h)                     : 현재 플레이어의 정보집합 키

CFR+ 3요소 (원 논문 정의 그대로):
  - regret matching+ : R ← max(R + Δ, 0)  (매 갱신 후 음수 절단)
  - 교대 갱신        : 반복마다 플레이어 한 명씩 순회
  - 지연 가중 평균   : 평균 전략 가중 w_T = max(T − d, 0)
"""
from collections import defaultdict


class CFRPlus:
    def __init__(self, game, avg_delay: int = 0):
        self.g = game
        self.d = avg_delay
        self.regret = defaultdict(lambda: defaultdict(float))    # I -> a -> R+
        self.strat_sum = defaultdict(lambda: defaultdict(float))  # I -> a -> Σwσ
        self.t = 0

    # ── regret matching+ 현재 전략 ─────────────────────────
    def sigma(self, I, acts):
        r = self.regret[I]
        pos = {a: max(r[a], 0.0) for a in acts}
        s = sum(pos.values())
        if s > 0:
            return {a: pos[a] / s for a in acts}
        return {a: 1.0 / len(acts) for a in acts}

    # ── 한 반복 (교대 갱신) ────────────────────────────────
    def iterate(self):
        self.t += 1
        w = max(self.t - self.d, 0)
        for traverser in (0, 1):
            self._walk(self.g.initial(), traverser, 1.0, 1.0, w)

    def _walk(self, h, trav, pi_trav, pi_other, w):
        g = self.g
        if g.is_terminal(h):
            u0 = g.util0(h)
            return u0 if trav == 0 else -u0
        if g.is_chance(h):
            return sum(p * self._walk(g.next(h, o), trav, pi_trav, pi_other * p, w)
                       for o, p in g.chance(h))
        p_act = g.player(h)
        I = g.infoset(h)
        acts = g.actions(h)
        sig = self.sigma(I, acts)
        if p_act == trav:
            u_a = {a: self._walk(g.next(h, a), trav, pi_trav * sig[a], pi_other, w)
                   for a in acts}
            u = sum(sig[a] * u_a[a] for a in acts)
            r = self.regret[I]
            for a in acts:                     # regret matching+ 절단
                r[a] = max(r[a] + pi_other * (u_a[a] - u), 0.0)
            ss = self.strat_sum[I]
            for a in acts:                     # 평균 전략 (자기 도달 가중)
                ss[a] += w * pi_trav * sig[a]
            return u
        u = 0.0
        for a in acts:
            u += sig[a] * self._walk(g.next(h, a), trav, pi_trav, pi_other * sig[a], w)
        return u

    # ── 평균 전략 ──────────────────────────────────────────
    def avg_sigma(self, I, acts):
        ss = self.strat_sum[I]
        s = sum(ss[a] for a in acts)
        if s > 0:
            return {a: ss[a] / s for a in acts}
        return {a: 1.0 / len(acts) for a in acts}

    # ── 평가: 평균 전략의 게임 가치 & exploitability ───────
    def game_value(self):
        """플레이어 0 기준 평균 전략 상호 대국 기대 payoff."""
        return self._ev(self.g.initial())

    def _ev(self, h):
        g = self.g
        if g.is_terminal(h):
            return g.util0(h)
        if g.is_chance(h):
            return sum(p * self._ev(g.next(h, o)) for o, p in g.chance(h))
        sig = self.avg_sigma(g.infoset(h), g.actions(h))
        return sum(sig[a] * self._ev(g.next(h, a)) for a in g.actions(h))

    def exploitability(self):
        """(BR0 이득 + BR1 이득)/2 — 0이면 정확한 내쉬."""
        br0 = self._best_response(0)
        br1 = self._best_response(1)
        v = self.game_value()
        return ((br0 - v) + (br1 - (-v))) / 2

    def _best_response(self, br_player):
        # 상대의 평균 전략을 고정하고 br_player 의 최적 대응 가치 계산.
        # 정보집합 단위 최적화: 동일 정보집합의 히스토리들을 모아 도달확률 가중 argmax.
        from collections import defaultdict as dd
        infoset_hists = dd(list)                 # I -> [(h, reach_other)]

        def collect(h, reach):
            g = self.g
            if g.is_terminal(h):
                return
            if g.is_chance(h):
                for o, p in g.chance(h):
                    collect(g.next(h, o), reach * p)
                return
            if g.player(h) == br_player:
                infoset_hists[g.infoset(h)].append((h, reach))
                for a in g.actions(h):
                    collect(g.next(h, a), reach)
            else:
                sig = self.avg_sigma(g.infoset(h), g.actions(h))
                for a in g.actions(h):
                    collect(g.next(h, a), reach * sig[a])

        collect(self.g.initial(), 1.0)
        memo = {}

        def br_val(h):                            # br_player 기준 가치
            g = self.g
            if h in memo:
                return memo[h]
            if g.is_terminal(h):
                u0 = g.util0(h)
                v = u0 if br_player == 0 else -u0
            elif g.is_chance(h):
                v = sum(p * br_val(g.next(h, o)) for o, p in g.chance(h))
            elif g.player(h) == br_player:
                I = g.infoset(h)
                a_star = self._br_action(I, infoset_hists, br_val)
                v = br_val(g.next(h, a_star))
            else:
                sig = self.avg_sigma(g.infoset(h), g.actions(h))
                v = sum(sig[a] * br_val(g.next(h, a)) for a in g.actions(h))
            memo[h] = v
            return v

        self._br_cache = {}
        return br_val(self.g.initial())

    def _br_action(self, I, infoset_hists, br_val):
        if I in self._br_cache:
            return self._br_cache[I]
        g = self.g
        hists = infoset_hists[I]
        acts = g.actions(hists[0][0])
        best_a, best_v = None, float('-inf')
        for a in acts:
            v = sum(reach * br_val(g.next(h, a)) for h, reach in hists)
            if v > best_v:
                best_v, best_a = v, a
        self._br_cache[I] = best_a
        return best_a
