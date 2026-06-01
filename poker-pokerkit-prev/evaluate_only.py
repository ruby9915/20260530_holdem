"""
evaluate_only.py
─────────────────────────────────────────────────────────────────────
저장된 Q-table pickle을 로드해 평가만 수행한다.
용도: SE 분리 — 정책 분산 vs sampling noise 진단.

CLI:
    python evaluate_only.py <pkl_path> [n_games]
"""
import math
import statistics
import sys
import random
from pathlib import Path

# 같은 폴더의 학습 모듈에서 평가 로직과 상수 가져오기
sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_eval_mc_prop_eps_prev as t
from qlearning import QLearning


def evaluate(ql: QLearning, n_games: int):
    payoffs_r:  list[float] = []
    payoffs_rb: list[float] = []
    for i in range(n_games):
        payoffs_r.append(t._play_eval_episode(ql, 'random', learner_id=i % 2))
    for i in range(n_games):
        payoffs_rb.append(t._play_eval_episode(ql, 'rulebased', learner_id=i % 2))

    def _stats(payoffs: list[float]):
        n    = len(payoffs)
        mean = sum(payoffs) / n
        std  = statistics.stdev(payoffs) if n > 1 else 0.0
        scale = 1000.0 / t.BIG_BLIND
        win  = sum(1 for p in payoffs if p > 0) / n
        return win, mean * scale, (std / math.sqrt(n)) * scale

    return _stats(payoffs_r), _stats(payoffs_rb)


def main():
    if len(sys.argv) < 2:
        print("사용: python evaluate_only.py <pkl_path> [n_games]")
        sys.exit(1)
    pkl_path = sys.argv[1]
    n_games  = int(sys.argv[2]) if len(sys.argv) >= 3 else 5_000

    random.seed(123)  # 학습 시드(42)와 분리

    ql = QLearning.load(pkl_path)
    print(f"로드 완료: {pkl_path}")
    print(f"평가 게임 수: {n_games:,} (vs random / vs rulebased 각각)\n")

    (wr, mr, sr), (wrb, mrb, srb) = evaluate(ql, n_games)

    print(f"{'opponent':>10} │ {'win%':>7} │ {'mbb/g':>10} │ {'SE':>8} │ {'95% CI':>22}")
    print("─" * 70)
    for name, w, m, s in [('random', wr, mr, sr), ('rulebased', wrb, mrb, srb)]:
        lo, hi = m - 1.96 * s, m + 1.96 * s
        print(f"{name:>10} │ {w*100:>6.2f}% │ {m:>+10.1f} │ {s:>8.1f} │ [{lo:>+8.0f}, {hi:>+8.0f}]")


if __name__ == '__main__':
    main()
