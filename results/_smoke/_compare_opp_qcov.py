"""
21번 실험: 학습 상대(random/rulebased/selfplay)별 모델의
깊은 셀 커버리지 vs raw greedy mbb 전이 비교.

각 eval_results.pkl 에서:
  - q 테이블 커버리지(q!=0)
  - 깊은 공격 셀(턴/리버 × 레이즈직면) 커버리지
  - raw greedy argmax 액션 분포 (FOLD 동률 위임 비율 포함)
  - 최종 평가 행(vs random / vs rulebased 승률·mbb)
를 뽑아 한 표로 정리한다.
"""
import pickle
import csv
import os
from collections import Counter

RUNS = [
    ("random",    r"results/21a_softmax_random_2000k"),
    ("rulebased", r"results/21b_softmax_rulebased_2000k"),
    ("selfplay",  r"results/21c_softmax_selfplay_2000k"),
    ("19(orig)",  r"results/19_mc_prop_softmax_prev_2000k"),
]

NR, NP, NS, NPA, NA = 4, 2, 8, 4, 8
EPS = 1e-12
AN = ["FOLD", "CHECK", "CALL", "R25", "R50", "R75", "R100", "ALLIN"]


def pct(a, b):
    return f"{100*a/b:.1f}%" if b else "n/a"


def analyze_q(q):
    total = zero = 0
    ctx = ctx_all_zero = ctx_tie0 = 0
    deep_total = deep_zero = 0
    greedy = Counter()
    fold_tie = 0  # greedy max==0 동률인데 argmax가 FOLD로 잡힘
    for r in range(NR):
        for p in range(NP):
            for s in range(NS):
                for pa in range(NPA):
                    ctx += 1
                    row = q[r][p][s][pa]
                    if all(abs(v) < EPS for v in row):
                        ctx_all_zero += 1
                    mx = max(row)
                    if abs(mx) < EPS and sum(1 for v in row if abs(v - mx) < EPS) > 1:
                        ctx_tie0 += 1
                    am = row.index(mx)
                    greedy[AN[am]] += 1
                    if abs(mx) < EPS and am == 0:
                        fold_tie += 1
                    for a in range(NA):
                        total += 1
                        if abs(row[a]) < EPS:
                            zero += 1
                        if r in (2, 3) and pa in (2, 3):
                            deep_total += 1
                            if abs(row[a]) < EPS:
                                deep_zero += 1
    return {
        "cov": 1 - zero / total,
        "deep_cov": 1 - deep_zero / deep_total if deep_total else 0,
        "ctx_all_zero": ctx_all_zero,
        "ctx_tie0": ctx_tie0,
        "fold_tie": fold_tie,
        "ctx": ctx,
        "greedy": greedy,
    }


def last_eval_row(path):
    csvp = os.path.join(path, "eval_results.csv")
    if not os.path.exists(csvp):
        return None
    with open(csvp, newline="") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        return None
    header = rows[0]
    last = rows[-1]
    return dict(zip(header, last))


