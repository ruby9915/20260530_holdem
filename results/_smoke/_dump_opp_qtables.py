"""
21a/b/c 각 모델의 eval_results.pkl 을 로드해
19번과 동일 포맷의 qtable.md 를 생성한다.
(원본 base 스크립트의 print_q_table 출력 형식을 그대로 사용)
"""
import sys
import os
import contextlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "poker-pokerkit-prev"))
from qlearning import QLearning  # noqa: E402

RUNS = [
    ("random",    r"results/21a_softmax_random_2000k"),
    ("rulebased", r"results/21b_softmax_rulebased_2000k"),
    ("selfplay",  r"results/21c_softmax_selfplay_2000k"),
]

HEADER = "=== Q-Table (Prop MC + Softmax + CHECK=1chip + PrevAction) ==="

for name, path in RUNS:
    pkl = os.path.join(path, "eval_results.pkl")
    if not os.path.exists(pkl):
        print(f"[skip] {pkl} 없음")
        continue
    ql = QLearning.load(pkl)
    out = os.path.join(path, "qtable.md")
    with open(out, "w", encoding="utf-8") as f:
        with contextlib.redirect_stdout(f):
            print(f"{HEADER}  [train_opp={name}]")
            ql.print_q_table()
    print(f"[ok] {out}")
