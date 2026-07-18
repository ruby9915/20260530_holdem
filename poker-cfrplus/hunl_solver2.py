# -*- coding: utf-8 -*-
"""벡터 CFR+ 솔버 v2 — 층별·그룹별 배치 처리 (수학은 hunl_solver 와 동일).

원리: 트리를 깊이 층으로 평탄화하고, 같은 층의 동종 노드(같은 라운드·행동자·
행동수)를 그룹으로 묶어 (배치 × 버킷 × 행동) 텐서 연산으로 한꺼번에 처리.
그룹의 regret/ssum 은 연속 메모리에 배치 — 파이썬 루프가 "노드 수(수백만)"에서
"층 × 그룹(수백)"으로 줄어든다. 도달/가치 버퍼는 플랫 배열 + fancy-index gather.

의미론 보존 (hunl_solver._walk 1:1):
  전진(얕→깊): 상대 도달 전파, 상대 노드에서 σ 곱 + ssum 진입 누적
  후진(깊→얕): 종단 EQ 가치 → σ-가중합, 트래버서 노드 RM+ 갱신(진입 σ 사용)
  교대 갱신 · 평균 가중 w=max(t−d,0) 동일. 상태 파일 s{i}/r{i} 순서 호환.

usage: python hunl_solver2.py [iters=4000] [--resume]
검증: tests/test_solver_equiv.py (구솔버와 수치 일치) 통과 후 사용.
"""
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from hunl_tree import BB, Chance, Decision, Terminal, build  # noqa: E402
from hunl_solver import combo_weights, K, PRE  # noqa: E402


