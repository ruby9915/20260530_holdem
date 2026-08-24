# -*- coding: utf-8 -*-
"""36번 ε-greedy 교차 러너 (사전 등록: 실험일지 36절 (5), 저자 메모 39).
argv: mode alpha seed out_dir  (mode: off | fixed — _run_potfrac_seed.py와 동일 의미)

_run_potfrac_seed.py(30번 계열 clean 규약)를 그대로 따르되, 탐색만 교체하는 두 패치:
  1) QLearning.softmax_action -> epsilon_greedy (시그니처 동일 — 마지막 스칼라가 온도 대신 ε)
  2) abl.temperature_at -> ε 스케줄 1.0 -> 0.05 (예산의 80% 지점에서 하한, softmax
     온도 10.0 -> 0.5와 동일한 선형·동일 감쇠 구간 — 단일변수 성립)
분모는 abl.TOTAL_EPISODES를 참조하므로 ABLATION_EPISODES 환경변수로 스모크도 신축된다."""
import sys

import qlearning as ql
import train_ablation_vic as abl
import train_softmax_persona_2000k as pb

EPS_START, EPS_END, EPS_DECAY_END = 1.0, 0.05, 0.8


def eps_at(episode):
    progress = min(1.0, episode / (abl.TOTAL_EPISODES * EPS_DECAY_END))
    return EPS_START + (EPS_END - EPS_START) * progress


ql.QLearning.softmax_action = ql.QLearning.epsilon_greedy
abl.temperature_at = eps_at
pb.CLEAN_ZERO_INVEST = True
pb.POT_APPLY = 'all'
pb.POT_MODE = 'off'

mode = sys.argv[1]
alpha = float(sys.argv[2])
seed = int(sys.argv[3])
out = sys.argv[4]

if mode == 'off':
    vic_on = False
elif mode == 'fixed':
    abl.FIXED_VIC_OVERRIDE = alpha
    vic_on = True
else:
    raise SystemExit(f'unsupported mode for eps cross: {mode}')

print(f"[eps-cross] explore=epsilon_greedy eps {EPS_START}->{EPS_END}@{EPS_DECAY_END} "
      f"total={abl.TOTAL_EPISODES} mode={mode} alpha={alpha} seed={seed} "
      f"FIXED={abl.FIXED_VIC_OVERRIDE} vic={vic_on} clean={pb.CLEAN_ZERO_INVEST} out={out}",
      flush=True)
abl.main(out, 'single', vic_on=vic_on, single_persona='tag', seed=seed)
