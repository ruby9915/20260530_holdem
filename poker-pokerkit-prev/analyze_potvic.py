# -*- coding: utf-8 -*-
"""pot-VIC 메커니즘 진단 (E4a·E4c) — 세션 일회성 계산의 정식화(재현 가능).

(a) argmax-flip 분류: off pkl vs pot-VIC pkl(같은 seed)에서 greedy 선택이 바뀐 active 셀을
    유형별로 분류 — ZCA 서사(음수 흡수 해소)인가, 거울상(+EV 체크 복원)인가, 기타인가.
(b) 흡수·희석 집계: mean|Q(CHECK)|, CHECK-공격 흡수율, 공격|Q| (라운드 조건부 포함 —
    팟 크기는 라운드와 상관하므로 희석의 라운드 프로파일이 채널 증거가 됨).

usage: python analyze_potvic.py OFF_PKL VIC_PKL
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from abstraction import Round, Position, State, PrevAction, Action
from qlearning import QLearning

TOL = 1.0
AGG = [Action.RAISE_25, Action.RAISE_50, Action.RAISE_75,
       Action.RAISE_100, Action.RAISE_ALLIN]


def cells(ql):
    out = {}
    for r in Round:
        for p in Position:
            for s in State:
                for pa in PrevAction:
                    q = [ql.get_q(r, p, s, pa, a) for a in Action]
                    if max(abs(x) for x in q) > TOL:
                        out[(r, p, s, pa)] = q
    return out


def summarize(label, cs):
    ac = len(cs)
    mqc = sum(abs(q[Action.CHECK.value]) for q in cs.values()) / ac
    absorb = sum(1 for q in cs.values()
                 if abs(q[Action.CHECK.value]) < TOL
                 and q[Action.CHECK.value] > max(q[a.value] for a in AGG)
                 and min(q[a.value] for a in AGG) < -TOL)
    agg_abs = sum(max(abs(q[a.value]) for a in AGG) for q in cs.values()) / ac
    print(f"{label:12} active={ac:4d} mean|Qc|={mqc:6.3f} "
          f"CHECK흡수공격={absorb/ac*100:5.1f}% 공격|Q|={agg_abs:6.2f}")
    # 라운드 조건부 공격|Q| (희석의 라운드 프로파일)
    for rd in Round:
        sub = {k: q for k, q in cs.items() if k[0] == rd}
        if sub:
            v = sum(max(abs(q[a.value]) for a in AGG) for q in sub.values()) / len(sub)
            print(f"    {rd.name:8} n={len(sub):3d} 공격|Q|={v:6.2f}")


def main():
    off = QLearning.load(sys.argv[1])
    vic = QLearning.load(sys.argv[2])
    co, cv = cells(off), cells(vic)
    print("=== (b) 집계 진단 ===")
    summarize("off", co)
    summarize("pot-VIC", cv)

    print("\n=== (a) argmax-flip 분류 (양쪽 active 교집합) ===")
    both = set(co) & set(cv)
    kinds = {"neg_absorb_fix": 0, "posEV_check_restore": 0,
             "check_to_other": 0, "other_flip": 0, "no_flip": 0}
    examples = {"neg_absorb_fix": [], "posEV_check_restore": []}
    for key in both:
        qo, qv = co[key], cv[key]
        ao = max(Action, key=lambda a: qo[a.value])
        av = max(Action, key=lambda a: qv[a.value])
        if ao == av:
            kinds["no_flip"] += 1
            continue
        # off에서 CHECK(핀 0)가 음수 행동들을 눌렀는데 VIC 후 다른 행동으로 → ZCA 서사
        if (ao == Action.CHECK and abs(qo[Action.CHECK.value]) < TOL
                and av != Action.CHECK
                and any(qo[a.value] < -TOL for a in Action if a != Action.CHECK)):
            kinds["neg_absorb_fix"] += 1
            if len(examples["neg_absorb_fix"]) < 5:
                examples["neg_absorb_fix"].append((key, ao.name, av.name))
        # off에서 +EV 행동이 이겼는데 VIC 후 CHECK(+값)로 → 거울상(+EV 체크 복원)
        elif (ao != Action.CHECK and av == Action.CHECK
                and qv[Action.CHECK.value] > TOL):
            kinds["posEV_check_restore"] += 1
            if len(examples["posEV_check_restore"]) < 5:
                examples["posEV_check_restore"].append((key, ao.name, av.name))
        elif ao == Action.CHECK:
            kinds["check_to_other"] += 1
        else:
            kinds["other_flip"] += 1
    for k, v in kinds.items():
        print(f"  {k:22} {v:4d}")
    for k, exs in examples.items():
        for (key, a, b) in exs:
            r, p, s, pa = key
            print(f"    [{k}] {r.name} {p.name} {s.name} {pa.name}: {a} -> {b}")


if __name__ == '__main__':
    main()
