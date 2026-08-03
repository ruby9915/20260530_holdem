# -*- coding: utf-8 -*-
"""게이트 B 기각 후 수리 검증 — 방문수 필터(nmin) sweep 의 전 앵커 재대조.

수리 가설: 훈련 저방문 행동의 Q 잡음이 "작은 임계로 풀리는 셀" 질량을 부풀림
           → n(s,a) ≥ nmin 필터로 지도를 다시 그리면 게이트 B 예측이 관측에 접근.
성공 기준 (사전 고정):
  ① 게이트 B 두 점(α=0.10→1/5, 0.15→2/5)의 |기대−관측| ≤ 1.0 시드
  ② 기존 적중점(게이트 A 3점 · legacy8 K축 8점 · 타 플랫폼 10점)의 적중 유지
     (적중 = |기대−관측| ≤ 1.0 시드; 수리로 새 실패 ≤ 1점 허용)
  ③ M2 재적합은 legacy8 α축(훈련셋)에서만 — 나머지는 전부 out-of-sample.
어느 nmin 도 ①②를 못 채우면 "방문수 필터 가설 기각"으로 정직 보고.

usage: python fit_probit_repair.py
"""
import csv
import math
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path(__file__).resolve().parent.parent / 'results' / '34_threshold_stage0'


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def load_samples(tag, platform):
    f = OUT / f'samples_chec{tag}_{platform}.csv'
    rows = list(csv.DictReader(open(f, encoding='utf-8')))
    return [(float(r['alpha_min']), float(r['eps_min']), float(r['weight']))
            for r in rows if r['mode'] == 'absorption']


def F_of(samples, x, key):
    i = 0 if key == 'alpha' else 1
    tot = sum(s[2] for s in samples)
    return sum(s[2] for s in samples if s[i] < x) / tot if tot else float('nan')


def fit_binom(points, grids):
    best = (-1e18, None, None)
    for t in grids[0]:
        for s in grids[1]:
            ll = 0.0
            for F, k, n in points:
                p = min(max(phi((F - t) / s), 1e-6), 1 - 1e-6)
                ll += k * math.log(p) + (n - k) * math.log(1 - p)
            if ll > best[0]:
                best = (ll, t, s)
    return best


def frange(a, b, step):
    out = []
    while a <= b + 1e-12:
        out.append(round(a, 4))
        a += step
    return out


# 평가 대상 앵커 (v, k, n, 플랫폼샘플키, 축) — 게이트 관측 포함
TRAIN_L8 = [  # legacy8 α축 (M2 재적합 훈련셋)
    (0.01, 0, 1), (0.02, 0, 1), (0.04, 0, 6), (0.04, 0, 5), (0.06, 0, 1),
    (0.08, 3, 6), (0.08, 2, 5), (0.10, 1, 6), (0.10, 2, 5),
    (0.15, 2, 6), (0.15, 3, 5), (0.20, 5, 6), (0.20, 4, 5),
    (0.25, 1, 1), (0.30, 6, 6), (0.30, 5, 5), (0.50, 5, 5),
]
HOLDOUT = [
    # (라벨, 샘플키, 축, v, 관측k, n)
    ('게이트B α=0.10', 'k20-A12', 'alpha', 0.10, 1, 5),
    ('게이트B α=0.15', 'k20-A12', 'alpha', 0.15, 2, 5),
    ('게이트A K=8',    'k20-A12', 'eps', 8, 5, 5),
    ('게이트A K=10',   'k20-A12', 'eps', 10, 5, 5),
    ('게이트A K=20',   'k20-A12', 'eps', 20, 5, 5),
    ('l8 K=1(구)',     'legacy8-A8', 'eps', 1, 2, 6),
    ('l8 K=1(신)',     'legacy8-A8', 'eps', 1, 1, 5),
    ('l8 K=5(구)',     'legacy8-A8', 'eps', 5, 5, 5),
    ('l8 K=5(신)',     'legacy8-A8', 'eps', 5, 5, 5),
    ('l8 K=20(구)',    'legacy8-A8', 'eps', 20, 5, 5),
    ('l8 K=20(신)',    'legacy8-A8', 'eps', 20, 4, 5),
    ('l8 K=60(구)',    'legacy8-A8', 'eps', 60, 5, 5),
    ('l8 K=60(신)',    'legacy8-A8', 'eps', 60, 4, 5),
    ('k20A8 fixed5',   'k20-A8', 'eps', 5, 5, 5),
    ('k20A8 chec30',   'k20-A8', 'alpha', 0.30, 5, 5),
    ('k20A12 fixed5',  'k20-A12', 'eps', 5, 2, 5),
    ('k20A12 chec30',  'k20-A12', 'alpha', 0.30, 5, 5),
    ('k50A12 fixed5',  'k50-A12', 'eps', 5, 5, 5),
    ('k50A12 chec30',  'k50-A12', 'alpha', 0.30, 5, 5),
    ('k20CFR fixed5',  'k20-A12-CFR', 'eps', 5, 5, 5),
    ('k20CFR chec30',  'k20-A12-CFR', 'alpha', 0.30, 5, 5),
    ('k50CFR fixed5',  'k50-A12-CFR', 'eps', 5, 5, 5),
    ('k50CFR chec30',  'k50-A12-CFR', 'alpha', 0.30, 5, 5),
]
PLATS = ['legacy8-A8', 'k20-A8', 'k20-A12', 'k50-A12', 'k20-A12-CFR', 'k50-A12-CFR']


def evaluate(tag, label):
    S = {p: load_samples(tag, p) for p in PLATS}
    train = [(F_of(S['legacy8-A8'], v, 'alpha'), k, n) for v, k, n in TRAIN_L8]
    ll, theta, wf = fit_binom(train, (frange(0.10, 1.0, 0.01), frange(0.03, 0.6, 0.01)))
    print(f"\n=== {label}: M2 재적합 θ={theta:.2f} w_F={wf:.2f} (LL={ll:.1f}) ===")
    gateB_ok, misses = 0, []
    for lab, key, axis, v, k, n in HOLDOUT:
        Fv = F_of(S[key], v, axis)
        exp = phi((Fv - theta) / wf) * n
        hit = abs(exp - k) <= 1.0
        mark = 'O' if hit else 'X'
        if lab.startswith('게이트B') and hit:
            gateB_ok += 1
        if not hit:
            misses.append(lab)
        print(f"  [{mark}] {lab:14s} F={Fv:.2f} 기대 {exp:.1f}/{n} ↔ 관측 {k}/{n}")
    others_miss = [m for m in misses if not m.startswith('게이트B')]
    verdict = '성공' if (gateB_ok == 2 and len(others_miss) <= 1) else '실패'
    print(f"  → 게이트B 적중 {gateB_ok}/2, 기타 실패 {len(others_miss)}점"
          f"{'(' + ', '.join(others_miss) + ')' if others_miss else ''} — 수리 {verdict}")
    return verdict, gateB_ok, others_miss


def main():
    evaluate('', '기준선(필터 없음, 0단계 지도)')
    for nmin in (10, 30, 100):
        evaluate(f'_n{nmin}', f'수리안 nmin={nmin}')


if __name__ == '__main__':
    main()
