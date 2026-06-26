# -*- coding: utf-8 -*-
"""clean VIC ablation 단일 런 — CLEAN_ZERO_INVEST=True(올체크 누수 제거).
argv: scheme(single|cycle|mixed) vic(on|off) out_dir [persona].
mixed_vic_off_clean에서 확인한 누수 제거를 6조건 전체로 확장(Table 5 권위값 재산출).
"""
import sys
import train_ablation_vic as abl
import train_softmax_persona_2000k as persona_base

persona_base.CLEAN_ZERO_INVEST = True   # 누수 제거(전 조건 동일 적용)
scheme  = sys.argv[1]
vic     = sys.argv[2]
out     = sys.argv[3]
persona = sys.argv[4] if len(sys.argv) > 4 else "tag"
print(f"[clean ablation] scheme={scheme} vic={vic} CLEAN_ZERO_INVEST=True out={out}", flush=True)
abl.main(out, scheme, vic_on=(vic == "on"), single_persona=persona, seed=42)
