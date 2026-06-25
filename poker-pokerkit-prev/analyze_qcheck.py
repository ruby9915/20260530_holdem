"""
analyze_qcheck.py  (ZCA 지문 진단 — Q(CHECK) 영-고정점 측정)
─────────────────────────────────────────────────────────────────────
저장된 Q-테이블 pkl을 로드해 CHECK 행동의 학습값 분포와 "영-비용 흡수(ZCA)"
지문을 정량화한다. 여러 pkl을 받아 나란히 비교 출력한다.

ZCA 가설:
  PROP+VIC-off 에서는 CHECK invest=0 → credit=0 → 방문해도 Q(CHECK)가 0으로
  고정되고, 음(-)의 Q를 가진 다른 행동들을 0이 greedy로 지배 → CHECK 흡수.
  PURE / PROP+VIC-on 에서는 CHECK도 보상을 받아 Q가 0에서 풀린다.

주의: softmax-MC 학습은 방문카운트 n 을 증가시키지 않는다(n은 UCB 전용).
      따라서 "학습된 셀"은 n 이 아니라 **Q값**으로 판정한다:
        active cell = 그 셀의 어떤 행동이든 |Q|>TOL → 컨텍스트가 도달·학습됨.
      ZCA의 본질도 여기에 있다: PROP+VIC-off 는 CHECK credit=0 이라 방문해도
      Q(CHECK)가 0에 머물러 n/q 어느 쪽으로도 "방문"이 안 보인다. 그래서
      다른 행동이 학습된(active) 셀에서 Q(CHECK)≈0 이 음수행동을 지배하는지를 본다.

측정 지표(active cell = max_a|Q|>TOL 에 한정):
  active_cells        : 어떤 행동이든 학습값이 잡힌 컨텍스트 수
  mean_abs_qcheck     : active 셀의 |Q(CHECK)| 평균 (ZCA면 ≈0, 정상이면 큼)
  qcheck_pinned_frac  : active 셀 중 |Q(CHECK)|<TOL 비율 (0 고정 비율)
  qcheck_learned_frac : active 셀 중 |Q(CHECK)|>TOL 비율 (CHECK이 값을 학습)
  check_argmax_frac   : active 셀 중 argmax_a Q == CHECK 비율
  zca_dominance_frac  : argmax==CHECK & |Q(CHECK)|<TOL & 다른 행동에 Q<-TOL 존재
                        → "0이 음수를 흡수"한 셀 비율 (ZCA 직접 지문)

CLI:
  python analyze_qcheck.py LABEL=경로.pkl [LABEL2=경로2.pkl ...]
  (LABEL= 생략 시 파일명 stem 을 라벨로 사용)
환경변수:
  QCHECK_TOL  (default 1.0; chip 스케일에서 0근처 판정 임계)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from abstraction import Round, Position, State, PrevAction, Action
from qlearning import QLearning

TOL = float(os.environ.get('QCHECK_TOL', 1.0))
CHECK = Action.CHECK


def analyze(pkl_path: str) -> dict:
    ql = QLearning.load(pkl_path)
    active_cells = 0
    pinned = 0
    learned = 0
    check_argmax = 0
    zca_dom = 0
    sum_abs_q = 0.0
    qcheck_min = float('inf')
    qcheck_max = float('-inf')

    for r in Round:
        for p in Position:
            for s in State:
                for pa in PrevAction:
                    qrow = [ql.get_q(r, p, s, pa, a) for a in Action]
                    # active = 셀의 어떤 행동이든 학습값이 잡혔는가
                    if max(abs(q) for q in qrow) <= TOL:
                        continue
                    active_cells += 1
                    qc = qrow[CHECK.value]
                    sum_abs_q += abs(qc)
                    qcheck_min = min(qcheck_min, qc)
                    qcheck_max = max(qcheck_max, qc)
                    if abs(qc) < TOL:
                        pinned += 1
                    else:
                        learned += 1
                    amax = max(Action, key=lambda a: qrow[a.value])
                    if amax == CHECK:
                        check_argmax += 1
                        neg_exists = any(qrow[a.value] < -TOL for a in Action
                                         if a != CHECK)
                        if abs(qc) < TOL and neg_exists:
                            zca_dom += 1

    ac = max(active_cells, 1)
    return {
        'active_cells':         active_cells,
        'mean_abs_qcheck':      sum_abs_q / ac,
        'qcheck_pinned_frac':   pinned / ac,
        'qcheck_learned_frac':  learned / ac,
        'check_argmax_frac':    check_argmax / ac,
        'zca_dominance_frac':   zca_dom / ac,
        'qcheck_min':           (qcheck_min if active_cells else 0.0),
        'qcheck_max':           (qcheck_max if active_cells else 0.0),
    }


def main(args: list[str]):
    if not args:
        raise SystemExit("usage: python analyze_qcheck.py LABEL=path.pkl [...]")
    items = []
    for arg in args:
        if '=' in arg:
            label, path = arg.split('=', 1)
        else:
            label, path = Path(arg).stem, arg
        if not Path(path).exists():
            raise SystemExit(f"not found: {path}")
        items.append((label, analyze(path)))

    print(f"\n=== Q(CHECK) ZCA 진단  (TOL={TOL}) ===")
    cols = ['active_cells', 'mean_abs_qcheck', 'qcheck_pinned_frac',
            'qcheck_learned_frac', 'check_argmax_frac', 'zca_dominance_frac',
            'qcheck_min', 'qcheck_max']
    namew = max(len(l) for l, _ in items)
    namew = max(namew, 8)
    print(f"{'label':<{namew}} | " + " | ".join(f"{c:>18}" for c in cols))
    print("-" * (namew + 3 + len(cols) * 21))
    for label, m in items:
        cells = []
        for c in cols:
            v = m[c]
            if c == 'active_cells':
                cells.append(f"{v:>18d}")
            elif c.endswith('_frac'):
                cells.append(f"{v*100:>17.1f}%")
            else:
                cells.append(f"{v:>18.3f}")
        print(f"{label:<{namew}} | " + " | ".join(cells))
    print()
    print("해석: ZCA(영-비용 흡수)가 강할수록 → mean_abs_qcheck↓(≈0),")
    print("      pinned_zero_frac↑, zca_dominance_frac↑ (0이 음수행동을 흡수).")
    print("      PURE / PROP+VIC-on 은 Q(CHECK)가 0에서 풀려 위 지표가 낮아야 함.\n")


if __name__ == '__main__':
    main(sys.argv[1:])
