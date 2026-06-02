"""
25번 온도 스윕 4조건(+19번 기준) Q테이블 미탐색/FOLD동률 셀 비교.

테이블: q[round=4][pos=2][state=8][prevaction=4][action=8]
Action: 0=FOLD 1=CHECK 2=CALL 3=R25 4=R50 5=R75 6=R100 7=ALLIN

핵심 측정:
  - zero_cells          : q==0 셀 수(미학습)
  - ctx_all_zero        : 8액션 전부 q==0 컨텍스트(완전 미학습)
  - ctx_greedy_tie0     : greedy max==0 동률 → tie-break(=FOLD) 위임 컨텍스트
  - ctx_fold_call_tie0  : FOLD·CALL 둘 다 합법 가정에서 max==0 동률 (1순위 문제 셀)
  - greedy FOLD argmax  : raw greedy가 FOLD를 고르는 컨텍스트 수
"""
import pickle
import sys
from collections import Counter

EPS = 1e-12
NR, NP, NS, NPA, NA = 4, 2, 8, 4, 8
AN = ["FOLD", "CHECK", "CALL", "R25", "R50", "R75", "R100", "ALLIN"]

RUNS = [
    ("19_base", r"results/19_mc_prop_softmax_prev_2000k/eval_results.pkl"),
    ("25a_base", r"results/25a_temp_baseline_2000k/eval_results.pkl"),
    ("25b_Thi", r"results/25b_temp_hi_2000k/eval_results.pkl"),
    ("25c_Tslow", r"results/25c_temp_slow_2000k/eval_results.pkl"),
    ("25d_Tfloor", r"results/25d_temp_floor_2000k/eval_results.pkl"),
]


def pct(a, b):
    return f"{100*a/b:.1f}%" if b else "n/a"


def analyze(q):
    total_cells = zero_cells = 0
    contexts = ctx_all_zero = ctx_greedy_tie0 = 0
    greedy = Counter()
    for r in range(NR):
        for p in range(NP):
            for s in range(NS):
                for pa in range(NPA):
                    contexts += 1
                    row = q[r][p][s][pa]
                    if all(abs(v) < EPS for v in row):
                        ctx_all_zero += 1
                    mx = max(row)
                    if abs(mx) < EPS and sum(1 for v in row if abs(v - mx) < EPS) > 1:
                        ctx_greedy_tie0 += 1
                    greedy[AN[row.index(mx)]] += 1
                    for a in range(NA):
                        total_cells += 1
                        if abs(row[a]) < EPS:
                            zero_cells += 1
    return dict(total_cells=total_cells, zero_cells=zero_cells, contexts=contexts,
                ctx_all_zero=ctx_all_zero, ctx_greedy_tie0=ctx_greedy_tie0,
                greedy=greedy)


rows = []
for name, path in RUNS:
    try:
        d = pickle.load(open(path, "rb"))
    except FileNotFoundError:
        print(f"[skip] {name}: {path} 없음")
        continue
    q = d["q"]
    rows.append((name, analyze(q)))

print("=" * 92)
hdr = f"{'run':<12} {'q==0셀':>10} {'미학습ctx':>10} {'FOLD동률ctx':>12} {'greedy_FOLD':>12} {'greedy_CALL':>12}"
print(hdr)
print("-" * 92)
for name, m in rows:
    g = m["greedy"]
    print(f"{name:<12} "
          f"{m['zero_cells']:>5d}/{m['total_cells']:<4d} "
          f"{m['ctx_all_zero']:>4d}/{m['contexts']:<4d} "
          f"{m['ctx_greedy_tie0']:>5d}/{m['contexts']:<4d}   "
          f"{g['FOLD']:>11d} {g['CALL']:>12d}")
print("=" * 92)

print("\nraw greedy(어댑터 없음) argmax 액션 분포 (256 컨텍스트):")
alla = ["FOLD", "CHECK", "CALL", "R25", "R50", "R75", "R100", "ALLIN"]
hdr2 = f"{'run':<12}" + "".join(f"{a:>7}" for a in alla)
print(hdr2)
print("-" * len(hdr2))
for name, m in rows:
    g = m["greedy"]
    print(f"{name:<12}" + "".join(f"{g[a]:>7d}" for a in alla))
print("=" * 92)
