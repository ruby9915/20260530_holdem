# -*- coding: utf-8 -*-
"""정밀 평가 — 100k 게임 × N회 (레거시 eval_persona_100k 프로토콜 동일).

usage: python evaluate.py RUN_DIR [RUN_DIR ...]
env  : N_GAMES=100000  N_REPEAT=5  BASE_SEED=1000
       OPPONENTS=random,eval_tag  (E2 홀드아웃: lag,man,sta,nit 추가 가능)

회차마다 random.seed(BASE_SEED+k) 후 상대별 N_GAMES 순차 평가.
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
from personas import PERSONA_POLICIES
from qtable import QTable
from train import mbb_se

N_GAMES = int(os.environ.get('N_GAMES', '100000'))
N_REPEAT = int(os.environ.get('N_REPEAT', '5'))
BASE_SEED = int(os.environ.get('BASE_SEED', '1000'))
OPPONENTS = os.environ.get('OPPONENTS', 'random,eval_tag').split(',')

_COL = {'random': 'vsRand', 'eval_tag': 'vsTAG',
        'lag': 'vsLAG', 'man': 'vsMAN', 'sta': 'vsSTA',
        'nit': 'vsNIT', 'tag': 'vsTAGp'}


def _kind(name: str):
    if name in ('random', 'eval_tag'):
        return name
    return PERSONA_POLICIES[name]


def eval_run(run_dir: str):
    run = Path(run_dir)
    qt = QTable.load(run / 'qtable.pkl')
    cards = make_cards(qt.meta['card'])
    rows = []
    for k in range(N_REPEAT):
        random.seed(BASE_SEED + k)
        t0 = time.perf_counter()
        rec = {'rep': k}
        for name in OPPONENTS:
            col = _COL[name]
            pays = [play_eval_episode(qt, cards, _kind(name), learner_id=i % 2)
                    for i in range(N_GAMES)]
            mbb, se = mbb_se(pays)
            rec[col], rec[col + '_se'] = mbb, se
            rec[col + '_win'] = sum(1 for p in pays if p > 0) / N_GAMES
        rows.append(rec)
        head = ' | '.join(f"{_COL[n]} {rec[_COL[n]]:+9.1f}±{rec[_COL[n]+'_se']:5.1f}"
                          for n in OPPONENTS)
        print(f"  [{run.name}] rep{k+1}/{N_REPEAT} {head} | "
              f"{time.perf_counter()-t0:.0f}s", flush=True)

    sd = statistics.stdev if N_REPEAT > 1 else (lambda _: 0.0)
    stats = {}
    for n in OPPONENTS:
        col = _COL[n]
        vals = [r[col] for r in rows]
        stats[col] = (statistics.mean(vals), sd(vals))
    line = ' | '.join(f"{c} {m:+9.1f} (SD {s:6.1f})" for c, (m, s) in stats.items())
    print(f"  ==> {run.name:<28} {line}", flush=True)

    with open(run / 'precision_eval.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return run.name, stats


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: python evaluate.py RUN_DIR [RUN_DIR ...]')
    summary = [eval_run(d) for d in sys.argv[1:]]
    print('=' * 100, flush=True)
    cols = [_COL[n] for n in OPPONENTS]
    print(f"{'run':<30}" + ''.join(f"{c:>12}{'SD':>8}" for c in cols), flush=True)
    for name, stats in summary:
        print(f"{name:<30}" + ''.join(f"{stats[c][0]:>+12.1f}{stats[c][1]:>8.1f}"
                                      for c in cols), flush=True)
