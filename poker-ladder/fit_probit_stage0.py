# -*- coding: utf-8 -*-
"""0단계 probit 적합 — 검정력 보정층(Φ) 검증 + 게이트 A/B 사전 등록 예측 산출.

입력: results/34_threshold_stage0/anchors.csv (앵커: 용량 v, 양수 k/n)
      results/34_threshold_stage0/samples_chec_<플랫폼>.csv (α_min·ε_min 방문가중 분포)
모형:
  (M1) 용량 log-probit  P(양수) = Φ((ln v − ln v50)/w)   — 축·플랫폼별 2모수
  (M2) 커버리지 연결    P(양수) = Φ((F(v) − θ)/w_F)      — F = 흡수 셀 방문가중 CDF
       F 는 플랫폼별 samples 에서 평가 → 플랫폼 간 이식이 성립하는지가 핵심 검정.
검정:
  ① M1 적합 α50 vs 임계 분석 med(α_min) 대조 (P1(a))
  ② M2 를 legacy8 α축으로 적합 → K축·타 플랫폼 out-of-sample 예측 대조
  ③ 게이트 A/B 예측 수치 산출 (사전 등록용 — 런 전 고정)

usage: python fit_probit_stage0.py
"""
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path(__file__).resolve().parent.parent / 'results' / '34_threshold_stage0'


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def load_samples(platform, mode='absorption'):
    rows = list(csv.DictReader(open(OUT / f'samples_chec_{platform}.csv',
                                    encoding='utf-8')))
    return [(float(r['alpha_min']), float(r['eps_min']), float(r['weight']))
            for r in rows if r['mode'] == mode]


def F_of(samples, x, key='alpha'):
    """방문가중 CDF — key='alpha' 는 α_min, 'eps' 는 ε_min(칩)."""
    i = 0 if key == 'alpha' else 1
    tot = sum(w for *_, w in samples)
    return sum(w for s in samples if s[i] < x for w in [s[2]]) / tot if tot else float('nan')


def fit_binom(points, pfun, grid1, grid2):
    """이항 MLE 그리드 탐색. points = [(x, k, n)], pfun(x, a, b) → p."""
    best = (-1e18, None, None)
    for a in grid1:
        for b in grid2:
            ll = 0.0
            for x, k, n in points:
                p = min(max(pfun(x, a, b), 1e-6), 1 - 1e-6)
                ll += k * math.log(p) + (n - k) * math.log(1 - p)
            if ll > best[0]:
                best = (ll, a, b)
    return best


def frange(a, b, step):
    out = []
    while a <= b + 1e-12:
        out.append(round(a, 6))
        a += step
    return out


