# -*- coding: utf-8 -*-
"""계측 런 투여 분석 — 훈련기 실효 지분 s(α)의 직접 실측 (수리 가설 2의 올바른 측정).

입력: results/34_threshold_stage0/doselog_a{15,30}_s1/dose.csv
  (ep, temp, t_real, checks="r:pot;...") — 학습 중 순수 관측 훅의 산출물.
분석:
  ① 온도 구간(T≥7 초기 / 3≤T<7 중기 / T<3 후기) × 라운드별 실효 지분
     s(α) = E[α·p_i / (t_real + α·Σp_j)]  (game.py:120-124 실산술 그대로)
  ② 올체크 핸드(t_real=0) 비율 — α 상쇄 국면의 질량
  ③ a15 vs a30 대조 + 나이브 근사 α/(1+α)·greedy 실측과의 3자 비교
  ④ 요구 지분 k 분포(stage0 지도에서 역산: k = α_min/(1+α_min))와 겹쳐
     "훈련 초기 s(0.15) 가 요구 지분을 넘는 셀 비중" = 수정 커버리지 산출
usage: python analyze_dose.py
"""
import csv
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

OUT = Path(__file__).resolve().parent.parent / 'results' / '34_threshold_stage0'
RNAMES = {0: 'PREFLOP', 1: 'FLOP', 2: 'TURN', 3: 'RIVER'}
ALPHAS = (0.10, 0.15, 0.30, 0.50)


def load(run):
    rows = []
    with open(OUT / run / 'dose.csv', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            checks = [(int(c.split(':')[0]), float(c.split(':')[1]))
                      for c in r['checks'].split(';')]
            rows.append((int(r['ep']), float(r['temp']), float(r['t_real']), checks))
    return rows


def phase_of(temp):
    return '초기(T≥7)' if temp >= 7 else ('중기(3≤T<7)' if temp >= 3 else '후기(T<3)')


def s_share(t_real, checks, p_i, alpha):
    sp = sum(p for _, p in checks)
    denom = t_real + alpha * sp
    return alpha * p_i / denom if denom > 0 else 0.0


def analyze(run, a_train):
    rows = load(run)
    print(f"=== {run} (α_학습={a_train}, 에피소드 표본 {len(rows):,}) ===")
    by_phase = defaultdict(list)
    allcheck = defaultdict(lambda: [0, 0])
    for ep, temp, t_real, checks in rows:
        ph = phase_of(temp)
        by_phase[ph].append((t_real, checks))
        allcheck[ph][0] += (1 if t_real == 0 else 0)
        allcheck[ph][1] += 1
    for ph in ('초기(T≥7)', '중기(3≤T<7)', '후기(T<3)'):
        eps_ = by_phase.get(ph, [])
        if not eps_:
            continue
        ac, tot = allcheck[ph]
        # 라운드별 s(α): 체크 단위 표본
        per_round = defaultdict(list)
        for t_real, checks in eps_:
            for r, p in checks:
                per_round[r].append((t_real, checks, p))
        print(f"  [{ph}] 에피소드 {tot:,} | 올체크(실투자 0) 비율 {ac/tot*100:.1f}%")
        for r in sorted(per_round):
            smp = per_round[r]
            line = f"    {RNAMES[r]:8s} n={len(smp):6,} | " + " ".join(
                f"s({a:g})={st.mean(s_share(t, c, p, a) for t, c, p in smp):.3f}"
                for a in ALPHAS)
            naive = " | 나이브 " + " ".join(f"{a/(1+a):.3f}" for a in ALPHAS)
            print(line + naive)
    print()
    return by_phase


def coverage_vs_required(run, by_phase, plat='k20-A12'):
    """stage0 지도의 요구 지분 k 분포와 초기 실효 지분을 겹쳐 수정 커버리지 계산."""
    f = OUT / f'samples_chec_{plat}.csv'
    ks = []
    for r in csv.DictReader(open(f, encoding='utf-8')):
        if r['mode'] != 'absorption':
            continue
        am = float(r['alpha_min'])
        ks.append((am / (1 + am), float(r['weight'])))   # k = α_min/(1+α_min)
    tot_w = sum(w for _, w in ks)
    early = by_phase.get('초기(T≥7)', []) + by_phase.get('중기(3≤T<7)', [])
    smp = [(t, c, p) for t, c in early for _, p in [(0, 0)] for r, p in c][:0]
    # 체크 단위 표본 (라운드 무시 병합 — 보수적 1차 근사)
    smp = [(t, c, p) for t, c in early for r, p in c]
    print(f"  [{run} → {plat} 수정 커버리지] 초·중기 체크 표본 {len(smp):,}")
    for a in ALPHAS:
        shares = sorted(s_share(t, c, p, a) for t, c, p in smp)
        med_s = shares[len(shares)//2] if shares else 0.0
        # 각 요구 지분 k 에 대해 "달성 확률" = P(s(α) ≥ k) — 표본 CDF
        def p_reach(k):
            import bisect
            i = bisect.bisect_left(shares, k)
            return 1 - i / len(shares) if shares else 0.0
        cov = sum(w * p_reach(k) for k, w in ks) / tot_w if tot_w else float('nan')
        print(f"    α={a:g}: 실효 지분 중앙값 {med_s:.3f} | "
              f"기대 커버리지(달성확률 가중) {cov:.2f}")


def main():
    bp15 = analyze('doselog_a15_s1', 0.15)
    bp30 = analyze('doselog_a30_s1', 0.30)
    print("=== 요구 지분 k 대비 수정 커버리지 (k20-A12) ===")
    coverage_vs_required('a15', bp15)
    coverage_vs_required('a30', bp30)


if __name__ == '__main__':
    main()
