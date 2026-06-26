# -*- coding: utf-8 -*-
"""ZCA 계열 일반화 toy — "invest 공식 버그"가 아니라 "기여도-비례 credit 계열의 구조적 함정"임을 보인다.

같은 toy(CHECK invest 0 / BET1 invest b / 강제 BET2 invest c, 진짜값 μ_C=-5 < μ_B=-1 < 0)에서
기여도 함수 φ만 바꿔 credit(a) = φ(a)/Σφ · P 의 MC 고정점 Q를 비교한다.

핵심 주장:
  ZCA(영-고정점 흡수) ⟺ φ(비용0 행동)=0.
  - invest(칩), aggression(베팅이면 1 아니면 0): 둘 다 φ(CHECK)=0 → Q(CHECK)→0 → ZCA.
    (aggression은 '칩'과 무관한 구조적으로 다른 φ인데도 ZCA → invest 특정 아님)
  - uniform(모든 행동 1): φ(CHECK)=1≠0 → Q(CHECK)→μ_C/2≠0 → 면역.
  - std(표준 MC, return-equivalent): Q→진짜값 → 면역. (RUDDER 정리의 안전 영역)
즉 ZCA = "return-equivalence를 깨고(분산↓) + 비용0 행동을 0으로" 두는 비례 credit의 함정
   = Shapley null-player 공리(기여 0→배분 0)를 *가치학습 신호*로 쓸 때의 그림자.
"""
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

random.seed(0)
N = 400_000
b, c = 1.0, 1.0
MEAN = {'CHECK': -5.0, 'BET1': -1.0}   # 분기별 종단 payoff 평균 (CHECK가 진짜 더 나쁨)
NOISE = 3.0

# 기여도 함수 φ: 행동유형 → 가중치. BET2는 강제 후속(투자 c).
PHI = {
    'invest':     {'CHECK': 0.0, 'BET1': b,   'BET2': c},    # 칩 투자액
    'aggression': {'CHECK': 0.0, 'BET1': 1.0, 'BET2': 1.0},  # 베팅=1, 체크=0 (칩과 무관)
    'uniform':    {'CHECK': 1.0, 'BET1': 1.0, 'BET2': 1.0},  # 모든 행동 동일 기여
}
DESC = {
    'std':        '표준 MC (return-equivalent)',
    'invest':     '비례배분: φ=invest(칩)',
    'aggression': '비례배분: φ=aggression(베팅 여부)',
    'uniform':    '비례배분: φ=uniform(균등)',
}


def credit(scheme, a1, P):
    if scheme == 'std':           # 분해 없음 = return-equivalent
        return P
    phi = PHI[scheme]
    return phi[a1] / (phi[a1] + phi['BET2']) * P


def estimate(scheme):
    Q = {}
    for a1 in ('CHECK', 'BET1'):
        s = 0.0
        for _ in range(N):
            P = MEAN[a1] + random.gauss(0.0, NOISE)
            s += credit(scheme, a1, P)
        Q[a1] = s / N
    return Q


print("진짜값:  CHECK=-5.0   BET1=-1.0   → 최적=BET1\n")
print(f"{'기여도 함수 φ':<34}{'φ(CHECK)':>9}{'Q(CHECK)':>11}{'Q(BET1)':>10}  {'greedy':>6}  ZCA?")
print("-" * 84)
for sc in ('std', 'invest', 'aggression', 'uniform'):
    Q = estimate(sc)
    phichk = '—' if sc == 'std' else f"{PHI[sc]['CHECK']:.0f}"
    pick = 'CHECK' if Q['CHECK'] > Q['BET1'] else 'BET1'
    zca = '★있음(열등 CHECK)' if pick == 'CHECK' else '없음(최적 BET1)'
    print(f"{DESC[sc]:<34}{phichk:>9}{Q['CHECK']:>11.3f}{Q['BET1']:>10.3f}  {pick:>6}  {zca}")
print("-" * 84)
print("결론: ZCA ⟺ φ(CHECK)=0.  invest·aggression(φ(CHECK)=0)은 ZCA, uniform·std(return-equivalent)는 면역.")
print("      → 'invest 공식'이 아니라 '비용0 행동에 0을 주는 비(非)return-equivalent 비례 credit' 일반의 함정.")
