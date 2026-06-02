"""
26번 성향별 단독학습 5종(+19번 기준) Q테이블 미탐색/FOLD동률 셀 비교.
_inspect_qcov_25.py 와 동일 측정, RUNS 만 교체.

핵심 가설:
  - 공격적 성향(lag/man)일수록 베팅직면 셀 도달↑ → 미학습ctx↓, FOLD동률ctx↓
  - sta 는 라운드 도달↑이나 베팅직면은 안 만듦
  - nit 은 상대가 거의 안 들어와 커버리지 낮을 것
"""
import pickle
from collections import Counter

EPS = 1e-12
NR, NP, NS, NPA, NA = 4, 2, 8, 4, 8
AN = ["FOLD", "CHECK", "CALL", "R25", "R50", "R75", "R100", "ALLIN"]

RUNS = [
    ("19_base",  r"results/19_mc_prop_softmax_prev_2000k/eval_results.pkl"),
    ("26e_tag",  r"results/26e_persona_tag_2000k/eval_results.pkl"),
    ("26a_lag",  r"results/26a_persona_lag_2000k/eval_results.pkl"),
    ("26b_man",  r"results/26b_persona_man_2000k/eval_results.pkl"),
    ("26c_sta",  r"results/26c_persona_sta_2000k/eval_results.pkl"),
    ("26d_nit",  r"results/26d_persona_nit_2000k/eval_results.pkl"),
]


def analyze(q):
    total_cells = zero_cells = 0
    contexts = ctx_all_zero = ctx_greedy_tie0 = 0
    greedy = Counter()
    # 라운드별 미학습 컨텍스트(깊은 라운드 도달 진단용)
    ctx_all_zero_by_round = [0, 0, 0, 0]
    for r in range(NR):
        for p in range(NP):
            for s in range(NS):
                for pa in range(NPA):
                    contexts += 1
                    row = q[r][p][s][pa]
                    if all(abs(v) < EPS for v in row):
                        ctx_all_zero += 1
                        ctx_all_zero_by_round[r] += 1
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
                ctx_all_zero_by_round=ctx_all_zero_by_round, greedy=greedy)


rows = []
for name, path in RUNS:
    try:
        d = pickle.load(open(path, "rb"))
    except FileNotFoundError:
        print(f"[skip] {name}: {path} 없음")
        continue
    rows.append((name, analyze(d["q"])))

print("=" * 96)
hdr = f"{'run':<10} {'q==0셀':>10} {'미학습ctx':>10} {'FOLD동률ctx':>12} {'greedy_FOLD':>12} {'greedy_CALL':>12}"
print(hdr)
print("-" * 96)
for name, m in rows:
    g = m["greedy"]
    print(f"{name:<10} "
          f"{m['zero_cells']:>5d}/{m['total_cells']:<4d} "
          f"{m['ctx_all_zero']:>4d}/{m['contexts']:<4d} "
          f"{m['ctx_greedy_tie0']:>5d}/{m['contexts']:<4d}   "
          f"{g['FOLD']:>11d} {g['CALL']:>12d}")
print("=" * 96)

print("\n라운드별 미학습 컨텍스트 (PRE/FLOP/TURN/RIVER, 각 64 ctx):")
print(f"{'run':<10}{'PRE':>8}{'FLOP':>8}{'TURN':>8}{'RIVER':>8}")
print("-" * 42)
for name, m in rows:
    z = m["ctx_all_zero_by_round"]
    print(f"{name:<10}{z[0]:>8d}{z[1]:>8d}{z[2]:>8d}{z[3]:>8d}")
print("=" * 96)

print("\nraw greedy argmax 액션 분포 (256 컨텍스트):")
hdr2 = f"{'run':<10}" + "".join(f"{a:>7}" for a in AN)
print(hdr2)
print("-" * len(hdr2))
for name, m in rows:
    g = m["greedy"]
    print(f"{name:<10}" + "".join(f"{g[a]:>7d}" for a in AN))
print("=" * 96)
