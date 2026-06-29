# -*- coding: utf-8 -*-
"""19번 Random 라인 시드 스윕 러너. argv: <vic on|off> <seed> <out_dir>.
19번 base를 import해 VIC만 토글 + seed만 바꿈. 그 외(softmax·Random학습·2M·평가) 동일."""
import sys, os, random
import train_eval_mc_prop_softmax_2000k as base

vic  = sys.argv[1] if len(sys.argv) > 1 else "on"
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
out  = sys.argv[3] if len(sys.argv) > 3 else "../results/28c_seedsweep/rand_on_s42"

os.makedirs(out, exist_ok=True)
base.CHECK_VIRTUAL_INVEST = 1 if vic == "on" else 0
base.CSV_PATH = out + "/eval_results.csv"
print(f"  [Random-line] VIC={vic} | seed={seed} | out={out}", flush=True)
random.seed(seed)
base.main()