def main():
    anchors = list(csv.DictReader(open(OUT / 'anchors.csv', encoding='utf-8')))
    for r in anchors:
        r['value'] = float(r['value'])
        r['n_seeds'] = int(r['n_seeds'])
        r['n_positive'] = int(r['n_positive'])

    # ── M1: legacy8 α축 log-probit (구코드 6-seed + 신코드 5-seed 병합) ──
    a_pts = [(r['value'], r['n_positive'], r['n_seeds']) for r in anchors
             if r['axis'] == 'alpha-checktime' and r['value'] > 0
             and r['platform'] in ('legacy8-A8-TAG', 'legacy8-A8-TAG-ladder')]
    ll, lnv50, w = fit_binom(a_pts,
                             lambda x, m, s: phi((math.log(x) - m) / s),
                             [math.log(v) for v in frange(0.05, 0.40, 0.005)],
                             frange(0.10, 1.50, 0.02))
    a50 = math.exp(lnv50)
    print(f"[M1 α축 log-probit, legacy8 병합 {len(a_pts)}점] "
          f"α50={a50:.3f}, w={w:.2f} (LL={ll:.1f})")

    samples = {p: load_samples(p) for p in
               ['legacy8-A8', 'k20-A8', 'k20-A12', 'k50-A12',
                'k20-A12-CFR', 'k50-A12-CFR']}
    med_l8 = sorted((a, wt) for a, _, wt in samples['legacy8-A8'])
    print(f"  ↔ 임계 분석 med(α_min) legacy8 = (별도 로그 참조) — P1(a) 대조는 아래 표")

    # ── M2: 커버리지 연결 Φ((F−θ)/w_F) — legacy8 α축으로 적합 ──
    def cov_pts(axis, platform_names, sample_key, xkey):
        pts = []
        for r in anchors:
            if r['axis'] != axis or r['value'] <= 0:
                continue
            if r['platform'] not in platform_names:
                continue
            Fv = F_of(samples[sample_key], r['value'], xkey)
            pts.append((Fv, r['n_positive'], r['n_seeds'], r['value']))
        return pts

    m2_train = cov_pts('alpha-checktime',
                       ('legacy8-A8-TAG', 'legacy8-A8-TAG-ladder'),
                       'legacy8-A8', 'alpha')
    ll2, theta, wf = fit_binom([(F, k, n) for F, k, n, _ in m2_train],
                               lambda F, t, s: phi((F - t) / s),
                               frange(0.30, 1.00, 0.01),
                               frange(0.03, 0.60, 0.01))
    print(f"[M2 커버리지-probit, legacy8 α축 {len(m2_train)}점] "
          f"θ={theta:.2f}, w_F={wf:.2f} (LL={ll2:.1f})")
    print("  적합점: " + " ".join(
        f"α={v:g}:F={F:.2f}→P̂={phi((F-theta)/wf):.2f}({k}/{n})"
        for F, k, n, v in sorted(m2_train, key=lambda t: t[3])))

    # ── out-of-sample: K축(legacy8) + 타 플랫폼 fixed5/chec_a30 ──
    print("\n[M2 out-of-sample 예측 vs 관측]")
    k_pts = cov_pts('K-fixed', ('legacy8-A8-TAG', 'legacy8-A8-TAG-rep33'),
                    'legacy8-A8', 'eps')
    for F, k, n, v in sorted(k_pts, key=lambda t: t[3]):
        p = phi((F - theta) / wf)
        print(f"  legacy8 K={v:>4g}칩: F={F:.2f} → P̂={p:.2f} "
              f"(기대 {p*n:.1f}/{n}) ↔ 관측 {k}/{n}")
    plat_map = {'K20-A8-TAG': 'k20-A8', 'K20-A12-TAG': 'k20-A12',
                'K50-A12-TAG': 'k50-A12', 'K20-A12-CFR': 'k20-A12-CFR',
                'K50-A12-CFR': 'k50-A12-CFR'}
    for pl, sk in plat_map.items():
        for r in anchors:
            if r['platform'] != pl or r['value'] <= 0:
                continue
            xkey = 'eps' if r['axis'] == 'K-fixed' else 'alpha'
            Fv = F_of(samples[sk], r['value'], xkey)
            p = phi((Fv - theta) / wf)
            lab = f"K={r['value']:g}칩" if xkey == 'eps' else f"α={r['value']:g}"
            print(f"  {pl:14s} {lab:8s}: F={Fv:.2f} → P̂={p:.2f} "
                  f"(기대 {p*r['n_seeds']:.1f}/{r['n_seeds']}) ↔ 관측 "
                  f"{r['n_positive']}/{r['n_seeds']}")

    # ── 게이트 A/B 사전 등록 예측 ──
    print("\n[게이트 A/B 사전 등록 예측 — k20-A12 플랫폼]")
    s12 = samples['k20-A12']
    for K in (8, 10, 20):
        Fv = F_of(s12, K, 'eps')
        p = phi((Fv - theta) / wf)
        print(f"  게이트A fixed K={K:>2}: F={Fv:.2f} → P̂={p:.2f} → 기대 양수 {p*5:.1f}/5")
    for al in (0.10, 0.15):
        Fv = F_of(s12, al, 'alpha')
        p = phi((Fv - theta) / wf)
        print(f"  게이트B chec α={al:.2f}: F={Fv:.2f} → P̂={p:.2f} → 기대 양수 {p*5:.1f}/5")


if __name__ == '__main__':
    main()
