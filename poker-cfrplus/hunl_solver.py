# -*- coding: utf-8 -*-
"""추상 HUNL 벡터형 CFR+ 솔버 (4단 부품 ④-2).

cfr.py 로 정답 검증한 수학(RM+·교대 갱신·지연 가중 평균, Tammelin 2014)을
hunl_tree.py 의 베팅 트리 × 버킷 확률 벡터 위에서 돈다.

정보집합 = (결정 노드, 행동자의 현재 라운드 버킷) — 베팅 시퀀스는 전체 기억,
카드 버킷은 현재 라운드 것만(imperfect recall). 프리플랍 169 무손실, 포스트플랍 K.

공개하는 근사: 두 플레이어 버킷 전이 독립 취급(카드 제거 상관 무시 — 버킷 CFR 표준),
에퀴티는 버킷쌍 행렬(EQ0~EQ3, 동일 보드 결합 집계).

값 규약: walk()가 반환하는 u[k] = "행동자 버킷 k 의 상대-도달가중 반사실적 가치(칩)".
"""
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from hunl_tree import BB, STACK, Chance, Decision, Terminal, build  # noqa: E402

K = 50
PRE = 169


def combo_weights():
    """169 클래스의 콤보 확률 (페어 6 / 수티드 4 / 오프수트 12, 합 1)."""
    RANKS = 'AKQJT98765432'
    w = []
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i == j and r1 == r2:
                w.append(6)
            elif j > i:
                w.append(4); w.append(12)
    v = np.array(w, dtype=np.float64)
    return v / v.sum()


class HunlCFRPlus:
    def __init__(self, mat_path=None, avg_delay=50):
        d = np.load(mat_path or HERE / 'data' / f'matrices_k{K}.npz')
        self.T = [d['T0'], d['T1'], d['T2']]          # street s → s+1 전이
        self.EQ = [d['EQ0'], d['EQ1'], d['EQ2'], d['EQ3']]
        self.pre_w = combo_weights()
        self.d = avg_delay
        self.t = 0

        self.root, self.stats = build()
        # 결정 노드에 (regret, strat_sum) 배열 부착
        self._nodes = []

        def attach(n):
            if isinstance(n, Decision):
                kb = PRE if n.street == 0 else K
                acts = sorted(n.children)
                n.acts = acts
                n.regret = np.zeros((kb, len(acts)), dtype=np.float32)
                n.ssum = np.zeros((kb, len(acts)), dtype=np.float32)
                self._nodes.append(n)
                for c in n.children.values():
                    attach(c)
            elif isinstance(n, Chance):
                attach(n.child)
        sys.setrecursionlimit(300000)
        attach(self.root)

    # ── regret matching+ (버킷별 행 정규화) ────────────────
    @staticmethod
    def _sigma(regret):
        pos = np.maximum(regret, 0.0)
        s = pos.sum(axis=1, keepdims=True)
        n_act = regret.shape[1]
        sig = np.where(s > 0, pos / np.where(s > 0, s, 1), 1.0 / n_act)
        return sig

    def sigma_avg(self, node):
        s = node.ssum.sum(axis=1, keepdims=True)
        n_act = node.ssum.shape[1]
        return np.where(s > 0, node.ssum / np.where(s > 0, s, 1), 1.0 / n_act)

    # ── 종단 가치: u[k] = Σ_k' r_opp[k'] · payoff(k,k') ────
    def _terminal_u(self, n, trav, r_opp):
        me_c = n.contrib[trav]
        opp_c = n.contrib[1 - trav]
        if n.kind == 'fold':
            val = opp_c if n.folder != trav else -me_c
            return np.full(self._kb_at(n.street), val) * r_opp.sum()
        # showdown/allin: 동일 기여(c) — E = EQ·2c − c (무승부 절반 포함, 정확)
        eq = self.EQ[n.street]
        if trav == 1:
            eq = 1.0 - eq.T      # EQ[k,k'] = P(좌석0 관점 승) 대칭화
        c = me_c                  # = opp_c
        return (eq @ r_opp) * (2 * c) - c * r_opp.sum()

    @staticmethod
    def _kb_at(street):
        return PRE if street == 0 else K

    # ── 교대 갱신 반복 ─────────────────────────────────────
    def iterate(self):
        self.t += 1
        w = max(self.t - self.d, 0)
        for trav in (0, 1):
            self._walk(self.root, trav, self.pre_w.copy(), w)

    def _walk(self, n, trav, r_opp, w):
        if isinstance(n, Terminal):
            return self._terminal_u(n, trav, r_opp)
        if isinstance(n, Chance):
            u_next = self._walk(n.child, trav, r_opp @ self.T[n.street], w)
            return self.T[n.street] @ u_next
        sig = self._sigma(n.regret)
        if n.to_act == trav:
            u_as = []
            for ai, a in enumerate(n.acts):
                u_as.append(self._walk(n.children[a], trav, r_opp, w))
            U = np.stack(u_as, axis=1)                  # [kb, n_act]
            u = (sig * U).sum(axis=1)
            n.regret[:] = np.maximum(n.regret + (U - u[:, None]), 0.0)
            return u
        # 상대 노드: 평균 전략 누적(Tammelin — 자기 도달가중) + 도달 분기
        n.ssum += w * r_opp[:, None] * sig
        u = np.zeros(self._kb_at_trav(n, trav))
        for ai, a in enumerate(n.acts):
            u = u + self._walk(n.children[a], trav, r_opp * sig[:, ai], w)
        return u

    def _kb_at_trav(self, n, trav):
        # 행동자 노드에서 반환 벡터는 '트래버서'의 현재 라운드 버킷 차원
        return PRE if n.street == 0 else K

    # ── 평균 전략 상호 대국 가치 (좌석0 관점, 칩) ───────────
    def game_value(self):
        return self._ev(self.root, self.pre_w.copy(), self.pre_w.copy())

    def _ev(self, n, r0, r1):
        if isinstance(n, Terminal):
            c0, c1 = n.contrib
            if n.kind == 'fold':
                mass = r0.sum() * r1.sum()
                return (c1 if n.folder == 1 else -c0) * mass
            eq = self.EQ[n.street]
            c = c0
            return float(r0 @ eq @ r1) * (2 * c) - c * (r0.sum() * r1.sum())
        if isinstance(n, Chance):
            return self._ev(n.child, r0 @ self.T[n.street], r1 @ self.T[n.street])
        sig = self.sigma_avg(n)
        tot = 0.0
        for ai, a in enumerate(n.acts):
            if n.to_act == 0:
                tot += self._ev(n.children[a], r0 * sig[:, ai], r1)
            else:
                tot += self._ev(n.children[a], r0, r1 * sig[:, ai])
        return tot

    # ── 추상 게임 내 exploitability (mbb/g) ────────────────
    def exploitability(self):
        br0 = self._br(0)
        br1 = self._br(1)
        v = self.game_value()
        # 좌석0 최적대응 이득 + 좌석1 최적대응 이득 (칩) → mbb/g (BB=2)
        return ((br0 - v) + (br1 - (-v))) / 2 * 1000.0 / BB

    def _br(self, br_p):
        """br_p 의 최적 대응 가치 (칩, br_p 관점) — 상대 평균 전략 고정."""
        def walk(n, r_opp):
            if isinstance(n, Terminal):
                return self._terminal_u_br(n, br_p, r_opp)
            if isinstance(n, Chance):
                return self.T[n.street] @ walk(n.child, r_opp @ self.T[n.street])
            sig = self.sigma_avg(n)
            if n.to_act == br_p:
                U = np.stack([walk(n.children[a], r_opp) for a in n.acts], axis=1)
                return U.max(axis=1)
            u = None
            for ai, a in enumerate(n.acts):
                r = walk(n.children[a], r_opp * sig[:, ai])
                u = r if u is None else u + r
            return u
        u = walk(self.root, self.pre_w.copy())
        return float(u @ self.pre_w)

    def _terminal_u_br(self, n, trav, r_opp):
        me_c = n.contrib[trav]
        opp_c = n.contrib[1 - trav]
        kb = self._kb_at(n.street)
        if n.kind == 'fold':
            val = opp_c if n.folder != trav else -me_c
            return np.full(kb, val) * r_opp.sum()
        eq = self.EQ[n.street]
        if trav == 1:
            eq = 1.0 - eq.T
        c = me_c
        return (eq @ r_opp) * (2 * c) - c * r_opp.sum()


