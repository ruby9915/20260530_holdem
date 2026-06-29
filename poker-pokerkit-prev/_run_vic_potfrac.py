# -*- coding: utf-8 -*-
"""α%×팟 VIC 실험 — CHECK 가상 invest = α% × pot. 28번 single(TAG) clean 위에서 α 스윕.
argv: pot_mode(terminal|checktime)  alpha(%)  out_dir  [scheme=single].
누수 제거(CLEAN_ZERO_INVEST=True). 비교: off(α=0)·fixed-1은 기존 clean 라인.
"""
import sys
import train_ablation_vic as abl
import train_softmax_persona_2000k as pb

pb.CLEAN_ZERO_INVEST = True
pb.POT_MODE = sys.argv[1]                        # 'terminal' | 'checktime'
pb.CHECK_POT_FRAC = float(sys.argv[2]) / 100.0   # α% → 비율
out = sys.argv[3]
scheme = sys.argv[4] if len(sys.argv) > 4 else 'single'
print(f"[potfrac] mode={pb.POT_MODE} alpha={sys.argv[2]}% frac={pb.CHECK_POT_FRAC} "
      f"scheme={scheme} CLEAN={pb.CLEAN_ZERO_INVEST} out={out}", flush=True)
abl.main(out, scheme, vic_on=True, single_persona='tag', seed=42)
