# -*- coding: utf-8 -*-
"""V1 — ZCA 거울상(+EV 체크 은폐) 모드 검증.

기존 Theorem(μ_C<μ_B<0)은 "0이 음수를 흡수"만 다뤘고, §5 주석은 "+EV 행동이 있으면
무해"라 했다. 그러나 Lemma 2는 부호 무관(∀μ_C)이므로 거울상이 존재한다:
  CHECK가 참-최선(μ_C>μ_B>0)인 결정 상태에서 Q_prop(CHECK)=0 < (b/(b+c))μ_B
  → greedy가 열등한 +EV BET을 선택 = "+EV 체크 은폐(masking)".
VIC 복원 조건은 흡수 모드와 동일 형태: ε/(ε+c) > k, k=(b/(b+c))(μ_B/μ_C)∈(0,1)
  ⇔ ε > ε_min = kc/(1−k).  (μ 부호가 둘 다 양수라 부등호 방향 유지)
실측된 트랩 사례(off: 잼 3.9 → pot-VIC: 체크 19.8)가 정확히 이 모드다.
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
MEAN_CHECK, MEAN_BET1 = +5.0, +1.0    # 거울상: CHECK가 참-최선(+5), BET도 +EV(+1)
NOISE = 3.0
k = (b / (b + c)) * (MEAN_BET1 / MEAN_CHECK)
EPS_MIN = k * c / (1 - k)


def q(scheme, a1, eps=1.0):
    inv = {'CHECK': (eps if scheme == 'vic' else 0.0), 'BET1': b}[a1]
    mean = {'CHECK': MEAN_CHECK, 'BET1': MEAN_BET1}[a1]
    s = 0.0
    for _ in range(N):
        P = mean + random.gauss(0.0, NOISE)
        s += P if scheme == 'std' else (inv / (inv + c)) * P
    return s / N


print(f"참값: CHECK=+5(최선) BET1=+1  |  k={k:.3f}  ε_min={EPS_MIN:.3f}\n")
print(f"{'scheme':<10}{'Q(CHECK)':>10}{'Q(BET1)':>10}  greedy  판정")
print("-" * 58)
for sc in ('std', 'prop'):
    qc, qb = q(sc, 'CHECK'), q(sc, 'BET1')
    pick = 'CHECK' if qc > qb else 'BET1'
    ok = '정상(최선 CHECK)' if pick == 'CHECK' else '★은폐(+EV 열등 BET)'
    print(f"{sc:<10}{qc:>10.3f}{qb:>10.3f}  {pick:>6}  {ok}")
for eps in (0.05, EPS_MIN * 0.999, EPS_MIN * 1.02, 0.5, 1.0):
    qc, qb = q('vic', 'CHECK', eps), q('vic', 'BET1', eps)
    pick = 'CHECK' if qc > qb else 'BET1'
    mark = '복원' if pick == 'CHECK' else '은폐 잔존'
    print(f"vic ε={eps:<5.3f}{qc:>9.3f}{qb:>10.3f}  {pick:>6}  {mark} (임계 {'초과' if eps > EPS_MIN else '미달'})")
print("-" * 58)
print("결론: ZCA는 음수 흡수만이 아니라 +EV 체크 은폐도 만든다(양방향 오순위).")
print("      VIC 임계식은 두 모드에서 동일: ε > ε_min = kc/(1-k).")