def save_state(s, path):
    arrs = {}
    for i, n in enumerate(s._nodes):
        arrs[f's{i}'] = n.ssum
        arrs[f'r{i}'] = n.regret
    arrs['t'] = np.array([s.t])
    np.savez_compressed(path, **arrs)


def load_state(s, path):
    d = np.load(path)
    for i, n in enumerate(s._nodes):
        n.ssum = d[f's{i}']
        n.regret = d[f'r{i}']
    s.t = int(d['t'][0])


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    resume = '--resume' in sys.argv
    state = HERE / 'data' / f'hunl_state_k{K}.npz'
    s = HunlCFRPlus(avg_delay=100)
    if resume and state.exists():
        load_state(s, state)
        print(f"[hunl-cfr+] resume from t={s.t}", flush=True)
    ckpt = sorted({250, 1000, 2000, 3000, iters} | {iters // 2})
    print(f"[hunl-cfr+] 결정노드 {len(s._nodes):,} | K={K} | iters={iters}", flush=True)
    t0 = time.time()
    done0 = s.t
    while s.t - done0 < iters:
        s.iterate()
        tt = s.t - done0
        if tt % 25 == 0 and tt not in ckpt and tt % 250 != 0:
            el = time.time() - t0                  # 심박 (감시 창 정지 오판 방지)
            print(f"  ({tt/iters*100:5.1f}%) iter {s.t:>5} | {el:.0f}s "
                  f"eta {el/tt*(iters-tt):.0f}s", flush=True)
        if tt % 250 == 0 and tt not in ckpt:       # 저장만 (재부팅 대비, ~2h 간격)
            save_state(s, state)
            print(f"  ({tt/iters*100:5.1f}%) iter {s.t:>5} | state saved", flush=True)
        if tt in ckpt:
            ex = s.exploitability()
            el = time.time() - t0
            pct = tt / iters * 100
            print(f"  ({pct:5.1f}%) iter {s.t:>5} | value(좌석0) {s.game_value():+8.3f}칩 "
                  f"| expl {ex:8.2f} mbb/g | {el:.0f}s eta {el/tt*(iters-tt):.0f}s", flush=True)
            save_state(s, state)
    save_state(s, state)
    print(f"saved {state.name} (t={s.t})", flush=True)


if __name__ == '__main__':
    main()
