"""
19번(=20번에 쓰인) Softmax MC 모델 분석.
주의: 이 실험은 Softmax 탐색이라 n(방문) 테이블은 increment_n이 호출되지 않아 전부 0.
따라서 커버리지는 q != 0 (한 번이라도 업데이트되어 0에서 벗어난 셀)로 추정한다.

테이블: q[round=4][pos=2][state=8][prevaction=4][action=8]
Round:  0=PREFLOP 1=FLOP 2=TURN 3=RIVER
PrevA:  0=NONE 1=CHECK_CALL 2=SMALL_RAISE 3=BIG_RAISE
Action: 0=FOLD 1=CHECK 2=CALL 3=R25 4=R50 5=R75 6=R100 7=ALLIN
"""
import pickle

d = pickle.load(open(r"results/19_mc_prop_softmax_prev_2000k/eval_results.pkl", "rb"))
q = d["q"]
NR, NP, NS, NPA, NA = 4, 2, 8, 4, 8
EPS = 1e-12
RN = ["PRE", "FLOP", "TURN", "RIV"]
PAN = ["NONE", "CH/CL", "SMALL_R", "BIG_R"]
AN = ["FOLD", "CHECK", "CALL", "R25", "R50", "R75", "R100", "ALLIN"]

total_cells = 0
zero_cells = 0
contexts = 0
ctx_all_zero = 0           # 컨텍스트의 8개 액션 q가 전부 0 → 완전 미학습
ctx_greedy_tie0 = 0        # greedy max==0 이고 동률 → tie-break(FOLD회피)에 결정 위임
deep_total = deep_zero = 0 # 턴/리버 × 레이즈직면 셀

def pct(a, b): return f"{100*a/b:.1f}%" if b else "n/a"

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
                for a in range(NA):
                    total_cells += 1
                    if abs(row[a]) < EPS:
                        zero_cells += 1
                    if r in (2, 3) and pa in (2, 3):
                        deep_total += 1
                        if abs(row[a]) < EPS:
                            deep_zero += 1

print("=" * 64)
print(f"테이블 {total_cells} 셀 / 결정 컨텍스트 {contexts} 개")
print(f"[학습 커버리지]  q==0(미학습) 셀: {zero_cells}/{total_cells} ({pct(zero_cells,total_cells)})")
print(f"[결정 컨텍스트]  8액션 전부 q==0(완전 미학습): {ctx_all_zero}/{contexts} ({pct(ctx_all_zero,contexts)})")
print(f"                greedy 0.000 동률→tie-break 위임: {ctx_greedy_tie0}/{contexts} ({pct(ctx_greedy_tie0,contexts)})")
print(f"[깊은 공격 셀]   턴/리버×레이즈직면 q==0: {deep_zero}/{deep_total} ({pct(deep_zero,deep_total)})")
print("=" * 64)

# greedy 정책이 실제 무슨 액션을 고르는지 분포 (동률이면 FOLD가 argmax로 잡힘 = raw 정책)
from collections import Counter
greedy = Counter()
for r in range(NR):
    for p in range(NP):
        for s in range(NS):
            for pa in range(NPA):
                row = q[r][p][s][pa]
                greedy[AN[row.index(max(row))]] += 1
print("raw greedy(어댑터 없음) argmax 액션 분포 (256 컨텍스트):")
for a in AN:
    if greedy[a]:
        print(f"  {a:<6}: {greedy[a]:3d} ({pct(greedy[a],contexts)})")
print("=" * 64)
