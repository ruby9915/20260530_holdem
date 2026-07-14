# -*- coding: utf-8 -*-
"""추상 게임 확률 행렬 사전계산 (CFR+ 봇 1단계 — 실험일지 35절 (5), 4단).

한 번의 대규모 MC 패스로 실제 카드를 다음 행렬들로 치환한다:
  T0 : P(플랍 버킷 | 프리플랍 169클래스)          169×K
  T1 : P(턴 버킷 | 플랍 버킷)                      K×K
  T2 : P(리버 버킷 | 턴 버킷)                      K×K
  EQ3: P(승 | 내 리버버킷, 상대 리버버킷)          K×K   (쇼다운)
  EQ0: P(승 | 내 프리플랍 클래스, 상대 클래스)     169×169 (프리플랍 올인 — 별도 경량 패스)
  EQ1/EQ2: 스트리트 올인용 버킷쌍 에퀴티            K×K

공개하는 근사(정직): 트리의 찬스 노드는 두 플레이어 전이를 독립으로 취급
(카드 제거 상관은 EQ 행렬 집계에는 반영되나 전이 분해에서는 무시) — 버킷 CFR 표준 관행.
버킷 배정 = ladder 와 동일한 E[HS] 추정량(n_roll 150/200, ehs_buckets_k{K}.json 경계).

usage: python precompute_matrices.py [K=50] [n_main=2000000] [n_pre=50000000]
출력: poker-cfrplus/data/matrices_k{K}.npz + _matrices_log.txt
진행: results/_logs/ladder_cfr_matrices.log 에 (xx.x%) 표기 → progress.py 창 표시
"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LADDER = HERE.parent / 'poker-ladder'
sys.path.insert(0, str(LADDER))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from treys import Card as TC, Evaluator  # noqa: E402
from cards import EHS, _canonical_label, _RawCard  # noqa: E402

K       = int(sys.argv[1]) if len(sys.argv) > 1 else 50
N_MAIN  = int(sys.argv[2]) if len(sys.argv) > 2 else 2_000_000
N_PRE   = int(sys.argv[3]) if len(sys.argv) > 3 else 50_000_000
SEED    = 20260714
N_JOBS  = 10

RANKS = '23456789TJQKA'
SUITS = 'shdc'
DECK_STR = [r + s for r in RANKS for s in SUITS]
_ev = Evaluator()

# 프리플랍 169 클래스 인덱스
PRE_LABELS = []
for i, r1 in enumerate(RANKS[::-1]):
    for j, r2 in enumerate(RANKS[::-1]):
        if r1 == r2 and i == j:
            PRE_LABELS.append(r1 + r2)
        elif j > i:
            PRE_LABELS.append(r1 + r2 + 's')
            PRE_LABELS.append(r1 + r2 + 'o')
PRE_IDX = {lbl: i for i, lbl in enumerate(PRE_LABELS)}
N_PRE_CLS = len(PRE_LABELS)          # 169


def pre_class(cards_str):
    return PRE_IDX[_canonical_label([_RawCard(c) for c in cards_str])]


def _win(h1_t, h2_t, board_t):
    s1 = _ev.evaluate(board_t, h1_t)
    s2 = _ev.evaluate(board_t, h2_t)
    return 1.0 if s1 < s2 else (0.5 if s1 == s2 else 0.0)


def job_main(args):
    """메인 패스: 딜 1회 = 두 플레이어 홀 + 풀보드 → 스트리트별 버킷 + 승자."""
    n, seed = args
    import random
    rng = random.Random(seed)
    ehs = EHS(K)
    deck_t = [TC.new(c) for c in DECK_STR]
    idx = list(range(52))

    T0 = np.zeros((N_PRE_CLS, K)); T1 = np.zeros((K, K)); T2 = np.zeros((K, K))
    EQn = [np.zeros((K, K)) for _ in range(3)]      # EQ1(플랍쌍) EQ2(턴쌍) EQ3(리버쌍)
    EQd = [np.zeros((K, K)) for _ in range(3)]

    for it in range(n):
        rng.shuffle(idx)
        h1s, h2s = idx[0:2], idx[2:4]
        board = idx[4:9]
        h1_t = [deck_t[i] for i in h1s]
        h2_t = [deck_t[i] for i in h2s]
        b_t = [deck_t[i] for i in board]
        c1 = pre_class([DECK_STR[i] for i in h1s])
        w = _win(h1_t, h2_t, b_t)
        prev1 = prev2 = None
        for st, nb in enumerate((3, 4, 5)):
            bb = b_t[:nb]
            b1 = ehs._ehs(h1_t, bb); k1 = ehs_bucket(ehs, b1, nb)
            b2 = ehs._ehs(h2_t, bb); k2 = ehs_bucket(ehs, b2, nb)
            if st == 0:
                T0[c1, k1] += 1
            elif st == 1:
                T1[prev1, k1] += 1
            else:
                T2[prev1, k1] += 1
            EQn[st][k1, k2] += w; EQd[st][k1, k2] += 1
            prev1, prev2 = k1, k2
    return T0, T1, T2, EQn, EQd


def ehs_bucket(ehs_obj, val, nb):
    from bisect import bisect_right
    return bisect_right(ehs_obj._cuts[nb], val)


def job_pre_equity(args):
    """경량 패스: 프리플랍 클래스쌍 에퀴티 (버킷 계산 없음 — 딜+평가 2회)."""
    n, seed = args
    import random
    rng = random.Random(seed)
    deck_t = [TC.new(c) for c in DECK_STR]
    idx = list(range(52))
    num = np.zeros((N_PRE_CLS, N_PRE_CLS)); den = np.zeros((N_PRE_CLS, N_PRE_CLS))
    for it in range(n):
        rng.shuffle(idx)
        h1s, h2s, board = idx[0:2], idx[2:4], idx[4:9]
        c1 = pre_class([DECK_STR[i] for i in h1s])
        c2 = pre_class([DECK_STR[i] for i in h2s])
        w = _win([deck_t[i] for i in h1s], [deck_t[i] for i in h2s],
                 [deck_t[i] for i in board])
        num[c1, c2] += w; den[c1, c2] += 1
    return num, den


def norm_rows(m):
    s = m.sum(axis=1, keepdims=True)
    s[s == 0] = 1
    return m / s


def main():
    t0 = time.time()
    out_dir = HERE / 'data'
    out_dir.mkdir(exist_ok=True)

    chunks = [(N_MAIN // N_JOBS, SEED + i) for i in range(N_JOBS)]
    pre_chunks = [(N_PRE // N_JOBS, SEED + 1000 + i) for i in range(N_JOBS)]
    with Pool(N_JOBS) as p:
        print('[1/2] 메인 패스 (버킷 전이 + 스트리트 에퀴티) ...', flush=True)
        rs = p.map(job_main, chunks)
        print(f'  ( 50.0%) 메인 패스 완료 {time.time()-t0:.0f}s', flush=True)
        print('[2/2] 프리플랍 에퀴티 경량 패스 ...', flush=True)
        rp = p.map(job_pre_equity, pre_chunks)
        print(f'  (100.0%) 전 패스 완료 {time.time()-t0:.0f}s', flush=True)

    T0 = sum(r[0] for r in rs); T1 = sum(r[1] for r in rs); T2 = sum(r[2] for r in rs)
    EQ = []
    for st in range(3):
        n = sum(r[3][st] for r in rs); d = sum(r[4][st] for r in rs)
        d2 = d.copy(); d2[d2 == 0] = 1
        EQ.append(n / d2)
    pn = sum(r[0] for r in rp); pd = sum(r[1] for r in rp)
    pd2 = pd.copy(); pd2[pd2 == 0] = 1
    EQ0 = pn / pd2

    np.savez_compressed(
        out_dir / f'matrices_k{K}.npz',
        T0=norm_rows(T0), T1=norm_rows(T1), T2=norm_rows(T2),
        EQ0=EQ0, EQ1=EQ[0], EQ2=EQ[1], EQ3=EQ[2],
        meta=np.array([K, N_MAIN, N_PRE, SEED]))

    with open(out_dir / f'_matrices_log_k{K}.txt', 'w', encoding='utf-8') as f:
        f.write(f'K={K} n_main={N_MAIN} n_pre={N_PRE} seed={SEED} '
                f'elapsed={time.time()-t0:.0f}s\n')
        f.write(f'T0 row-sum check: {norm_rows(T0).sum(axis=1).mean():.4f}\n')
        f.write(f'EQ3 대각 평균(동일 버킷쌍 ≈ 0.5): {np.diag(EQ[2]).mean():.4f}\n')
        f.write(f'EQ3[최강,최약] ≈ 1: {EQ[2][K-1,0]:.4f} / EQ3[최약,최강] ≈ 0: {EQ[2][0,K-1]:.4f}\n')
        f.write(f'EQ0 AA(={PRE_IDX["AA"]}) vs 랜덤 평균: {EQ0[PRE_IDX["AA"]].mean():.4f}\n')
    print(f'saved matrices_k{K}.npz | {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
