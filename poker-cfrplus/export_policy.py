# -*- coding: utf-8 -*-
"""동결 전략 → 컴팩트 상대용 산출물 내보내기 (5단 12병렬 메모리 대책).

산출물 (data/):
  bot_policy_k{K}.npy   : 정규화 정책 flat float16 — 학습 프로세스들이 mmap 공유(~1.1GB 1회)
  bot_tree_k{K}.npz     : 결정 노드 압축 배열 —
      street(u8) to_act(u8) c0(u16) c1(u16) kb(u8=169|50) na(u8)
      act_off(i64)  : 노드별 행동 시작 오프셋
      act_code(i32) : 행동 부호화 — 벳 = target(+), 'f'=-1, 'c'=-2, 'k'=-3
      child(i32)    : 그 행동의 후속 "결정 노드" 인덱스 (찬스는 건너뜀), 종단 = -1
      pol_off(i64)  : 정책 flat 에서 노드 행 시작 (row = kb×na)

usage: python export_policy.py
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from hunl_tree import Chance, Decision, Terminal, build  # noqa: E402
from hunl_solver import K, PRE  # noqa: E402


def main():
    root, _ = build()
    nodes = []                       # Decision 만, cfr_opponent 수집 순서와 동일

    def collect(n):
        if isinstance(n, Decision):
            n.acts = sorted(n.children)
            nodes.append(n)
            for c in n.children.values():
                collect(c)
        elif isinstance(n, Chance):
            collect(n.child)
    sys.setrecursionlimit(1000000)
    collect(root)
    idx = {id(n): i for i, n in enumerate(nodes)}
    print(f"결정 노드 {len(nodes):,}")

    d = np.load(HERE / 'data' / f'hunl_frozen_k{K}.npz')

    N = len(nodes)
    street = np.zeros(N, np.uint8); to_act = np.zeros(N, np.uint8)
    c0 = np.zeros(N, np.uint16); c1 = np.zeros(N, np.uint16)
    kb = np.zeros(N, np.uint8); na = np.zeros(N, np.uint8)
    act_off = np.zeros(N + 1, np.int64)
    pol_off = np.zeros(N + 1, np.int64)
    act_code_l, child_l = [], []

    CODE = {'f': -1, 'c': -2, 'k': -3}

    def resolve(ch):
        """후속의 다음 결정 노드 인덱스 (찬스 통과), 종단이면 -1."""
        while isinstance(ch, Chance):
            ch = ch.child
        return idx[id(ch)] if isinstance(ch, Decision) else -1

    for i, n in enumerate(nodes):
        street[i] = n.street
        to_act[i] = n.to_act
        c0[i], c1[i] = n.contrib
        kbi = PRE if n.street == 0 else K
        kb[i] = kbi if kbi < 256 else 0          # 169/50 둘 다 <256 ✓
        na[i] = len(n.acts)
        act_off[i + 1] = act_off[i] + len(n.acts)
        pol_off[i + 1] = pol_off[i] + kbi * len(n.acts)
        for a in n.acts:
            act_code_l.append(int(a[1:]) if a.startswith('b') else CODE[a])
            child_l.append(resolve(n.children[a]))

    pol = np.empty(pol_off[-1], np.float16)
    for i, n in enumerate(nodes):
        ss = d[f's{i}'].astype(np.float32)
        tot = ss.sum(axis=1, keepdims=True)
        nrm = np.where(tot > 0, ss / np.where(tot > 0, tot, 1), 1.0 / ss.shape[1])
        pol[pol_off[i]:pol_off[i + 1]] = nrm.astype(np.float16).ravel()

    np.save(HERE / 'data' / f'bot_policy_k{K}.npy', pol)
    np.savez_compressed(HERE / 'data' / f'bot_tree_k{K}.npz',
                        street=street, to_act=to_act, c0=c0, c1=c1, kb=kb, na=na,
                        act_off=act_off, pol_off=pol_off,
                        act_code=np.array(act_code_l, np.int32),
                        child=np.array(child_l, np.int32))
    print(f"saved bot_policy_k{K}.npy ({pol.nbytes/2**30:.2f}GB) + bot_tree_k{K}.npz")


if __name__ == '__main__':
    main()
