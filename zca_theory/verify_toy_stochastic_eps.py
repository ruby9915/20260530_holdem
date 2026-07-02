# -*- coding: utf-8 -*-
"""V2 — 확률적 팟 규모 C에서 고정 ε vs 팟-비례 ε(α×C)의 임계 검증.

실험 관측(fixed-1칩 무효 · 저α 무효 · α=30% 유효)의 toy 대응물.
핵심 구조: 실제 포커에서 베팅(공격)의 invest는 팟-비례(b=β×C)라 credit 비중이
C-불변인 반면, 고정 ε의 CHECK 비중 ε/(ε+C)는 큰 팟에서 소멸한다.
  fixed ε   : Q(CHECK)=E[ε/(ε+C)]·μ_C  → C↑에서 0으로 → 흡수 잔존
  α-비례 ε  : Q(CHECK)=[α/(α+1)]·μ_C   → C-불변       → α > k/(1−k)면 일관 복원
C∈{50,200,400}(칩), β=0.5(팟의 절반 베팅), μ_C=−5 < μ_B=−1 (최적=BET).
"""
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

random.seed(0)
N = 400_000
BETA = 0.5                    # BET invest = β×C (팟-비례 베팅)
CS = [50.0, 200.0, 400.0]     # 팟 규모 혼합 (실제 스케일)
MEAN_CHECK, MEAN_BET1 = -5.0, -1.0
NOISE = 3.0
# BET credit 비중 = βC/(βC+C) = β/(β+1) (C-불변)
Q_BET_SHARE = BETA / (BETA + 1.0)


def estimate(mode, val):
    acc = {'CHECK': 0.0, 'BET1': 0.0}
    for a1 in ('CHECK', 'BET1'):
        mean = MEAN_CHECK if a1 == 'CHECK' else MEAN_BET1
        for _ in range(N):
            C = random.choice(CS)
            P = mean + random.gauss(0.0, NOISE)
            if a1 == 'BET1':
                inv = BETA * C
            else:
                inv = val if mode == 'fixed' else val * C
            acc[a1] += (inv / (inv + C)) * P
    return acc['CHECK'] / N, acc['BET1'] / N


print(f"참값: CHECK=-5 < BET1=-1 → 최적=BET1.  C∈{CS}, BET invest=β×C(β={BETA})")
print(f"이론: Q(BET1)={Q_BET_SHARE:.3f}×(-1)={-Q_BET_SHARE:.3f} (C-불변)\n")
print(f"{'개입':<16}{'Q(CHECK)':>10}{'Q(BET1)':>10}  greedy  판정")
print("-" * 62)
for mode, val, lbl in [('fixed', 1.0, 'fixed ε=1칩'), ('fixed', 5.0, 'fixed ε=5칩'),
                       ('potfrac', 0.05, 'α=5%×C'), ('potfrac', 0.10, 'α=10%×C'),
                       ('potfrac', 0.30, 'α=30%×C')]:
    qc, qb = estimate(mode, val)
    pick = 'CHECK' if qc > qb else 'BET1'
    mark = '복원' if pick == 'BET1' else '★흡수 잔존'
    print(f"{lbl:<16}{qc:>10.3f}{qb:>10.3f}  {pick:>6}  {mark}")
print("-" * 62)
print("결론: 팟이 크고 베팅이 팟-비례인 환경에서 고정 소액 ε은 희석돼 흡수 잔존,")
print("      팟-비례 ε는 비중이 C-불변이라 임계 α 초과 시 일관 복원.")
print("      → 'fixed-1 무효 / 저α 무효 / α30% 유효' 실험 관측의 toy 대응.")
