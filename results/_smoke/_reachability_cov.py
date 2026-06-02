"""
reachability 보정 커버리지 분석.

세 가지 셀 분류:
  1) 구조적 불가능(STRUCT): 비교 대상 4개 모델(19, 21a/b/c) 모두에서 항상 q==0
     → 게임 규칙상 도달 불가 후보. 분모에서 제외해야 공정.
  2) 상대 편향(BIAS): 일부 모델은 채움, 일부 모델은 0
     → 그 상대 분포에서만 미도달. (reachable 이지만 특정 상대서 안 밟힘)
  3) 표본/탐색 부족: reachable 인데 해당 모델에서 0

여기서는 '컨텍스트' 단위가 아니라 '셀(컨텍스트×액션)' 단위로 본다.
단, FOLD/CHECK 등 합법성에 따라 항상 0일 수 있는 액션도 STRUCT 로 흡수된다.

깊은 셀 정의: round in {TURN, RIVER} AND prevaction in {SMALL_RAISE, BIG_RAISE}
"""
import pickle
import os

NR, NP, NS, NPA, NA = 4, 2, 8, 4, 8
EPS = 1e-12

RUNS = [
    ("random",    r"results/21a_softmax_random_2000k"),
    ("rulebased", r"results/21b_softmax_rulebased_2000k"),
    ("selfplay",  r"results/21c_softmax_selfplay_2000k"),
    ("19orig",    r"results/19_mc_prop_softmax_prev_2000k"),
]

qs = {}
for name, path in RUNS:
    pkl = os.path.join(path, "eval_results.pkl")
    if os.path.exists(pkl):
        qs[name] = pickle.load(open(pkl, "rb"))["q"]

names = list(qs.keys())


def nonzero(q, r, p, s, pa, a):
    return abs(q[r][p][s][pa][a]) > EPS


def is_deep(r, pa):
    return r in (2, 3) and pa in (2, 3)


# 셀 단위 분류
struct = bias = sample = filled = 0
deep_struct = deep_bias = deep_sample = deep_filled = 0
# 컨텍스트 단위 구조적 불가능 (8액션 전부 모든모델 0)
ctx_struct = 0
ctx_total = 0
ctx_deep_struct = 0
ctx_deep_total = 0

for r in range(NR):
    for p in range(NP):
        for s in range(NS):
            for pa in range(NPA):
                ctx_total += 1
                deepc = is_deep(r, pa)
                if deepc:
                    ctx_deep_total += 1
                ctx_any = False
                for a in range(NA):
                    flags = [nonzero(qs[n], r, p, s, pa, a) for n in names]
                    any_nz = any(flags)
                    all_nz = all(flags)
                    if any_nz:
                        ctx_any = True
                    # 분류 (셀 단위, 기준 모델 관점은 '아무 모델이나 채웠나')
                    if not any_nz:
                        struct += 1
                        if deepc:
                            deep_struct += 1
                    elif not all_nz:
                        bias += 1
                        if deepc:
                            deep_bias += 1
                    else:
                        filled += 1
                        if deepc:
                            deep_filled += 1
                if not ctx_any:
                    ctx_struct += 1
                    if deepc:
                        ctx_deep_struct += 1

total_cells = NR * NP * NS * NPA * NA
n_deep_rpa = sum(1 for r in range(NR) for pa in range(NPA) if is_deep(r, pa))  # =4
deep_cells = n_deep_rpa * NP * NS * NA  # 4 * 2 * 8 * 8 = 512

reachable = total_cells - struct
deep_reachable = deep_cells - deep_struct


def pct(a, b):
    return f"{100*a/b:.1f}%" if b else "n/a"


print("=" * 78)
print(f"[셀 단위] 전체 {total_cells} 셀")
print(f"  구조적 불가능(모든모델 0)     : {struct:5d} ({pct(struct,total_cells)})")
print(f"  상대편향(일부만 채움)         : {bias:5d} ({pct(bias,total_cells)})")
print(f"  모든모델 채움                 : {filled:5d} ({pct(filled,total_cells)})")
print(f"  -> reachable 분모             : {reachable}")
print("-" * 78)
print(f"[깊은 셀] 턴/리버 × 레이즈직면 {deep_cells} 셀")
print(f"  구조적 불가능                 : {deep_struct:5d} ({pct(deep_struct,deep_cells)})")
print(f"  상대편향                      : {deep_bias:5d} ({pct(deep_bias,deep_cells)})")
print(f"  모든모델 채움                 : {deep_filled:5d} ({pct(deep_filled,deep_cells)})")
print(f"  -> deep reachable 분모        : {deep_reachable}")
print("=" * 78)

# 각 모델별: reachable 분모 기준 진짜 커버리지
print("\n[모델별 reachable 기준 커버리지]")
print(f"{'model':<11} | {'전체cov(raw)':>11} | {'전체cov(reach)':>13} | "
      f"{'깊은cov(raw)':>11} | {'깊은cov(reach)':>13}")
print("-" * 78)
for n in names:
    q = qs[n]
    nz = dnz = 0
    dtot = 0
    for r in range(NR):
        for p in range(NP):
            for s in range(NS):
                for pa in range(NPA):
                    for a in range(NA):
                        if nonzero(q, r, p, s, pa, a):
                            nz += 1
                            if is_deep(r, pa):
                                dnz += 1
                        if is_deep(r, pa):
                            dtot += 1
    raw_cov = nz / total_cells
    reach_cov = nz / reachable
    raw_dcov = dnz / deep_cells
    reach_dcov = dnz / deep_reachable
    print(f"{n:<11} | {pct(nz,total_cells):>11} | {pct(nz,reachable):>13} | "
          f"{pct(dnz,deep_cells):>11} | {pct(dnz,deep_reachable):>13}")
print("=" * 78)
print("\n해석:")
print(" - reachable cov = (채운 셀)/(어떤 모델이든 한번이라도 채운 셀)")
print(" - 깊은cov(reach)가 100%에 가까우면: 2M로도 reachable 깊은셀은 거의 다 도달")
print(" - 100%에서 멀면: reachable인데도 못 채움 = 진짜 표본/탐색 부족")
print("=" * 78)
