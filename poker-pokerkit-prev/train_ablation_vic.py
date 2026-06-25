"""
train_ablation_vic.py  (VIC ablation — CHECK 흡수 해제가 분포강건성의 필요조건인가)
─────────────────────────────────────────────────────────────────────
가설: 27a/27b의 vs Random·vs TAG 동시 흑자(분포강건성)는
      VIC(CHECK=1chip 가상 정보비용)로 ZCA(영-비용 흡수)를 깬 토대 위에서만
      성립한다. VIC를 끄면(CHECK invest=0) 혼합 학습을 줘도 흡수로 붕괴한다.

설계: 2×3 controlled ablation
      scheme ∈ {single, cycle, mixed}  ×  vic ∈ {on, off}
      유일 변경 = (a) 상대 분포 선택, (b) CHECK_VIRTUAL_INVEST (1 or 0).
      알고리즘·하이퍼파라미터·평가·seed 전부 동일.

VIC 토글: play_train_episode 가 참조하는 persona_base 모듈 전역
          CHECK_VIRTUAL_INVEST 를 런타임에 1(on)/0(off) 로 덮어쓴다.

CLI:
  argv[1] = out_dir
  argv[2] = scheme   (single | cycle | mixed, default 'mixed')
  argv[3] = vic      (on | off, default 'on')
  argv[4] = persona  (single 스킴 전용 학습 상대, default 'tag')
"""
import csv
import os
import random
import sys
import time
from pathlib import Path

import train_eval_mc_prop_softmax_2000k as base
import train_softmax_persona_2000k as persona_base   # play_train_episode 재사용
import rulebased_personas as personas
from qlearning import QLearning

