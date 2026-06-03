"""
train_softmax_persona_mixed_2000k.py  (27번 실험 — 분포 강건성 / 혼합 페르소나)
─────────────────────────────────────────────────────────────────────
26번이 입증한 "단일 상대 = 과적합"(26a/26c vs Random 적자)을 넘기 위해,
학습 상대를 5종 페르소나의 혼합/순환으로 다양화한다.
알고리즘·하이퍼파라미터·평가는 26번과 100% 동일(비교 일관성).
유일한 변경 = 매 에피소드 상대 policy 선택.

핵심 통찰: 26번 학습 1에피소드 로직(play_train_episode)은 policy 객체 하나만
받으므로, 에피소드마다 policy 만 갈아끼우면 알고리즘은 한 줄도 안 바뀐다.
→ "혼합만 바꿨다"는 controlled comparison 성립.

가설 (사전 등록):
  H1  혼합 학습 → vs Random·vs 고정TAG 동시 raw-greedy 흑자(분포 강건성)
  H0  여전히 한쪽 적자 → 전이 병목이 단순 혼합으로 불충분(더 강한 음성)
  판정: 평균 - 1·회차SD > 0 이 두 상대 모두에서 성립해야 H1 채택.

CLI:
  argv[1] = out_dir
  argv[2] = scheme  (cycle | mixed, default 'cycle')
"""
import csv
import random
import sys
import time
from pathlib import Path

import train_eval_mc_prop_softmax_2000k as base
import train_softmax_persona_2000k as persona_base   # play_train_episode 재사용
import rulebased_personas as personas
from qlearning import QLearning

TOTAL_EPISODES = 2_000_000
EVAL_EVERY     = 8_000     # 26번과 동일(평가비율 0.4%)
EVAL_GAMES     = 200

# 26번에서 vs Random 적자였던 lag/sta 를 반드시 포함(병목 직격).
# nit/man 도 넣어 도달 컨텍스트 다양화. tag 는 평가 상대이므로 학습에도 포함.
TRAIN_PERSONAS = ['tag', 'lag', 'man', 'sta', 'nit']
# mixed 스킴 가중치: 26번 vs Random 적자였던 lag/sta 가중↑(병목 직격).
MIX_WEIGHTS    = [0.20, 0.25, 0.15, 0.25, 0.15]

ALPHA          = base.ALPHA
GAMMA          = base.GAMMA
temperature_at = base.temperature_at
evaluate       = base.evaluate
EvalResult     = base.EvalResult
_fmt_time      = base._fmt_time


def pick_persona(scheme: str, ep_index: int, rng: random.Random) -> str:
    if scheme == 'cycle':
        return TRAIN_PERSONAS[ep_index % len(TRAIN_PERSONAS)]
    # mixed
    return rng.choices(TRAIN_PERSONAS, weights=MIX_WEIGHTS, k=1)[0]


def main(out_dir: str, scheme: str):
    if scheme not in ('cycle', 'mixed'):
        raise SystemExit(f"unknown scheme '{scheme}'. choose from cycle|mixed")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "eval_results.csv"

    rng = random.Random(42)
    ql = QLearning(alpha=ALPHA, gamma=GAMMA, ucb_c=50.0)
    policies = {p: personas.PERSONA_POLICIES[p] for p in TRAIN_PERSONAS}
    results = []

    hdr = (f"{'episode':>9} {'pct':>5} {'temp':>5} |"
           f" {'rand%':>6} {'mbb/g_r':>10} |"
           f" {'rule%':>6} {'mbb/g_rl':>10} |"
           f" {'ep/s':>6} {'elapsed':>9} {'ETA':>9}")
    sep = "-" * len(hdr)
    print(sep, flush=True)
    print(f"  27번 MIXED PERSONA  |  scheme={scheme.upper()}  |  "
          f"학습상대={'/'.join(p.upper() for p in TRAIN_PERSONAS)}  |  "
          f"평가 vs Random / 고정TAG  |  {TOTAL_EPISODES:,} ep", flush=True)
    if scheme == 'mixed':
        print(f"  mix weights: "
              f"{dict(zip(TRAIN_PERSONAS, MIX_WEIGHTS))}", flush=True)
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
            persona = pick_persona(scheme, i, rng)
            policy  = policies[persona]
            # 26번 학습 1에피소드 로직 그대로 재사용(learner_id 교대도 동일).
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
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "../results/27a_persona_cycle_2000k"
    scheme  = sys.argv[2] if len(sys.argv) > 2 else "cycle"
    random.seed(42)
    main(out_dir, scheme)