class VecSolver:
    def __init__(self, mat_path=None, avg_delay=100):
        d = np.load(mat_path or HERE / 'data' / f'matrices_k{K}.npz')
        self.T = [d['T0'].astype(np.float32), d['T1'].astype(np.float32),
                  d['T2'].astype(np.float32)]
        EQ = [d[f'EQ{i}'].astype(np.float32) for i in range(4)]
        self.EQ = EQ
        self.EQT = [(1.0 - m.T).copy() for m in EQ]     # 트래버서=좌석1 관점
        self.pre_w = combo_weights().astype(np.float32)
        self.d = avg_delay
        self.t = 0

        self.root, _ = build()
        # ── 수집 (구솔버 attach 와 동일 순서 → 상태 파일 호환) ──
        self.nodes, self.dec_nodes = [], []
        depth_of, self._id2idx = [], {}

        stack = [(self.root, 0)]
        # 재귀 대신 명시적 선순회 (구현상 재귀와 동일 순서 보장 위해 재귀 사용)
        sys.setrecursionlimit(1000000)

        def collect(n, dep):
            idx = len(self.nodes)
            self.nodes.append(n)
            depth_of.append(dep)
            self._id2idx[id(n)] = idx
            if isinstance(n, Decision):
                n.acts = sorted(n.children)
                self.dec_nodes.append(n)
                # 재귀는 삽입 순서 — 구솔버 attach·cfr_opponent 와 동일 (상태 호환)
                for c in n.children.values():
                    collect(c, dep + 1)
            elif isinstance(n, Chance):
                collect(n.child, dep + 1)
        collect(self.root, 0)
        N = len(self.nodes)
        kb_arr = np.array([PRE if n.street == 0 else K for n in self.nodes], np.int64)

        # 가치/도달 플랫 버퍼
        self.v_off = np.zeros(N + 1, np.int64)
        np.cumsum(kb_arr, out=self.v_off[1:])
        self.V = np.zeros(self.v_off[-1], np.float32)
        self.RCH = np.zeros(self.v_off[-1], np.float32)

        # ── 층·그룹 구성 ──
        by_layer = defaultdict(lambda: {'dec': defaultdict(list), 'chn': defaultdict(list),
                                        'tf': defaultdict(list), 'ts': defaultdict(list)})
        for i, n in enumerate(self.nodes):
            g = by_layer[depth_of[i]]
            if isinstance(n, Decision):
                g['dec'][(n.street, n.to_act, len(n.acts))].append(i)
            elif isinstance(n, Chance):
                g['chn'][n.street].append(i)
            elif n.kind == 'fold':
                g['tf'][n.street].append(i)
            else:
                g['ts'][n.street].append(i)
        self.max_depth = max(by_layer)

        # 그룹-연속 regret/ssum 저장 + 그룹 메타
        total = 0
        self.layers = []
        self.dec_groups = []                            # (노드 인덱스 목록, 텐서 뷰 사양)
        for dep in range(self.max_depth + 1):
            g = by_layer[dep]
            dec = []
            for (street, actor, na), ids in sorted(g['dec'].items()):
                ids = np.array(ids, np.int64)
                kbk = PRE if street == 0 else K
                B = len(ids)
                gidx = len(self.dec_groups)
                dec.append((street, actor, na, ids, kbk, total, gidx))
                self.dec_groups.append((ids, kbk, na, total))
                total += B * kbk * na
            chn = [(st, np.array(ids, np.int64)) for st, ids in sorted(g['chn'].items())]
            tf = []
            for st, ids in sorted(g['tf'].items()):
                ids = np.array(ids, np.int64)
                v0 = np.array([self._fold_val(self.nodes[i], 0) for i in ids], np.float32)
                v1 = np.array([self._fold_val(self.nodes[i], 1) for i in ids], np.float32)
                tf.append((st, ids, v0, v1))
            ts = []
            for st, ids in sorted(g['ts'].items()):
                ids = np.array(ids, np.int64)
                c = np.array([self.nodes[i].contrib[0] for i in ids], np.float32)
                ts.append((st, ids, c))
            self.layers.append({'dec': dec, 'chn': chn, 'tf': tf, 'ts': ts})

        self.R = np.zeros(total, np.float32)
        self.S = np.zeros(total, np.float32)

        # 노드 객체에 뷰 부착 (평가·상대 모듈·저장 호환) + 그룹 텐서 뷰 캐시
        self._gview = []
        for (ids, kbk, na, off) in self.dec_groups:
            B = len(ids)
            Rg = self.R[off:off + B * kbk * na].reshape(B, kbk, na)
            Sg = self.S[off:off + B * kbk * na].reshape(B, kbk, na)
            self._gview.append((Rg, Sg))
            for b, i in enumerate(ids):
                n = self.nodes[i]
                n.regret = Rg[b]
                n.ssum = Sg[b]
        self._nodes = self.dec_nodes

        # 자식 인덱스 텐서 (그룹별 B×na) / 찬스 자식
        self._gchild = []
        for (ids, kbk, na, off) in self.dec_groups:
            ch = np.empty((len(ids), na), np.int64)
            for b, i in enumerate(ids):
                n = self.nodes[i]
                for a_ix, a in enumerate(n.acts):
                    ch[b, a_ix] = self._id2idx[id(n.children[a])]
            self._gchild.append(ch)
        self._chn_child = {}
        for dep in range(self.max_depth + 1):
            for st, ids in self.layers[dep]['chn']:
                self._chn_child[(dep, st)] = np.array(
                    [self._id2idx[id(self.nodes[i].child)] for i in ids], np.int64)

        # gather 인덱스 캐시: (ids, kbk) → 인덱스 행렬
        self._gi_cache = {}

    @staticmethod
    def _fold_val(n, trav):
        return n.contrib[1 - trav] if n.folder != trav else -n.contrib[trav]

    def _gi(self, ids_key, ids, kbk):
        m = self._gi_cache.get(ids_key)
        if m is None:
            m = (self.v_off[ids][:, None] + np.arange(kbk)[None, :]).astype(np.int32)
            self._gi_cache[ids_key] = m
        return m

    # ── 한 반복 (교대 갱신) ──
    def iterate(self):
        self.t += 1
        w = np.float32(max(self.t - self.d, 0))
        for trav in (0, 1):
            self._pass(trav, w)

    def _sigma_g(self, gidx, na):
        Rg, _ = self._gview[gidx]
        pos = np.maximum(Rg, 0.0)
        s = pos.sum(axis=2, keepdims=True)
        return np.where(s > 0, pos / np.where(s > 0, s, 1), np.float32(1.0 / na))

    def _pass(self, trav, w):
        V, RCH = self.V, self.RCH
        RCH[self.v_off[0]:self.v_off[0] + PRE] = self.pre_w
        # ── 전진 ──
        for dep in range(self.max_depth + 1):
            Lg = self.layers[dep]
            for (street, actor, na, ids, kbk, off, gidx) in Lg['dec']:
                gi = self._gi(('d', dep, street, actor, na), ids, kbk)
                r = RCH[gi]                                        # (B, kb)
                ch = self._gchild[gidx]
                if actor != trav:
                    sig = self._sigma_g(gidx, na)                  # 상대 노드만 σ 필요
                    _, Sg = self._gview[gidx]
                    Sg += w * r[:, :, None] * sig
                    for a_ix in range(na):
                        ci = self._gi(('dc', dep, street, actor, na, a_ix),
                                      ch[:, a_ix], kbk)
                        RCH[ci] = r * sig[:, :, a_ix]
                else:
                    for a_ix in range(na):
                        ci = self._gi(('dc', dep, street, actor, na, a_ix),
                                      ch[:, a_ix], kbk)
                        RCH[ci] = r
            for st, ids in Lg['chn']:
                kbk = PRE if st == 0 else K
                gi = self._gi(('c', dep, st), ids, kbk)
                r2 = RCH[gi] @ self.T[st]
                ci = self._gi(('cc', dep, st), self._chn_child[(dep, st)], K)
                RCH[ci] = r2
        # ── 후진 ──
        EQ = self.EQ if trav == 0 else self.EQT
        for dep in range(self.max_depth, -1, -1):
            Lg = self.layers[dep]
            for (st, ids, v0, v1) in Lg['tf']:
                kbk = PRE if st == 0 else K
                gi = self._gi(('f', dep, st), ids, kbk)
                r = RCH[gi]
                val = v0 if trav == 0 else v1
                V[gi] = val[:, None] * r.sum(axis=1, keepdims=True)
            for (st, ids, c) in Lg['ts']:
                kbk = PRE if st == 0 else K
                gi = self._gi(('s', dep, st), ids, kbk)
                r = RCH[gi]
                V[gi] = (r @ EQ[st].T) * (2 * c[:, None]) \
                    - c[:, None] * r.sum(axis=1, keepdims=True)
            for st, ids in Lg['chn']:
                kbk = PRE if st == 0 else K
                ci = self._gi(('cc', dep, st), self._chn_child[(dep, st)], K)
                u = V[ci] @ self.T[st].T
                gi = self._gi(('c', dep, st), ids, kbk)
                V[gi] = u
            for (street, actor, na, ids, kbk, off, gidx) in Lg['dec']:
                ch = self._gchild[gidx]
                U = np.empty((len(ids), na, kbk), np.float32)
                for a_ix in range(na):
                    ci = self._gi(('dc', dep, street, actor, na, a_ix),
                                  ch[:, a_ix], kbk)
                    U[:, a_ix, :] = V[ci]
                gi = self._gi(('d', dep, street, actor, na), ids, kbk)
                if actor == trav:
                    sig = self._sigma_g(gidx, na)                  # 트래버서 노드만 σ 필요
                    u = np.einsum('bka,bak->bk', sig, U)
                    Rg, _ = self._gview[gidx]
                    np.maximum(Rg + (np.transpose(U, (0, 2, 1)) - u[:, :, None]),
                               0.0, out=Rg)
                else:
                    u = U.sum(axis=1)
                V[gi] = u

    # ── 평가 (구솔버 재귀 로직 재사용 — 체크포인트 전용, 느려도 무방) ──
    def _avg_sig(self, n):
        s = n.ssum.sum(axis=1, keepdims=True)
        return np.where(s > 0, n.ssum / np.where(s > 0, s, 1), 1.0 / n.ssum.shape[1])

    def game_value(self):
        return self._ev(self.root, self.pre_w.astype(np.float64),
                        self.pre_w.astype(np.float64))

    def _ev(self, n, r0, r1):
        if isinstance(n, Terminal):
            c0, c1 = n.contrib
            if n.kind == 'fold':
                return (c1 if n.folder == 1 else -c0) * r0.sum() * r1.sum()
            return float(r0 @ self.EQ[n.street].astype(np.float64) @ r1) * (2 * c0) \
                - c0 * r0.sum() * r1.sum()
        if isinstance(n, Chance):
            T = self.T[n.street].astype(np.float64)
            return self._ev(n.child, r0 @ T, r1 @ T)
        sig = self._avg_sig(n)
        tot = 0.0
        for a_ix, a in enumerate(n.acts):
            child = n.children[a]
            if n.to_act == 0:
                tot += self._ev(child, r0 * sig[:, a_ix], r1)
            else:
                tot += self._ev(child, r0, r1 * sig[:, a_ix])
        return tot

    def exploitability(self):
        v = self.game_value()
        br0 = self._br(0)
        br1 = self._br(1)
        return ((br0 - v) + (br1 - (-v))) / 2 * 1000.0 / BB

    def _br(self, br_p):
        def walk(n, r_opp):
            if isinstance(n, Terminal):
                trav = br_p
                kbk = PRE if n.street == 0 else K
                me_c = n.contrib[trav]; opp_c = n.contrib[1 - trav]
                if n.kind == 'fold':
                    val = opp_c if n.folder != trav else -me_c
                    return np.full(kbk, val) * r_opp.sum()
                eq = self.EQ[n.street] if trav == 0 else self.EQT[n.street]
                return (eq.astype(np.float64) @ r_opp) * (2 * me_c) \
                    - me_c * r_opp.sum()
            if isinstance(n, Chance):
                T = self.T[n.street].astype(np.float64)
                return T @ walk(n.child, r_opp @ T)
            sig = self._avg_sig(n)
            if n.to_act == br_p:
                U = np.stack([walk(n.children[a], r_opp) for a in n.acts], axis=1)
                return U.max(axis=1)
            u = None
            for a_ix, a in enumerate(n.acts):
                r = walk(n.children[a], r_opp * sig[:, a_ix])
                u = r if u is None else u + r
            return u
        u = walk(self.root, self.pre_w.astype(np.float64))
        return float(u @ self.pre_w)


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
        n.ssum[:] = d[f's{i}']              # 뷰 유지 — 반드시 복사 대입
        n.regret[:] = d[f'r{i}']
    s.t = int(d['t'][0])


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    resume = '--resume' in sys.argv
    state = HERE / 'data' / f'hunl_state_k{K}.npz'
    t0 = time.time()
    s = VecSolver(avg_delay=100)
    print(f"[hunl-cfr+ v2] 결정노드 {len(s._nodes):,} | 그룹 {len(s.dec_groups)} | "
          f"빌드 {time.time()-t0:.0f}s", flush=True)
    if resume and state.exists():
        load_state(s, state)
        print(f"[hunl-cfr+ v2] resume from t={s.t}", flush=True)
    ckpt = sorted({250, 1000, 2000, 3000, iters} | {iters // 2})
    t0 = time.time()
    done0 = s.t
    while s.t - done0 < iters:
        s.iterate()
        tt = s.t - done0
        if tt % 25 == 0 and tt not in ckpt and tt % 250 != 0:
            el = time.time() - t0
            print(f"  ({tt/iters*100:5.1f}%) iter {s.t:>5} | {el:.0f}s "
                  f"eta {el/tt*(iters-tt):.0f}s", flush=True)
        if tt % 500 == 0 and tt not in ckpt:
            save_state(s, state)
            print(f"  ({tt/iters*100:5.1f}%) iter {s.t:>5} | state saved", flush=True)
        if tt in ckpt:
            ex = s.exploitability()
            el = time.time() - t0
            print(f"  ({tt/iters*100:5.1f}%) iter {s.t:>5} | value(좌석0) "
                  f"{s.game_value():+8.3f}칩 | expl {ex:8.2f} mbb/g | {el:.0f}s "
                  f"eta {el/tt*(iters-tt):.0f}s", flush=True)
            save_state(s, state)
            if ex <= 5.0:                       # 수렴 게이트 조기 충족 → 종료
                print(f"  early-stop: expl {ex:.2f} <= 5", flush=True)
                break
    save_state(s, state)
    print(f"saved (t={s.t})", flush=True)


if __name__ == '__main__':
    main()
