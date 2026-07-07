# -*- coding: utf-8 -*-
"""percentile E[HS] 버킷 경계 사전계산 (32번 실험, 사다리 1단 — 실험일지 35절).

정의 (Johanson et al. 2013, AAMAS):
  HS  = 보드 완성 시 균등 무작위 상대 핸드보다 강할 확률 (무승부 0.5)
  E[HS] = 잔여 보드 롤아웃에 대한 HS의 기댓값 (MC: 상대+런아웃 결합 표본 — 평균 동일)
  percentile 버킷 = E[HS] 기준 등질량 K등분

산출물 (모든 런이 공유 — 재현성):
  ehs_buckets_k{K}.json
    preflop: 169 canonical 클래스 → {ehs, bucket}  (콤보 수 가중 등질량: pair 6·suited 4·offsuit 12)
    flop/turn/river: E[HS] 경계값 K-1개 (균등 무작위 상황 표본의 분위수)
  ../results/32_ehs_k20/_precompute_log.txt: 파라미터·분포 통계·소요시간

usage: python precompute_ehs_buckets.py [K=20] [n_pre=3000] [n_sit=30000] [n_roll=150]
RNG: 고정 seed 20260707 (스트리트별 파생 seed) — 결정론적 재생성 보장.
"""
import json
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from treys import Card as TC, Evaluator

K       = int(sys.argv[1]) if len(sys.argv) > 1 else 20
N_PRE   = int(sys.argv[2]) if len(sys.argv) > 2 else 3000    # 프리플랍 클래스당 롤아웃
N_SIT   = int(sys.argv[3]) if len(sys.argv) > 3 else 30000   # 포스트플랍 스트리트당 상황 표본
N_ROLL  = int(sys.argv[4]) if len(sys.argv) > 4 else 150     # 상황당 롤아웃 (river는 +50)
SEED    = 20260707

RANKS = '23456789TJQKA'
SUITS = 'shdc'
DECK = [TC.new(r + s) for r in RANKS for s in SUITS]
HERE = Path(__file__).resolve().parent
OUT_JSON = HERE / f'ehs_buckets_k{K}.json'
OUT_LOG = HERE.parent / 'results' / '32_ehs_k20' / '_precompute_log.txt'

_ev = Evaluator()


def _hs(hero, board, opp):
    """단일 대전 HS: 승 1 / 무 0.5 / 패 0."""
    sh = _ev.evaluate(board, hero)
    so = _ev.evaluate(board, opp)
    return 1.0 if sh < so else (0.5 if sh == so else 0.0)


# ── 프리플랍: 169 canonical 클래스 ─────────────────────────
def preflop_classes():
    """(label, weight) — pair 6콤보 / suited 4 / offsuit 12."""
    out = []
    for i, r1 in enumerate(RANKS[::-1]):          # A..2
        for j, r2 in enumerate(RANKS[::-1]):
            if j < i:
                continue
            if r1 == r2:
                out.append((r1 + r2, 6))
            elif j > i:
                out.append((r1 + r2 + 's', 4))
                out.append((r1 + r2 + 'o', 12))
    return out


def _concrete(label, rng):
    """클래스 라벨 → 무작위 구체 콤보 (suit 효과 평균화)."""
    if len(label) == 2:                            # pair
        s1, s2 = rng.sample(SUITS, 2)
        return [TC.new(label[0] + s1), TC.new(label[1] + s2)]
    r1, r2, kind = label[0], label[1], label[2]
    if kind == 's':
        s = rng.choice(SUITS)
        return [TC.new(r1 + s), TC.new(r2 + s)]
    s1 = rng.choice(SUITS)
    s2 = rng.choice([x for x in SUITS if x != s1])
    return [TC.new(r1 + s1), TC.new(r2 + s2)]


def job_preflop(_):
    rng = random.Random(SEED)
    res = {}
    for label, w in preflop_classes():
        acc = 0.0
        for _ in range(N_PRE):
            hero = _concrete(label, rng)
            rest = [c for c in DECK if c not in hero]
            draw = rng.sample(rest, 7)             # opp 2 + board 5
            acc += _hs(hero, draw[2:], draw[:2])
        res[label] = (acc / N_PRE, w)
    return ('preflop', res)


# ── 포스트플랍: 스트리트별 E[HS] 분포 → 분위 경계 ──────────
def job_street(args):
    name, n_board, n_roll, seed = args
    rng = random.Random(seed)
    vals = []
    for _ in range(N_SIT):
        draw = rng.sample(DECK, 2 + n_board)
        hero, board = draw[:2], draw[2:]
        rest = [c for c in DECK if c not in draw]
        need = 5 - n_board                         # 남은 보드 장수
        acc = 0.0
        for _ in range(n_roll):
            d2 = rng.sample(rest, 2 + need)
            acc += _hs(hero, board + d2[2:], d2[:2])
        vals.append(acc / n_roll)
    vals.sort()
    cuts = [vals[int(len(vals) * q / K)] for q in range(1, K)]
    stats = (vals[0], vals[len(vals) // 2], vals[-1])
    return (name, {'cuts': cuts, 'min_med_max': stats})


def main():
    t0 = time.time()
    jobs = [('flop', 3, N_ROLL, SEED + 1), ('turn', 4, N_ROLL, SEED + 2),
            ('river', 5, N_ROLL + 50, SEED + 3)]
    with Pool(4) as p:
        pre_async = p.map_async(job_preflop, [None])
        street_res = p.map(job_street, jobs)
        pre_res = pre_async.get()

    out = {'meta': {'K': K, 'seed': SEED, 'n_pre': N_PRE, 'n_sit': N_SIT,
                    'n_roll': N_ROLL, 'def': 'percentile E[HS] (Johanson et al. 2013)'}}

    # 프리플랍: 콤보 가중 등질량 버킷 (0=최약 ~ K-1=최강)
    _, pre = pre_res[0]
    ordered = sorted(pre.items(), key=lambda kv: kv[1][0])
    total_w = sum(w for _, (_, w) in ordered)      # 1326
    out['preflop'], cum = {}, 0
    for label, (ehs, w) in ordered:
        bucket = min(K - 1, int(cum / total_w * K))
        out['preflop'][label] = {'ehs': round(ehs, 5), 'bucket': bucket}
        cum += w

    for name, d in street_res:
        out[name] = {'cuts': [round(c, 5) for c in d['cuts']]}

    OUT_JSON.write_text(json.dumps(out, indent=1), encoding='utf-8')

    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_LOG, 'w', encoding='utf-8') as f:
        f.write(f"precompute_ehs_buckets K={K} seed={SEED} "
                f"n_pre={N_PRE} n_sit={N_SIT} n_roll={N_ROLL}\n")
        f.write(f"elapsed {time.time()-t0:.0f}s\n")
        strongest = ordered[-1][0]; weakest = ordered[0][0]
        f.write(f"preflop: weakest {weakest} ehs={pre[weakest][0]:.3f} / "
                f"strongest {strongest} ehs={pre[strongest][0]:.3f}\n")
        for name, d in street_res:
            lo, med, hi = d['min_med_max']
            f.write(f"{name}: min/med/max = {lo:.3f}/{med:.3f}/{hi:.3f}, "
                    f"cuts[0]={d['cuts'][0]:.3f} cuts[-1]={d['cuts'][-1]:.3f}\n")
    print(f"done {time.time()-t0:.0f}s -> {OUT_JSON.name}")


if __name__ == '__main__':
    main()
