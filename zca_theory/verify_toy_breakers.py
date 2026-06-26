# -*- coding: utf-8 -*-
"""ZCA 탈출 메커니즘 통제비교 (toy MDP) — VIC vs 노이즈 vs tie-break vs 고정페널티.

목적(논문 §7 단서 정량화): "흡수 탈출 자체는 여러 처방이 가능하나, 고정점이 진짜값
부호 쪽으로 가는가(informed)와 strict-ZCA(0 > 음수)를 푸는가가 갈린다"를 toy에서 분리.

setup는 verify_toy_zca.py와 동일:
  state s 에서 A1 ∈ {CHECK(invest 0), BET1(invest b=1)} 선택 → 강제 BET2(invest c=1) → 종단 payoff.
  진짜값 q*(CHECK)=-5 < q*(BET1)=-1 < 0  → 최적=BET1. 비례배분: Q(CHECK)→0(흡수), Q(BET1)→-0.5.

비교 메커니즘(전부 PROP credit 위에 얹음):
  std        : 표준 MC (대조군, ZCA 없음)
  prop       : 비례배분 (ZCA 발생)
  vic        : CHECK invest 0→ε (informed: 고정점이 ε/(ε+c)·μ_C, 부호=μ_C 따라감)
  noise      : prop Q에 결정시 Gauss(0,σ) 노이즈 (uninformed: 고정점 0 불변, argmax만 흔듦)
  tiebreak   : prop + "정확히 동률일 때만 CHECK 후순위" (strict 0>음수에는 미발동)
  fixedpen   : CHECK Q에서 상수 κ 차감 (uninformed magnitude: 부호는 강제 음, μ_C 무관)

핵심 예측:
  vic       → BET1 복원 (고정점 informed 음수)
  noise     → CHECK 우세 잔존 (Q(CHECK)=0 > Q(BET1)=-0.5 라 노이즈는 오히려 열등 선택 다수)
  tiebreak  → CHECK 잔존 (0 ≠ -0.5 라 동률 아님 → 규칙 미발동 → 흡수 그대로)
  fixedpen  → κ>0.5면 복원하나 부호만 맞을 뿐 크기 무정보 (다중 μ_C에 단일 κ 부적응)
"""
import random
import math

random.seed(0)
N = 400_000
b, c = 1.0, 1.0
MEAN_CHECK, MEAN_BET1 = -5.0, -1.0
NOISE_PAYOFF = 3.0
EPS = 1.0          # VIC 가상투자
SIGMA = 1.0        # noise 처방의 결정시 노이즈 표준편차
KAPPA = 1.0        # fixedpen 차감 상수


def prop_Q(a1):
    """비례배분 고정점 Q(s,a1) = inv/(inv+c) * mu."""
    inv = 0.0 if a1 == "CHECK" else b
    mu = MEAN_CHECK if a1 == "CHECK" else MEAN_BET1
    return (inv / (inv + c)) * mu


def std_Q(a1):
    return MEAN_CHECK if a1 == "CHECK" else MEAN_BET1


def vic_Q(a1):
    inv = EPS if a1 == "CHECK" else b      # CHECK invest 0→EPS
    mu = MEAN_CHECK if a1 == "CHECK" else MEAN_BET1
    return (inv / (inv + c)) * mu


# 결정론적 고정점 기반 greedy 선택률 (noise만 표본추출 필요)
def pick_rate_deterministic(Qfn):
    qc, qb = Qfn("CHECK"), Qfn("BET1")
    return ("BET1" if qb > qc else "CHECK"), qc, qb


def pick_rate_noise():
    """prop 고정점에 결정시 노이즈. BET1 선택 빈도 추정."""
    qc, qb = prop_Q("CHECK"), prop_Q("BET1")   # 0, -0.5
    bet = 0
    for _ in range(N):
        ec = qc + random.gauss(0, SIGMA)
        eb = qb + random.gauss(0, SIGMA)
        if eb > ec:
            bet += 1
    return bet / N, qc, qb


def pick_tiebreak():
    """prop + 정확 동률일 때만 CHECK 후순위. 0 != -0.5 → 미발동."""
    qc, qb = prop_Q("CHECK"), prop_Q("BET1")
    if abs(qc - qb) < 1e-12:      # 동률일 때만 BET 우선
        return "BET1", qc, qb
    return ("BET1" if qb > qc else "CHECK"), qc, qb


def pick_fixedpen():
    qc, qb = prop_Q("CHECK") - KAPPA, prop_Q("BET1")
    return ("BET1" if qb > qc else "CHECK"), qc, qb


print(f"진짜값 q*: CHECK=-5.0 BET1=-1.0 → 최적=BET1   (b={b} c={c} eps={EPS} sigma={SIGMA} kappa={KAPPA})\n")
print(f"{'mechanism':<12}{'Q(CHECK)':>11}{'Q(BET1)':>11}{'P(pick BET1)':>14}  {'greedy':>7}  판정")
print("-" * 78)

# std
pick, qc, qb = pick_rate_deterministic(std_Q)
print(f"{'std':<12}{qc:>11.3f}{qb:>11.3f}{(1.0 if pick=='BET1' else 0.0):>14.3f}  {pick:>7}  대조군(ZCA없음·최적)")
# prop
pick, qc, qb = pick_rate_deterministic(prop_Q)
print(f"{'prop(ZCA)':<12}{qc:>11.3f}{qb:>11.3f}{(1.0 if pick=='BET1' else 0.0):>14.3f}  {pick:>7}  ★흡수(열등 CHECK)")
# vic
pick, qc, qb = pick_rate_deterministic(vic_Q)
print(f"{'vic':<12}{qc:>11.3f}{qb:>11.3f}{(1.0 if pick=='BET1' else 0.0):>14.3f}  {pick:>7}  복원(informed 음수)")
# noise
rate, qc, qb = pick_rate_noise()
pick = "BET1" if rate > 0.5 else "CHECK"
print(f"{'noise':<12}{qc:>11.3f}{qb:>11.3f}{rate:>14.3f}  {pick:>7}  미복원(고정점0 불변·열등 다수)")
# tiebreak
pick, qc, qb = pick_tiebreak()
print(f"{'tiebreak':<12}{qc:>11.3f}{qb:>11.3f}{(1.0 if pick=='BET1' else 0.0):>14.3f}  {pick:>7}  미복원(strict 0>음수엔 미발동)")
# fixedpen
pick, qc, qb = pick_fixedpen()
print(f"{'fixedpen':<12}{qc:>11.3f}{qb:>11.3f}{(1.0 if pick=='BET1' else 0.0):>14.3f}  {pick:>7}  복원하나 무정보(부호만)")
print("-" * 78)
print("결론: ZCA 탈출은 vic/fixedpen만, tiebreak는 strict 흡수에 미발동, noise는 열등 잔존.")
print("      vic만 '고정점이 진짜값 부호로(informed)' + strict 흡수 해소 둘 다 충족.")
