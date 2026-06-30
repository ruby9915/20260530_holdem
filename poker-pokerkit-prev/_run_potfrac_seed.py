# -*- coding: utf-8 -*-
"""α-pot VIC seed sweep 러너. argv: mode(terminal|off) alpha(%) seed out_dir.
mode='off'면 VIC 없음(CHECK invest=0). 그 외 terminal pot α%. single/TAG, clean(누수제거).
seed 42 기존 런과 합쳐 α당 다중 seed 비교."""
import sys
import train_ablation_vic as abl
import train_softmax_persona_2000k as pb

pb.CLEAN_ZERO_INVEST = True
mode  = sys.argv[1]            # 'terminal' | 'off'
alpha = float(sys.argv[2])     # % (off면 0)
seed  = int(sys.argv[3])
out   = sys.argv[4]
if mode == 'off':
    pb.POT_MODE = 'off'
    vic_on = False
else:
    pb.POT_MODE = mode
    pb.CHECK_POT_FRAC = alpha / 100.0
    vic_on = True
print(f"[seedsweep] mode={mode} α={alpha}% seed={seed} POT_MODE={pb.POT_MODE} vic={vic_on} out={out}", flush=True)
abl.main(out, 'single', vic_on=vic_on, single_persona='tag', seed=seed)
