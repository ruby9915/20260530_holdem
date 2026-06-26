# -*- coding: utf-8 -*-
"""ZCA 고정점 toy 증명의 수치 검증.

설정 (2-스텝 에피소드, 결정상태 s에서 한 번만 선택):
  state s 에서 A1 ∈ {CHECK(invest 0), BET1(invest b)} 선택
  → 이후 state s2 에서 강제 BET2(invest c)   [두 번째 invested 행동 — 비례배분 분모 형성]
  → 종단 payoff P (A1 분기에 따라 분포 다름)

핵심 수: CHECK 분기는 '실제로 더 나쁨'(평균 -5)이지만, 비례배분에서 CHECK invest=0이라
  R_CHECK=(0/(0+c))*P=0 → Q_prop(CHECK)→0 (진짜값 -5와 무관·구조적 고정).
  반면 BET1(진짜 -1, 더 좋음)은 R_BET1=(b/(b+c))*P → 음수.
  → greedy_prop 는 0 > 음수 라 CHECK(열등) 선택 = '흡수'.
  표준 MC 는 Q→진짜값 → BET1(우월) 선택 = 정상.
  VIC(CHECK invest 0→1)는 CHECK에 음의 credit 부여 → 순서 복원.

진짜값(γ=1, 종단보상만): q*(s,A1)=E[P|A1].  설정: q*(CHECK)=-5 < q*(BET1)=-1 → 최적=BET1.
"""
import random
import sys

# Windows cp949 콘솔에서 ≈·− 등 유니코드 출력 시 크래시 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

random.seed(0)
N = 400_000
b, c = 1.0, 1.0          # invest 액수
MEAN_CHECK, MEAN_BET1 = -5.0, -1.0   # 분기별 종단 payoff 평균 (CHECK가 진짜 더 나쁨)
NOISE = 3.0              # payoff 분산 (MC 평균이 의미있도록)

def episode_payoff(mean):
    return mean + random.gauss(0.0, NOISE)

def credit(scheme, invest_a1, total_invest, payoff):
    if scheme == "std":          # 표준 MC: 종단보상 그대로(γ=1)
        return payoff
    if scheme == "prop":         # 비례배분: CHECK는 invest_a1=0 → (0/total)*P=0 이 매 표본 정확히 0
        # (분산 0). 즉 Q(CHECK)→0 은 sampling 평균의 우연이 아니라 구조적 영-고정(방문 수 무관).
        return (invest_a1 / total_invest) * payoff if total_invest > 0 else payoff
    if scheme == "vic":          # VIC: CHECK invest 0→1 은 호출부에서 처리
        return (invest_a1 / total_invest) * payoff if total_invest > 0 else payoff

# 각 A1 을 고정으로 두고 step-1 행동의 Q (=credit 평균) 추정
def estimate_Q(a1):
    inv_a1 = 0.0 if a1 == "CHECK" else b
    mean   = MEAN_CHECK if a1 == "CHECK" else MEAN_BET1
    acc = {"std": 0.0, "prop": 0.0, "vic": 0.0}
    for _ in range(N):
        P = episode_payoff(mean)
        # std / prop : CHECK invest=0
        total_prop = inv_a1 + c
        acc["std"]  += credit("std",  inv_a1, total_prop, P)
        acc["prop"] += credit("prop", inv_a1, total_prop, P)
        # vic : CHECK invest 0→1 (BET1 은 그대로 b)
        inv_a1_vic = 1.0 if a1 == "CHECK" else b
        total_vic  = inv_a1_vic + c
        acc["vic"] += credit("vic", inv_a1_vic, total_vic, P)
    return {k: v / N for k, v in acc.items()}

Qc = estimate_Q("CHECK")
Qb = estimate_Q("BET1")

print(f"진짜값 q*:        CHECK=-5.0   BET1=-1.0   → 최적=BET1\n")
print(f"{'scheme':<8}{'Q(CHECK)':>12}{'Q(BET1)':>12}   greedy 선택   판정")
print("-" * 60)
for s in ("std", "prop", "vic"):
    qc, qb = Qc[s], Qb[s]
    pick = "CHECK" if qc > qb else "BET1"
    ok = "정상(최적 BET1)" if pick == "BET1" else "★흡수(열등 CHECK)"
    print(f"{s:<8}{qc:>12.3f}{qb:>12.3f}   {pick:>8}     {ok}")
print("-" * 60)
print("기대: std→BET1(정상) / prop→CHECK(흡수, Q(CHECK)≈0≠-5) / vic→BET1(복원)")
