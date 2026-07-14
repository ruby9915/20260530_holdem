# -*- coding: utf-8 -*-
"""단일 학습 러너 — 실험 = 설정 조합. 스크립트 사본 증식 금지.

usage:
  python train.py --out DIR --card legacy8 --credit prop --vic off --seed 1
  python train.py --out DIR --card ehs20 --credit prop --vic checktime --vic-amount 0.30 --seed 3

설정 전체가 out/config.json 에 기록된다 (재현성).
체크포인트 평가(200게임)는 학습곡선 참고용 — 결론은 evaluate.py(100k×5)에서만.
"""
import argparse
import csv
import json
import math
import random
import statistics
import time
from pathlib import Path

from actions import N_ACTIONS_OF
from cards import make_cards
from game import BIG_BLIND, play_eval_episode, play_train_episode
from personas import PERSONA_POLICIES
from qtable import QTable

TEMP_START, TEMP_END, TEMP_DECAY_END = 10.0, 0.5, 0.8   # 레거시 스케줄


def temperature_at(episode: int, total: int) -> float:
    progress = min(1.0, episode / (total * TEMP_DECAY_END))
    return TEMP_START + (TEMP_END - TEMP_START) * progress


def mbb_se(payoffs):
    n = len(payoffs)
    mean = sum(payoffs) / n
    std = statistics.stdev(payoffs) if n > 1 else 0.0
    scale = 1000.0 / BIG_BLIND
    return mean * scale, (std / math.sqrt(n)) * scale


def checkpoint_eval(qt, cards, n_games: int, actions_version: str = 'A8'):
    out = {}
    for kind in ('random', 'eval_tag'):
        pays = [play_eval_episode(qt, cards, kind, learner_id=i % 2,
                                  actions_version=actions_version)
                for i in range(n_games)]
        mbb, se = mbb_se(pays)
        out[kind] = (sum(1 for p in pays if p > 0) / n_games, mbb, se)
    return out


# 27/28번 재현용 혼합 학습상대 풀·가중치 (레거시 동일)
TRAIN_PERSONAS = ['tag', 'lag', 'man', 'sta', 'nit']
MIX_WEIGHTS    = [0.20, 0.25, 0.15, 0.25, 0.15]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--card', default='legacy8')          # legacy8 | ehs20 | ehs50
    ap.add_argument('--credit', default='prop', choices=['prop', 'pure'])
    ap.add_argument('--vic', default='off',
                    choices=['off', 'fixed', 'checktime', 'terminal'])
    ap.add_argument('--vic-amount', type=float, default=0.0)  # fixed=칩, checktime/terminal=α(비율)
    ap.add_argument('--actions', default='A8', choices=['A8', 'A12'])  # 2단 행동축
    ap.add_argument('--opponent', default='tag',
                    choices=list(PERSONA_POLICIES) + ['random', 'cfrplus'])
    ap.add_argument('--scheme', default='single',
                    choices=['single', 'cycle', 'mixed'])    # 27/28번 재현
    ap.add_argument('--pot-apply', default='all',
                    choices=['all', 'invested_only', 'allcheck_only'])  # E1 격리
    ap.add_argument('--q-init', type=float, default=0.0)      # E8-② 낙관적 초기화
    ap.add_argument('--temp-floor', type=float, default=0.0)  # E8-① 탐색 강화
    ap.add_argument('--uniform-penalty', type=float, default=0.0)  # E8-③ 일률 벌점
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--episodes', type=int, default=2_000_000)
    ap.add_argument('--eval-every', type=int, default=8_000)
    ap.add_argument('--eval-games', type=int, default=200)
    cfg = ap.parse_args()

    if cfg.vic != 'off' and cfg.vic_amount <= 0:
        raise SystemExit('--vic fixed/checktime/terminal 에는 --vic-amount > 0 필요')
    if cfg.scheme != 'single' and cfg.opponent != 'tag':
        raise SystemExit('--scheme cycle/mixed 는 --opponent 지정과 배타 (풀 고정)')

    out = Path(cfg.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'config.json').write_text(
        json.dumps(vars(cfg), indent=1, ensure_ascii=False), encoding='utf-8')

    random.seed(cfg.seed)
    persona_rng = random.Random(cfg.seed)          # 페르소나 선택 전용 (레거시 동일)
    cards = make_cards(cfg.card)
    qt = QTable(cards.n_states, init_q=cfg.q_init,
                n_actions=N_ACTIONS_OF[cfg.actions])
    rows = []

    cfr_opp = None
    if cfg.opponent == 'cfrplus':
        from cfr_opponent import CfrOpponent
        cfr_opp = CfrOpponent(rng_seed=cfg.seed)

    def opponent_for(i: int):
        if cfg.scheme == 'cycle':
            return PERSONA_POLICIES[TRAIN_PERSONAS[i % len(TRAIN_PERSONAS)]]
        if cfg.scheme == 'mixed':
            name = persona_rng.choices(TRAIN_PERSONAS, weights=MIX_WEIGHTS, k=1)[0]
            return PERSONA_POLICIES[name]
        if cfg.opponent == 'cfrplus':
            return cfr_opp
        return 'random' if cfg.opponent == 'random' else PERSONA_POLICIES[cfg.opponent]

    tag = (f"card={cfg.card} actions={cfg.actions} credit={cfg.credit} "
           f"vic={cfg.vic}({cfg.vic_amount}) opp={cfg.scheme}:{cfg.opponent} "
           f"seed={cfg.seed}")
    print(f"[ladder-train] {tag} ep={cfg.episodes:,} -> {out}", flush=True)

    t0 = time.perf_counter()
    ep = 0
    while ep < cfg.episodes:
        nxt = min(ep + cfg.eval_every, cfg.episodes)
        for i in range(ep + 1, nxt + 1):
            temp = max(cfg.temp_floor, temperature_at(i, cfg.episodes))
            play_train_episode(qt, cards, opponent_for(i), temp,
                               cfg.credit, cfg.vic, cfg.vic_amount,
                               learner_id=i % 2, pot_apply=cfg.pot_apply,
                               uniform_penalty=cfg.uniform_penalty,
                               actions_version=cfg.actions)
        ep = nxt
        ck = checkpoint_eval(qt, cards, cfg.eval_games, cfg.actions)
        (wr, mr, _), (wt, mt, _) = ck['random'], ck['eval_tag']
        rows.append((ep, wr, mr, wt, mt))
        el = time.perf_counter() - t0
        eta = el / ep * (cfg.episodes - ep)
        print(f"  ep={ep:>9,} ({ep/cfg.episodes*100:4.1f}%) "
              f"T={temperature_at(ep, cfg.episodes):5.2f} | "
              f"vsRand {mr:>+8.0f} | vsTAG {mt:>+8.0f} | "
              f"{el:6.0f}s eta {eta:6.0f}s", flush=True)

    with open(out / 'train_curve.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['episode', 'win_vs_random', 'mbb_vs_random',
                    'win_vs_evaltag', 'mbb_vs_evaltag'])
        w.writerows(rows)

    qt.save(out / 'qtable.pkl', meta=vars(cfg))
    print(f"[ladder-train] done {time.perf_counter()-t0:.0f}s | saved {out}/qtable.pkl", flush=True)


if __name__ == '__main__':
    main()