# 기본 2M. 스모크는 환경변수로 단축: ABLATION_EPISODES=200000
TOTAL_EPISODES = int(os.environ.get('ABLATION_EPISODES', 2_000_000))
EVAL_EVERY     = max(2_000, TOTAL_EPISODES // 250)   # 27번과 동일 비율(0.4%)
EVAL_GAMES     = 200

# 27번과 동일한 학습 상대 풀·가중치(병목 직격: lag/sta 가중↑).
TRAIN_PERSONAS = ['tag', 'lag', 'man', 'sta', 'nit']
MIX_WEIGHTS    = [0.20, 0.25, 0.15, 0.25, 0.15]

ALPHA          = base.ALPHA
GAMMA          = base.GAMMA
temperature_at = base.temperature_at
evaluate       = base.evaluate
EvalResult     = base.EvalResult
_fmt_time      = base._fmt_time


def pick_persona(scheme: str, ep_index: int, rng: random.Random,
                 single_persona: str) -> str:
    if scheme == 'single':
        return single_persona
    if scheme == 'cycle':
        return TRAIN_PERSONAS[ep_index % len(TRAIN_PERSONAS)]
    # mixed
    return rng.choices(TRAIN_PERSONAS, weights=MIX_WEIGHTS, k=1)[0]


def main(out_dir: str, scheme: str, vic_on: bool, single_persona: str, seed: int = 42):
    if scheme not in ('single', 'cycle', 'mixed'):
        raise SystemExit(f"unknown scheme '{scheme}'. choose single|cycle|mixed")
    if scheme == 'single' and single_persona not in TRAIN_PERSONAS:
        raise SystemExit(f"unknown persona '{single_persona}'. "
                         f"choose from {TRAIN_PERSONAS}")

    # ── VIC 토글: play_train_episode 가 읽는 모듈 전역을 덮어쓴다 ──
    persona_base.CHECK_VIRTUAL_INVEST = 1 if vic_on else 0

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "eval_results.csv"

    random.seed(seed)              # 전역 RNG: 카드 분배·행동 샘플링·상대 행동
    rng = random.Random(seed)      # 페르소나 선택 RNG
    ql = QLearning(alpha=ALPHA, gamma=GAMMA, ucb_c=50.0)
    policies = {p: personas.PERSONA_POLICIES[p] for p in TRAIN_PERSONAS}
    results = []

    hdr = (f"{'episode':>9} {'pct':>5} {'temp':>5} |"
           f" {'rand%':>6} {'mbb/g_r':>10} |"
           f" {'rule%':>6} {'mbb/g_rl':>10} |"
           f" {'ep/s':>6} {'elapsed':>9} {'ETA':>9}")
    sep = "-" * len(hdr)
    label = scheme.upper() + (f"({single_persona})" if scheme == 'single' else '')
    print(sep, flush=True)
    print(f"  VIC ABLATION  |  scheme={label}  |  VIC={'ON(1chip)' if vic_on else 'OFF(0)'}  |  "
          f"평가 vs Random / 고정TAG  |  {TOTAL_EPISODES:,} ep  |  seed={seed}", flush=True)
    print(f"  CHECK_VIRTUAL_INVEST = {persona_base.CHECK_VIRTUAL_INVEST}", flush=True)
    if scheme == 'mixed':
        print(f"  mix weights: {dict(zip(TRAIN_PERSONAS, MIX_WEIGHTS))}", flush=True)
    print(f"  out: {out}", flush=True)
    print(sep, flush=True)
    print(hdr, flush=True)
    print(sep, flush=True)

    t_start = time.perf_counter()
    t_last  = t_start
    ep_last = 0

    wr, mr, sr, wrb, mrb, srb = evaluate(ql, EVAL_GAMES)
    results.append(EvalResult(0, wr, mr, sr, wrb, mrb, srb))
    print(f"{0:>9} {'0.0%':>5} {temperature_at(0):>5.1f} |"
          f" {wr*100:>5.1f}% {mr:>+9.0f} |"
          f" {wrb*100:>5.1f}% {mrb:>+9.0f} |"
          f" {'-':>6} {_fmt_time(time.perf_counter()-t_start):>9} {'-':>9}", flush=True)

    ep = 0
    while ep < TOTAL_EPISODES:
        next_eval = min(ep + EVAL_EVERY, TOTAL_EPISODES)
        for i in range(ep + 1, next_eval + 1):
            temp    = temperature_at(i)
            persona = pick_persona(scheme, i, rng, single_persona)
            policy  = policies[persona]
            persona_base.play_train_episode(ql, temp, policy, learner_id=i % 2)
        ep = next_eval

        t_now    = time.perf_counter()
        interval = t_now - t_last
        speed    = (ep - ep_last) / interval if interval > 0 else 0.0
        eta      = (TOTAL_EPISODES - ep) / speed if speed > 0 else 0.0
        t_last, ep_last = t_now, ep

        wr, mr, sr, wrb, mrb, srb = evaluate(ql, EVAL_GAMES)
        results.append(EvalResult(ep, wr, mr, sr, wrb, mrb, srb))
        print(f"{ep:>9} {ep/TOTAL_EPISODES*100:>4.1f}% {temperature_at(ep):>5.2f} |"
              f" {wr*100:>5.1f}% {mr:>+9.0f} |"
              f" {wrb*100:>5.1f}% {mrb:>+9.0f} |"
              f" {speed:>6.0f} {_fmt_time(t_now-t_start):>9} {_fmt_time(eta):>9}", flush=True)

    print(sep, flush=True)
    total = time.perf_counter() - t_start
    print(f"  Total: {_fmt_time(total)}  |  Avg: {TOTAL_EPISODES/total:.0f} ep/s", flush=True)
    print(sep, flush=True)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['episode',
                    'win%_vs_random', 'mbb/g_vs_random', 'se_vs_random',
                    'win%_vs_rulebased', 'mbb/g_vs_rulebased', 'se_vs_rulebased'])
        for r in results:
            w.writerow([r.episode,
                        f"{r.win_vs_random:.4f}", f"{r.mbb_vs_random:.2f}", f"{r.se_vs_random:.2f}",
                        f"{r.win_vs_rule:.4f}",   f"{r.mbb_vs_rule:.2f}",   f"{r.se_vs_rule:.2f}"])
    print(f"CSV saved: {csv_path}", flush=True)

    qmd_path = out / "qtable.md"
    print(f"Q-table markdown saved: {ql.save_qtable_markdown(str(qmd_path))}", flush=True)
    print(f"pickle saved: {ql.save(str(out / 'eval_results.pkl'))}", flush=True)


if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "../results/ablation_vic_smoke"
    scheme  = sys.argv[2] if len(sys.argv) > 2 else "mixed"
    vic     = (sys.argv[3] if len(sys.argv) > 3 else "on").lower()
    persona = sys.argv[4] if len(sys.argv) > 4 else "tag"
    seed    = int(sys.argv[5]) if len(sys.argv) > 5 else 42
    if vic not in ('on', 'off'):
        raise SystemExit("vic must be 'on' or 'off'")
    main(out_dir, scheme, vic_on=(vic == 'on'), single_persona=persona, seed=seed)
