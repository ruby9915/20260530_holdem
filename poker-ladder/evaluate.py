# -*- coding: utf-8 -*-
"""정밀 평가 — 100k 게임 × N회 (레거시 eval_persona_100k 프로토콜 동일).

usage: python evaluate.py RUN_DIR [RUN_DIR ...]
env  : N_GAMES=100000  N_REPEAT=5  BASE_SEED=1000

회차마다 random.seed(BASE_SEED+k) 후 vs random 100k → vs eval_tag 100k.
결과는 RUN_DIR/precision_eval.csv 에 저장, 요약은 stdout.
"""
import csv
import os
import random
import statistics
import sys
import time
from pathlib import Path

from cards import make_cards
from game import play_eval_episode
from qtable import QTable
from train import mbb_se

N_GAMES = int(os.environ.get('N_GAMES', '100000'))
N_REPEAT = int(os.environ.get('N_REPEAT', '5'))
BASE_SEED = int(os.environ.get('BASE_SEED', '1000'))


def eval_run(run_dir: str):
    run = Path(run_dir)
    qt = QTable.load(run / 'qtable.pkl')
    cards = make_cards(qt.meta['card'])
    rows = []
    for k in range(N_REPEAT):
        random.seed(BASE_SEED + k)
        t0 = time.perf_counter()
        rec = {'rep': k}
        for kind, col in (('random', 'vsRand'), ('eval_tag', 'vsTAG')):
            pays = [play_eval_episode(qt, cards, kind, learner_id=i % 2)
                    for i in range(N_GAMES)]
            mbb, se = mbb_se(pays)
            rec[col], rec[col + '_se'] = mbb, se
            rec[col + '_win'] = sum(1 for p in pays if p > 0) / N_GAMES
        rows.append(rec)
        print(f"  [{run.name}] rep{k+1}/{N_REPEAT} "
              f"vsRand {rec['vsRand']:+9.1f}±{rec['vsRand_se']:5.1f} | "
              f"vsTAG {rec['vsTAG']:+9.1f}±{rec['vsTAG_se']:5.1f} | "
              f"{time.perf_counter()-t0:.0f}s", flush=True)

    mr = [r['vsRand'] for r in rows]
    mt = [r['vsTAG'] for r in rows]
    sd = statistics.stdev if N_REPEAT > 1 else (lambda _: 0.0)
    print(f"  ==> {run.name:<28} vsRand {statistics.mean(mr):+9.1f} "
          f"(SD {sd(mr):6.1f}) | vsTAG {statistics.mean(mt):+9.1f} "
          f"(SD {sd(mt):6.1f})", flush=True)

    with open(run / 'precision_eval.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return run.name, statistics.mean(mr), sd(mr), statistics.mean(mt), sd(mt)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: python evaluate.py RUN_DIR [RUN_DIR ...]')
    summary = [eval_run(d) for d in sys.argv[1:]]
    print('=' * 90, flush=True)
    print(f"{'run':<30}{'vsRand':>12}{'SD':>9}{'vsTAG':>12}{'SD':>9}", flush=True)
    for name, mr, sdr, mt, sdt in summary:
        print(f"{name:<30}{mr:>+12.1f}{sdr:>9.1f}{mt:>+12.1f}{sdt:>9.1f}", flush=True)
