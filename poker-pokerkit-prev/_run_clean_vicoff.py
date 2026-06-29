# -*- coding: utf-8 -*-
"""clean VIC-off 재현런 — ±1.4 누수가 ablation을 오염시키는지 검증.

mixed_vic_off(28번)와 100% 동일(mixed 페르소나, VIC off, 2M, seed=42)하되
total_invest==0(올체크) 핸드의 equal-split 누수만 제거(CLEAN_ZERO_INVEST=True).
단일변수 = 올체크 폴백 처리. dominance/OOD가 불변이면 누수 무해 확정.
실행: ../.venv/Scripts/python.exe _run_clean_vicoff.py
"""
import sys
import train_ablation_vic as abl
import train_softmax_persona_2000k as persona_base

persona_base.CLEAN_ZERO_INVEST = True   # 누수 제거
OUT = sys.argv[1] if len(sys.argv) > 1 else "../results/28_ablation_vic_2m/mixed_vic_off_clean"
print(f"[clean VIC-off] CLEAN_ZERO_INVEST={persona_base.CLEAN_ZERO_INVEST} | out={OUT}", flush=True)
abl.main(OUT, "mixed", vic_on=False, single_persona="tag", seed=42)
