# -*- coding: utf-8 -*-
"""E8 rival bake-off 러너 — ZCA에 대한 경쟁 처방 3종 (전부 VIC 없음, clean, single-TAG).
argv: mode param seed out_dir
  mode  : optimistic | uniform | slowexp
          optimistic = 낙관적 초기화 (전 셀 Q0=param 칩; 예측: 재고정 → 무효)
          uniform    = 일률 가산 벌점 (전 행동 credit − param 칩; 예측: 순위 불변 → 무효)
          slowexp    = 탐색 강화 (온도 하한 param; 예측: 방문↑ → 재고정 → 무효)
이론 대응: Prop 1(낙관적 초기화 일시성), IV장 탈출 메커니즘 비교, action-penalty[8] 비선택성."""
import sys
import qlearning as qlmod
import train_ablation_vic as abl
import train_softmax_persona_2000k as pb

pb.CLEAN_ZERO_INVEST = True
mode  = sys.argv[1]
param = float(sys.argv[2])
seed  = int(sys.argv[3])
out   = sys.argv[4]

if mode == 'optimistic':
    _orig_init = qlmod.QLearning.__init__

    def _patched_init(self, *a, **k):
        _orig_init(self, *a, **k)
        for l1 in self.q:                 # q[r][pos][s][pa][a]
            for l2 in l1:
                for l3 in l2:
                    for l4 in l3:
                        for i in range(len(l4)):
                            l4[i] = param
    qlmod.QLearning.__init__ = _patched_init
elif mode == 'uniform':
    pb.UNIFORM_PENALTY = param
elif mode == 'slowexp':
    _base_temp = abl.temperature_at
    abl.temperature_at = lambda ep: max(_base_temp(ep), param)
else:
    raise SystemExit(f"unknown mode '{mode}'. choose optimistic|uniform|slowexp")

print(f"[rival] mode={mode} param={param} seed={seed} out={out} "
      f"UNIFORM_PENALTY={pb.UNIFORM_PENALTY} CLEAN={pb.CLEAN_ZERO_INVEST}", flush=True)
abl.main(out, 'single', vic_on=False, single_persona='tag', seed=seed)
