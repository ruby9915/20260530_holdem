"""
eval_persona_100k.py  (25/26번 완료 학습 정밀 평가)
─────────────────────────────────────────────────────────────────────
학습이 끝난 pkl(Q테이블)을 로드해 base.evaluate 로 100,000 게임씩 3회
독립 평가한다. 각 회차는 서로 다른 시드를 써 독립 표본을 만든다.

평가 상대(고정): vs random / vs (고정 TAG)rulebased  ← base._play_eval_episode 그대로.
보고: 각 회차 mbb/g ± SE(×500), 3회 평균과 회차간 표준편차.
  base.evaluate 는 어댑터 없는 raw greedy 지표(17.7 게이트와 동일).

CLI:
  argv[1..] = 평가할 run 디렉토리(상대경로, results/ 기준) 여러 개
              미지정 시 기본 목록(25a~d, 26a~e) 사용.
옵션 환경:
  N_GAMES (default 100000), N_REPEAT (default 3), BASE_SEED (default 1000)
"""
import os
import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import random

import train_eval_mc_prop_softmax_2000k as base
from qlearning import QLearning

N_GAMES   = int(os.environ.get("N_GAMES", "100000"))
N_REPEAT  = int(os.environ.get("N_REPEAT", "3"))
BASE_SEED = int(os.environ.get("BASE_SEED", "1000"))

RESULTS = Path(__file__).resolve().parent.parent / "results"

DEFAULT_RUNS = [
    "25a_temp_baseline_2000k",
    "25b_temp_hi_2000k",
    "25c_temp_slow_2000k",
    "25d_temp_floor_2000k",
    "26e_persona_tag_2000k",
    "26a_persona_lag_2000k",
    "26b_persona_man_2000k",
    "26c_persona_sta_2000k",
    "26d_persona_nit_2000k",
]


def _fmt(seconds: float) -> str:
    return base._fmt_time(seconds)


def eval_run(run: str):
    pkl = RESULTS / run / "eval_results.pkl"
    if not pkl.exists():
        print(f"[skip] {run}: {pkl} 없음", flush=True)
        return None
    ql = QLearning.load(str(pkl))

    rows = []  # (mbb_r, se_r, mbb_rb, se_rb)
    for k in range(N_REPEAT):
        random.seed(BASE_SEED + k)
        t0 = time.perf_counter()
        wr, mr, sr, wrb, mrb, srb = base.evaluate(ql, N_GAMES)
        dt = time.perf_counter() - t0
        rows.append((wr, mr, sr, wrb, mrb, srb))
        print(f"  [{run}] rep{k+1}/{N_REPEAT} "
              f"| vsRand {wr*100:5.1f}% {mr:>+8.1f}±{sr:>6.1f} "
              f"| vsTAG {wrb*100:5.1f}% {mrb:>+8.1f}±{srb:>6.1f} "
              f"| {_fmt(dt)}", flush=True)

    mr_list  = [r[1] for r in rows]
    mrb_list = [r[4] for r in rows]
    mean_r,  sd_r  = statistics.mean(mr_list),  (statistics.stdev(mr_list)  if N_REPEAT > 1 else 0.0)
    mean_rb, sd_rb = statistics.mean(mrb_list), (statistics.stdev(mrb_list) if N_REPEAT > 1 else 0.0)
    print(f"  ==> {run:<26} "
          f"vsRand mean {mean_r:>+9.1f} (회차SD {sd_r:6.1f}) | "
          f"vsTAG mean {mean_rb:>+9.1f} (회차SD {sd_rb:6.1f})", flush=True)
    return run, mean_r, sd_r, mean_rb, sd_rb


def main(runs):
    print("=" * 100, flush=True)
    print(f"  정밀 평가: {N_GAMES:,} games × {N_REPEAT}회  |  seed={BASE_SEED}..{BASE_SEED+N_REPEAT-1}", flush=True)
    print("=" * 100, flush=True)
    summary = []
    for run in runs:
        r = eval_run(run)
        if r:
            summary.append(r)
        print("-" * 100, flush=True)

    print("=" * 100, flush=True)
    print(f"{'run':<28}{'vsRand mean':>14}{'SD':>8}{'vsTAG mean':>14}{'SD':>8}", flush=True)
    print("-" * 100, flush=True)
    for run, mean_r, sd_r, mean_rb, sd_rb in summary:
        print(f"{run:<28}{mean_r:>+14.1f}{sd_r:>8.1f}{mean_rb:>+14.1f}{sd_rb:>8.1f}", flush=True)
    print("=" * 100, flush=True)


if __name__ == "__main__":
    runs = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_RUNS
    main(runs)
