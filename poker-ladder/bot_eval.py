# -*- coding: utf-8 -*-
"""CFR+ 봇 품질 게이트 — 봇 vs 페르소나 5종 대국 (판정 기준: 전 흑자).

usage: python bot_eval.py [n_games=20000] [strategy_npz]
보고: 페르소나별 봇의 mbb/g ± SE + 번역 발동률.
"""
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from cfr_opponent import CfrOpponent
from game import BIG_BLIND, STARTING_STACK, make_game
from personas import PERSONA_POLICIES, step_opponent


def play(bot, persona_policy, bot_id):
    pk = make_game()
    bot.reset(bot_id)
    prev: dict = {}
    while pk.status:
        if pk.can_deal_hole():
            pk.deal_hole()
        elif pk.can_deal_board():
            pk.deal_board()
        elif pk.actor_index is not None:
            if pk.actor_index == bot_id:
                bot.step(pk, bot_id, prev)
            else:
                step_opponent(pk, 1 - bot_id, persona_policy, prev)
        else:
            break
    return float(pk.stacks[bot_id] - STARTING_STACK)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    path = sys.argv[2] if len(sys.argv) > 2 else None
    bot = CfrOpponent(strategy_path=path, rng_seed=777)
    random.seed(777)
    scale = 1000.0 / BIG_BLIND
    results = {}
    for name, policy in PERSONA_POLICIES.items():
        pays = [play(bot, policy, i % 2) for i in range(n)]
        m = statistics.mean(pays) * scale
        se = statistics.stdev(pays) / math.sqrt(n) * scale
        results[name] = (m, se)
        print(f"  ({(list(PERSONA_POLICIES).index(name)+1)/5*100:5.1f}%) "
              f"bot vs {name:<4} n={n} | {m:+8.1f} ± {se:.1f} mbb/g", flush=True)
    tr_rate = bot.translations / max(bot.decisions, 1) * 100
    print(f"  번역 발동: {bot.translations}회 / 결정 {bot.decisions}회 = {tr_rate:.3f}%", flush=True)
    all_pos = all(m > 0 for m, _ in results.values())
    print(f"==> 품질 게이트(페르소나 전 흑자): {'PASS' if all_pos else 'FAIL'} | "
          + ' '.join(f"{k}:{v[0]:+.0f}" for k, v in results.items()), flush=True)


if __name__ == '__main__':
    main()