def tail_mean_mbb(path, tail=20):
    """마지막 tail개 평가행의 vs random / vs rulebased mbb 평균(노이즈 완화)."""
    csvp = os.path.join(path, "eval_results.csv")
    if not os.path.exists(csvp):
        return None, None
    with open(csvp, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None, None
    sel = rows[-tail:] if len(rows) >= tail else rows
    rr = [float(r["mbb/g_vs_random"]) for r in sel]
    ru = [float(r["mbb/g_vs_rulebased"]) for r in sel]
    return sum(rr) / len(rr), sum(ru) / len(ru)



print("=" * 92)
print(f"{'train_opp':<11} | {'cov':>6} | {'deep_cov':>8} | {'ctx_allzero':>11} | "
      f"{'FOLD동률위임':>11} | {'vsRand mbb':>10} | {'vsRule mbb':>10}")
print("-" * 92)

results = {}
for name, path in RUNS:
    pklp = os.path.join(path, "eval_results.pkl")
    if not os.path.exists(pklp):
        print(f"{name:<11} | (no pkl: {pklp})")
        continue
    d = pickle.load(open(pklp, "rb"))
    a = analyze_q(d["q"])
    ev = last_eval_row(path)
    results[name] = (a, ev, d["q"])

    def getmbb(ev, keys):
        if not ev:
            return "?"
        for k in keys:
            if k in ev:
                return ev[k]
        return "?"

    # CSV 컬럼명이 스크립트별로 다를 수 있어 후보키로 탐색
    rand_mbb = getmbb(ev, ["mbb/g_vs_random", "mbb_random", "mbb_r", "mbb/g_r"])
    rule_mbb = getmbb(ev, ["mbb/g_vs_rulebased", "mbb_rule", "mbb_rl", "mbb/g_rl"])

    print(f"{name:<11} | {pct(a['cov']*1, 1):>6} | {pct(a['deep_cov']*1,1):>8} | "
          f"{a['ctx_all_zero']:>3}/{a['ctx']:<3}{'':>3} | "
          f"{a['fold_tie']:>3}/{a['ctx']:<3}{'':>3} | {str(rand_mbb):>10} | {str(rule_mbb):>10}")

print("=" * 92)
print("[참고] 위 mbb는 마지막 1개 평가행(200게임, SE 수천)이라 노이즈가 큼.")
print(f"{'train_opp':<11} | {'vsRand mbb(tail20 평균)':>24} | {'vsRule mbb(tail20 평균)':>24}")
print("-" * 92)
for name, path in RUNS:
    if name not in results:
        continue
    tr, tu = tail_mean_mbb(path, tail=20)
    tr_s = f"{tr:+.1f}" if tr is not None else "?"
    tu_s = f"{tu:+.1f}" if tu is not None else "?"
    print(f"{name:<11} | {tr_s:>24} | {tu_s:>24}")

print("=" * 92)
print("\nraw greedy argmax 액션 분포 (256 컨텍스트):")
for name, _ in RUNS:
    if name not in results:
        continue
    a = results[name][0]
    g = a["greedy"]
    parts = [f"{k}={g[k]}" for k in AN if g[k]]
    print(f"  {name:<11}: " + "  ".join(parts))
print("=" * 92)

# ── 각 q테이블 greedy 정책 그리드 덤프 ─────────────────────────────
RN = ["PRE", "FLOP", "TURN", "RIV"]
PN = ["BTN", "BB"]
PAN = ["NONE", "CH/CL", "SMALL_R", "BIG_R"]
SHORT = {"FOLD": "FOLD", "CHECK": "CHCK", "CALL": "CALL", "R25": "R25",
         "R50": "R50", "R75": "R75", "R100": "R100", "ALLIN": "ALLI"}

for name, _ in RUNS:
    if name not in results:
        continue
    q = results[name][2]
    print(f"\n■ q테이블 greedy 정책 — train_opp={name}  (행:round/pos, 열:prevaction × state0-7)")
    print(f"  {'ctx':<12} | " + " | ".join(f"{pa:<7}" for pa in PAN))
    print("  " + "-" * 86)
    for r in range(NR):
        for p in range(NP):
            row_cells = []
            for pa in range(NPA):
                acts = []
                for s in range(NS):
                    cell = q[r][p][s][pa]
                    mx = max(cell)
                    am = cell.index(mx)
                    acts.append("." if abs(mx) < EPS else SHORT[AN[am]][0])
                row_cells.append("".join(acts))
            print(f"  {RN[r]+'/'+PN[p]:<12} | " + " | ".join(f"{c:<7}" for c in row_cells))
    print("  (열 8칸=state0..7;  '.'=미학습(q=0→FOLD동률);  F/C/A/R=FOLD/CHECK·CALL/ALLIN/Raise 첫글자)")
print("=" * 92)

