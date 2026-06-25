"""
train_pure_softmax_ablation.py  (Pure-vs-Prop 기여도 배분 통제실험 — softmax/mixed 매칭)
─────────────────────────────────────────────────────────────────────
목적: 분포강건성(vs Random·vs TAG 동시 흑자)이 비례배분(PROP)+VIC 라는
      "우리가 만든" 기여도 배분 설계의 산물이 아니라, **표준 몬테카를로(PURE)**
      대비 무엇이 다른지를 단일변수로 분리한다.

설계: ablation_vic_2m(PROP, softmax, mixed)와 **완전 매칭**된 조건에서
      기여도 배분만 PURE(표준 MC, 말단보상 γ-할인 역전파)로 바꾼 단 하나의 변경.

  공통(ablation_vic_2m/mixed 와 동일):
    - 탐색: softmax(Boltzmann), temperature 10.0→0.5 (80% 구간)
    - 상태: PrevAction 확장 (q[r][p][s][pa][a], 2,048 셀)
    - 학습상대: 혼합 5종 {tag,lag,man,sta,nit}, 가중 [.20,.25,.15,.25,.15]
    - 평가: base.evaluate (vs Random / 고정 TAG), 200게임/체크포인트
    - 하이퍼파라미터·온도·seed(42) 전부 동일

  유일 변경 = 기여도 배분(credit assignment):
    PROP : G_t = (invest_t / Σinvest) · payoff   → CHECK(invest=0)=0 → ZCA
    PURE : G_t = γ^(T-t) · payoff (말단보상만)    → CHECK도 할인보상 수령, 영-고정점 없음

  ★ VIC는 PURE에서 구조적으로 비활성(inert):
     PURE 기여도는 invest를 읽지 않으므로 CHECK_VIRTUAL_INVEST(1 or 0)가 결과에
     영향을 주지 않는다. 즉 PURE = "자연 VIC-on / ZCA 없는 표준 MC" 자체.
     → Pure-vs-Prop 은 2×2가 아니라 3-셀 비교다:
         (a) PROP+VIC-off [ZCA]
         (b) PROP+VIC-on  [ZCA 고정]
         (c) PURE         [ZCA 없음, VIC 무관]
       (a)(b)는 results/ablation_vic_2m/ 에 이미 존재 → 본 스크립트는 (c)만 생산.

CLI:
  argv[1] = out_dir   (default ../results/pure_softmax_mixed_2m)
  argv[2] = scheme    (single | cycle | mixed, default 'mixed')
  argv[3] = persona   (single 스킴 전용 학습상대, default 'tag')
  argv[4] = seed      (default 42 — ablation_vic_2m 매칭)
환경변수:
  ABLATION_EPISODES   (default 2_000_000; 스모크는 작게)
"""
import csv
import os
import random
import sys
import time
from pathlib import Path

import train_eval_mc_prop_softmax_2000k as base
import rulebased_personas as personas
from abstraction import (
    Round, State, Action, PrevAction,
    pk_to_round, pk_to_state, pk_to_position,
    legal_our_actions, execute_action,
)
from qlearning import QLearning

TOTAL_EPISODES = int(os.environ.get('ABLATION_EPISODES', 2_000_000))
EVAL_EVERY     = max(2_000, TOTAL_EPISODES // 250)   # 평가비율 0.4% (매칭)
EVAL_GAMES     = 200

# ablation_vic_2m 과 동일한 혼합 학습상대 풀·가중치
TRAIN_PERSONAS = ['tag', 'lag', 'man', 'sta', 'nit']
MIX_WEIGHTS    = [0.20, 0.25, 0.15, 0.25, 0.15]

STARTING_STACK = base.STARTING_STACK
ALPHA          = base.ALPHA
GAMMA          = base.GAMMA
_make_game     = base._make_game
temperature_at = base.temperature_at
evaluate       = base.evaluate
EvalResult     = base.EvalResult
_fmt_time      = base._fmt_time


def play_train_episode_pure(ql: QLearning, temperature: float,
                            policy: dict, learner_id: int = 0) -> float:
    """PROP 원본(train_softmax_persona_2000k.play_train_episode)과 동일한
    에피소드 진행. **유일 차이 = 마지막 기여도 배분 블록(PURE 표준 MC)**."""
    pk_state = _make_game()
    trace: list[tuple[Round, State, PrevAction, Action]] = []
    pos    = pk_to_position(learner_id)
    opp_id = 1 - learner_id
    prev_action_by_round: dict = {}

    while pk_state.status:
        if pk_state.can_deal_hole():
            pk_state.deal_hole()
        elif pk_state.can_deal_board():
            pk_state.deal_board()
        elif pk_state.actor_index is not None:
            pid = pk_state.actor_index
            if pid == learner_id:
                r     = pk_to_round(pk_state)
                s     = pk_to_state(pk_state, learner_id)
                pa    = prev_action_by_round.get(r, PrevAction.NONE)
                legal = legal_our_actions(pk_state)
                a = ql.softmax_action(r, pos, s, pa, legal, temperature)
                execute_action(pk_state, a)
                trace.append((r, s, pa, a))
            else:
                personas.step_persona_opponent(
                    pk_state, opp_id, policy, prev_action_by_round)
        else:
            break

    payoff = float(pk_state.stacks[learner_id] - STARTING_STACK)
    # ── PURE 표준 MC: 말단보상만, γ로 역할인 역전파 (invest 미사용 → VIC inert) ──
    G = payoff
    for (r, s, pa, a) in reversed(trace):
        ql.update_mc(r, pos, s, pa, a, G)
        G = GAMMA * G
    return payoff


def pick_persona(scheme: str, ep_index: int, rng: random.Random,
                 single_persona: str) -> str:
    if scheme == 'single':
        return single_persona
    if scheme == 'cycle':
        return TRAIN_PERSONAS[ep_index % len(TRAIN_PERSONAS)]
    return rng.choices(TRAIN_PERSONAS, weights=MIX_WEIGHTS, k=1)[0]


def main(out_dir: str, scheme: str, single_persona: str, seed: int):
    if scheme not in ('single', 'cycle', 'mixed'):
        raise SystemExit(f"unknown scheme '{scheme}'. choose single|cycle|mixed")
    if scheme == 'single' and single_persona not in TRAIN_PERSONAS:
        raise SystemExit(f"unknown persona '{single_persona}'. choose {TRAIN_PERSONAS}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "eval_results.csv"

    rng = random.Random(seed)
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
    print(f"  PURE CREDIT  |  scheme={label}  |  softmax  |  표준 MC(γ-discount)  |  "
          f"평가 vs Random / 고정TAG  |  {TOTAL_EPISODES:,} ep  |  seed={seed}", flush=True)
    print(f"  credit = PURE (G_t = γ^(T-t)·payoff); VIC inert", flush=True)
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
            play_train_episode_pure(ql, temp, policy, learner_id=i % 2)
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
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "../results/pure_softmax_mixed_2m"
    scheme  = sys.argv[2] if len(sys.argv) > 2 else "mixed"
    persona = sys.argv[3] if len(sys.argv) > 3 else "tag"
    seed    = int(sys.argv[4]) if len(sys.argv) > 4 else 42
    random.seed(seed)
    main(out_dir, scheme, single_persona=persona, seed=seed)
