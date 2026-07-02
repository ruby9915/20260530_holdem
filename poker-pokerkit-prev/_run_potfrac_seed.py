# -*- coding: utf-8 -*-
"""α-pot VIC seed sweep 러너 (E1/E3/E5/E6 공용).
argv: mode alpha seed out_dir [scheme=single] [apply=all]
  mode  : off | terminal | checktime | fixed
          off      = VIC 없음(CHECK invest 0)
          terminal = CHECK 가상 invest = alpha% × 핸드 최종 팟
          checktime= CHECK 가상 invest = alpha% × 체크시점 팟
          fixed    = CHECK 가상 invest = alpha 칩 고정 (E3 fixed-K; alpha를 칩수로 해석)
  apply : all | invested_only | allcheck_only   (E1 올체크-핸드 격리)
전 조건 clean(누수 폴백 제거). seed 42 기존 런과 합쳐 다중 seed 비교."""
import sys
import train_ablation_vic as abl
import train_softmax_persona_2000k as pb

pb.CLEAN_ZERO_INVEST = True
mode   = sys.argv[1]
alpha  = float(sys.argv[2])
seed   = int(sys.argv[3])
out    = sys.argv[4]
scheme = sys.argv[5] if len(sys.argv) > 5 else 'single'
apply_ = sys.argv[6] if len(sys.argv) > 6 else 'all'
pb.POT_APPLY = apply_

if mode == 'off':
    pb.POT_MODE = 'off'
    vic_on = False
elif mode == 'fixed':
    pb.POT_MODE = 'off'
    abl.FIXED_VIC_OVERRIDE = alpha          # K칩 고정
    vic_on = True
else:                                        # terminal | checktime
    pb.POT_MODE = mode
    pb.CHECK_POT_FRAC = alpha / 100.0
    vic_on = True

print(f"[potfrac] mode={mode} alpha={alpha} seed={seed} scheme={scheme} apply={apply_} "
      f"POT_MODE={pb.POT_MODE} FIXED={abl.FIXED_VIC_OVERRIDE} vic={vic_on} out={out}", flush=True)
abl.main(out, scheme, vic_on=vic_on, single_persona='tag', seed=seed)
