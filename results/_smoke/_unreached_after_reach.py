"""
reachability 보정 후에도 남는 미도달 셀 나열 (셀프플레이 제외).

reachable 정의(셀프플레이 빼고): random OR rulebased OR 19orig 중 하나라도 q!=0인 셀.
각 모델(random, rulebased)에 대해, reachable인데 그 모델이 q==0인 셀을 전부 출력.
이런 셀 = "상대를 바꾸면 채워지지만 이 상대로는 못 밟은 셀"(상대 편향).
"""
import pickle, os

NR, NP, NS, NPA, NA = 4, 2, 8, 4, 8
EPS = 1e-12

ROUND = ["PREFLOP", "FLOP", "TURN", "RIVER"]
POS   = ["BB", "SB"]
STATE = ["PREMIUM", "STRONG", "GOOD", "DECENT", "MEDIOCRE", "WEAK", "POOR", "TRASH"]
PREV  = ["NONE", "CHK/CALL", "S_RAISE", "B_RAISE"]
ACT   = ["FOLD", "CHECK", "CALL", "R25", "R50", "R75", "R100", "ALLIN"]

# 셀프플레이 제외
RUNS = [
    ("random",    r"results/21a_softmax_random_2000k"),
    ("rulebased", r"results/21b_softmax_rulebased_2000k"),
    ("19orig",    r"results/19_mc_prop_softmax_prev_2000k"),
]
qs = {}
for name, path in RUNS:
    pkl = os.path.join(path, "eval_results.pkl")
    if os.path.exists(pkl):
        qs[name] = pickle.load(open(pkl, "rb"))["q"]
names = list(qs.keys())


def nz(q, r, p, s, pa, a):
    return abs(q[r][p][s][pa][a]) > EPS


def is_deep(r, pa):
    return r in (2, 3) and pa in (2, 3)


def reachable(r, p, s, pa, a):
    return any(nz(qs[n], r, p, s, pa, a) for n in names)


def label(r, p, s, pa, a):
    tag = "  [깊은]" if is_deep(r, pa) else ""
    return f"{ROUND[r]:<7} {POS[p]:<2} {STATE[s]:<8} prev={PREV[pa]:<8} -> {ACT[a]:<5}{tag}"


# qtable.md 데이터 행은 4번째 줄부터 시작, 순서 = ((r*NP+p)*NS+s)*NPA+pa
def line_no(r, p, s, pa):
    row = ((r * NP + p) * NS + s) * NPA + pa
    return row + 4


QPATH = {
    "random":    "results/21a_softmax_random_2000k/qtable.md",
    "rulebased": "results/21b_softmax_rulebased_2000k/qtable.md",
}

for model in ("random", "rulebased"):
    q = qs[model]
    # 행 단위로 미도달 액션 모으기
    rows = {}
    for r in range(NR):
        for p in range(NP):
            for s in range(NS):
                for pa in range(NPA):
                    miss_acts = [a for a in range(NA)
                                 if reachable(r, p, s, pa, a) and not nz(q, r, p, s, pa, a)]
                    if miss_acts:
                        rows[(r, p, s, pa)] = miss_acts
    total = sum(len(v) for v in rows.values())
    deep = sum(len(v) for k, v in rows.items() if is_deep(k[0], k[3]))
    print("=" * 78)
    print(f"[{model}] reachable 미도달: {total}셀(깊은 {deep}) / {len(rows)}개 행  ({QPATH[model]})")
    print("=" * 78)
    for (r, p, s, pa), acts in rows.items():
        ln = line_no(r, p, s, pa)
        tag = " [깊은]" if is_deep(r, pa) else ""
        actstr = "/".join(ACT[a] for a in acts)
        print(f"   L{ln:<4} {ROUND[r]:<7} {POS[p]:<2} {STATE[s]:<8} prev={PREV[pa]:<8}{tag}  빠짐: {actstr}")
    print()

