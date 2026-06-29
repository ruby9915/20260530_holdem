# -*- coding: utf-8 -*-
"""softmax + VIC OFF + Random 학습 — 19번(softmax+VIC on)과 100% 매칭, CHECK_VIRTUAL_INVEST만 0.
(softmax × VIC) 2×2를 19번 메인 라인에서 닫기 위한 통제 런.
유일 변경: CHECK_VIRTUAL_INVEST = 1(19) → 0(이 런). 그 외(softmax·온도·Random학습·seed=42·2M·평가) 동일."""
import random
import train_eval_mc_prop_softmax_2000k as base

base.CHECK_VIRTUAL_INVEST = 0   # ← VIC OFF (유일 변경)
base.CSV_PATH = "../results/28b_softmax_novic_random_2m/eval_results.csv"

random.seed(42)                 # 19번과 동일 seed
base.main()
