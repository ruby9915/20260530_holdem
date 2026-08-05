# -*- coding: utf-8 -*-
"""부호 보존·증폭 지문 재현 스크립트 (임계조건_정리.md §4 기전 수치의 산정 기준 고정).

감사 P1-9② 대응: 세션 내 임시 코드로 산출됐던 수치를 저장소 고정 기준으로 재현 가능하게 한다.

산정 기준 (고정):
  기준 런 = legacy8 chec_a50_s1(33번), 대조 런 = gateC chec_a{100,400,800}_s1
  셀 포함 조건: 두 런 모두 n(CHECK) ≥ 30 이고 |Q(CHECK)| > 0.5
  부호 보존 = sign(Q_기준(CHECK)) == sign(Q_대조(CHECK)) 인 셀 수 / 포함 셀 수
  크기 배율 = 부호 보존 셀의 |Q_대조|/|Q_기준| 중앙값
  greedy 일치: 두 런 모두 max|row|>1 ∧ 방문 합 ≥100 인 셀에서 argmax 동일 비율

usage: python fingerprint_qsign.py
"""
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from actions import Action
from qtable import QTable

RES = Path(__file__).resolve().parent.parent / 'results'
C = Action.CHECK.value


def load(cond, s=1):
    root = (RES / '33_ladder_replicate_k8' if cond in ('chec_a20', 'chec_a50')
            else RES / '34_threshold_stage0' / 'gateC_legacy8')
    return QTable.load(root / f'{cond}_s{s}' / 'qtable.pkl')


def compare(ref, qt):
    same = flip = 0
    ratios = []
    agree = cells = 0
    for r in range(4):
        for p in range(2):
            for s_ in range(len(ref.q[r][p])):
                for pa in range(4):
                    q1 = ref.q[r][p][s_][pa]
                    q2 = qt.q[r][p][s_][pa]
                    n1 = ref.n[r][p][s_][pa]
                    n2 = qt.n[r][p][s_][pa]
                    if (n1[C] >= 30 and n2[C] >= 30
                            and abs(q1[C]) > 0.5 and abs(q2[C]) > 0.5):
                        if (q1[C] > 0) == (q2[C] > 0):
                            same += 1
                            ratios.append(abs(q2[C]) / abs(q1[C]))
                        else:
                            flip += 1
                    if (max(abs(x) for x in q1) > 1 and max(abs(x) for x in q2) > 1
                            and sum(n1) >= 100 and sum(n2) >= 100):
                        cells += 1
                        agree += (max(range(8), key=lambda a: q1[a]) ==
                                  max(range(8), key=lambda a: q2[a]))
    return same, flip, (st.median(ratios) if ratios else float('nan')), agree, cells


def main():
    ref = load('chec_a50')
    for cond in ('chec_a100', 'chec_a400', 'chec_a800'):
        s, f, m, a, c = compare(ref, load(cond))
        print(f"a50 대비 {cond}: 부호 유지 {s}/{s+f} (뒤집힘 {f}) | "
              f"크기 배율 중앙값 {m:.2f} | greedy 일치 {a}/{c} ({a/c*100:.0f}%)")


if __name__ == '__main__':
    main()
