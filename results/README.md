# 실험 결과 인덱스

각 폴더는 한 번의 학습 런(run)에 대응. CSV는 평가 시점별 승률·mbb/g·표준오차를 담고 있고, 400k 런은 stdout 학습 로그(`train_log.txt`)도 함께 보관.

## CSV 스키마 (공통)

```
episode, win%_vs_random, mbb/g_vs_random, se_vs_random,
         win%_vs_rulebased, mbb/g_vs_rulebased, se_vs_rulebased
```

mbb/g = payoff × 1000 / BIG_BLIND (BB=2 기준 ×500). 평가 게임 수 200, 표준오차는 1σ.

---

## 실험 순서

본 연구는 **tabular model-free RL**(라운드 × 포지션 × 핸드 버킷 × 직전 행동 → Q-table)이라는 골격을 1번에 잡아두고, 거기에 한 번에 한 가지씩만 — 알고리즘, 탐색, 보상 신호, 상태 차원, 학습량 — 을 더하거나 빼면서 효과를 측정해 나간 기록이다. **이전 대비 Δ** 컬럼은 그 한 단계 변화가 무엇이었는지를 가리킨다 (`+` 추가, `−` 제거, `→` 교체, `×n` 학습량 배수).

| # | 폴더 | 모델 | 탐색 | 보상 신호 | 에피소드 | 이전 대비 Δ | 결과 요약 |
|---|---|---|---|---|---|---|---|
| 1 | [`01_mc_eps_imm_40k`](01_mc_eps_imm_40k/) | MC | ε-greedy | terminal + imm | 40k | (베이스라인) | 정책 붕괴 (vs Rand 32%) |
| 2 | [`02_td_ucb_40k`](02_td_ucb_40k/) | TD(0) | UCB1 | step reward | 40k | MC→TD, ε→UCB, 보상→step | 안정 (vs Rand 75%) |
| 3 | [`03_mc_ucb_imm_40k`](03_mc_ucb_imm_40k/) | MC | UCB1 | terminal + imm | 40k | (vs 1) ε→UCB | 붕괴 (vs Rand 36%) — 탐색 바꿔도 동일 |
| 4 | [`04_mc_pure_40k`](04_mc_pure_40k/) | MC | UCB1 | payoff only | 40k | (vs 3) imm 제거 (Pure) | 안정 (vs Rand 80%) — imm이 원인 확정 |
| 5 | [`05_mc_prop_40k`](05_mc_prop_40k/) | MC | UCB1 | payoff × invest 비율 | 40k | (vs 4) Pure→비례배분 | mbb 안정 (vs Rule mbb≈0) |
| 6 | [`06_td_eps_400k`](06_td_eps_400k/) | TD(0) | ε-greedy | step reward | 400k | (vs 2) UCB→ε, ×10 | 완주 (vs Rand 79.5%, vs Rule mbb -3,823) |
| 7 | [`07_td_ucb_400k`](07_td_ucb_400k/) | TD(0) | UCB1 | step reward | 400k | (vs 2) ×10 | 완주 (vs Rand 71%, vs Rule mbb -4,953) |
| 8 | [`08_mc_pure_400k`](08_mc_pure_400k/) | MC | UCB1 | payoff only | 400k | (vs 4) ×10 | 완주 — 가설 검증용 |
| 9 | [`09_mc_prop_400k`](09_mc_prop_400k/) | MC | UCB1 | payoff × invest 비율 | 400k | (vs 5) ×10 | 완주 — 가설 검증용 |
| 10 | [`10_mc_pure_eps_400k`](10_mc_pure_eps_400k/) | MC | **ε-greedy** | payoff only | 400k | (vs 8) UCB→ε | 완주 (vs Rule mbb -1,810) |
| 11 | [`11_mc_prop_eps_400k`](11_mc_prop_eps_400k/) | MC | **ε-greedy** | payoff × invest 비율 | 400k | (vs 9) UCB→ε | 완주 (vs Rule mbb **-152**, SE=44) — break-even 근접 |
| 12 | [`12_mc_prop_eps_prev_400k`](12_mc_prop_eps_prev_400k/) | MC Prop ε + **PrevAction** | ε-greedy | payoff × invest 비율 | 400k | (vs 11) 상태 +PrevAction 4종 (×4) | 완주 (vs Rule mbb -807) — 상태 확장 후 분산 증가 |
| 12c | [`12c_mc_prop_eps_prev_800k`](12c_mc_prop_eps_prev_800k/) | MC Prop ε + PrevAction | ε-greedy | payoff × invest 비율 | **800k** | (vs 12) ×2 | SE 검증용 연장 (vs Rule mbb -523) |
| 12v2 | [`12_mc_prop_eps_prev_400k_v2`](12_mc_prop_eps_prev_400k_v2/) | MC Prop ε + PrevAction | ε-greedy | payoff × invest 비율 | 400k | (vs 12) 워크스페이스 이전 후 재실행 | vsRule mbb -735 (12번 -807과 근사, 랜덤 시드 차이) |
| 13 | [`13_td_eps_prev_400k`](13_td_eps_prev_400k/) | **TD(0)** ε + PrevAction | ε-greedy | bootstrap | 400k | (vs 6) +PrevAction | 완주 — TD maximization bias 폭주 (vs Rule mbb -6,734) |
| 14 | [`14_mc_pure_eps_prev_400k`](14_mc_pure_eps_prev_400k/) | MC Pure ε + PrevAction | ε-greedy | payoff only | 400k | (vs 10) +PrevAction | 완주 — Pure MC + ε-decay 붕괴 패턴 재확인 |
| 15 | [`15_mc_pure_eps_prev_1200k`](15_mc_pure_eps_prev_1200k/) | MC Pure ε + PrevAction | ε-greedy | payoff only | **1200k** | (vs 14) ×3 | 완주 — 학습량 늘려도 ε-decay 락인 지속, **Pure MC + ε-decay는 학습 불가 확정** |
| 16 | [`16_mc_prop_check1_eps_prev_1200k`](16_mc_prop_check1_eps_prev_1200k/) | MC Prop ε + PrevAction + **CHECK=1chip** | ε-greedy | payoff × invest 비율 | 1200k | (vs 12) +CHECK=1chip 가상투자, ×3 | **100k×5: vsRand +4,981.6 / vsRule −1,145.8(SD 28.2) → vsTAG 적자**. 기존 "vs Rule +10 첫 양수"는 200게임 체크포인트 착시(정정). 정밀평가는 OOD+/ID− 해리. VIC-on 단독 런이라 ZCA/VIC 인과는 ablation(28번)에 귀속, 16은 정성 사례로만 |
| 17 | [`17_mc_binary_eps_prev_1200k`](17_mc_binary_eps_prev_1200k/) | MC Binary ε + PrevAction + CHECK=1chip | ε-greedy | sign(payoff) × invest 비율 | 1200k | (vs 16) 보상 prop→binary | **100k×5: vsRand +7,574.8 / vsRule −3,654.2(SD 137)**. (기존 vsRule −788은 200게임) prop(16) 대비 강상대 더 열세 |
| 18 | [`18_mc_potnorm_eps_prev_1200k`](18_mc_potnorm_eps_prev_1200k/) | MC PotNorm ε + PrevAction + CHECK=1chip | ε-greedy | (invest / total) × (payoff / pot) | 1200k | (vs 16) 보상 prop→potnorm | **100k×5: vsRand +12,211.2 / vsRule −1,616.8(SD 55)**. (기존 vsRule −2,055은 200게임) 보상 potnorm |
| 19 | [`19_mc_prop_softmax_prev_2000k`](19_mc_prop_softmax_prev_2000k/) | MC Prop Softmax + PrevAction + CHECK=1chip | **Softmax** | payoff × invest 비율 | **2000k** | (vs 16) ε→Softmax(온도감쇠), ×1.67 | 100k×3 vs Rule **+124.6**. **100k×5: vsRand +277.0 / vsRule +112.1 → BOTH+** — 첫 진짜 일반화 성공(둘 다 흑자) |
| 20 | [`20_mc_prop_softmax_pypokerengine`](20_mc_prop_softmax_pypokerengine/) | 19번 최종 모델 vs PyPokerEngine Random/Honest | 평가 전용 | 외부 오픈소스 봇 교차검증 | 10k / 100k | (vs 19) 평가 엔진 pokerkit→PyPokerEngine | Honest 100k×3 평균 **+447.0 mbb/g**, Random 100k×3 평균 **+25.9 mbb/g** — 외부 봇 상대도 흑자 |
| 21a | [`21a_softmax_random_2000k`](21a_softmax_random_2000k/) | MC Prop Softmax + PrevAction + CHECK=1chip | Softmax | payoff × invest 비율 | **2000k** | (vs 19) 상대→**Random 단독** | **= 19와 동일 설정**(softmax 2M, vs Random, seed 42) → 동일 Q-table(결정론적 재현, 손상 아님; `eval_results.pkl` md5가 19·20과 동일한 건 정상). **100k×5: vsRand +277.0 / vsRule +112.1 = BOTH+** → Random 단독 학습도 일반화 성공. 기존 "−915 실패"는 200게임 착시 |
| 21b | [`21b_softmax_rulebased_2000k`](21b_softmax_rulebased_2000k/) | MC Prop Softmax + PrevAction + CHECK=1chip | Softmax | payoff × invest 비율 | **2000k** | (vs 19) 상대→**RuleBased 단독** | vsRand mbb +895, vsRule mbb **+762** — 흑자이나 상대 특화 과적합 |
| 21c | [`21c_softmax_selfplay_2000k`](21c_softmax_selfplay_2000k/) | MC Prop Softmax + PrevAction + CHECK=1chip | Softmax | payoff × invest 비율 | **2000k** | (vs 19) 상대→**Self-play 단독** | vsRand mbb +3,952, vsRule mbb **-7,005** — Self-play 단독은 RuleBased 극단 열세 |
| 22 | [`22_mc_prop_ucb_smoke_200k`](22_mc_prop_ucb_smoke_200k/) | MC Prop **UCB1** + PrevAction + CHECK=1chip | UCB1 (C=50) | payoff × invest 비율 | 200k (스모크) | (vs 16) ε→UCB1 | vsRule mbb +532(SE=507) — UCB_C=50 과대(Q스케일 대비), vs Rand win% 단조 하락(62.5%→27.5%), 2M 연장 불필요 판정 |
| 24 | [`24_softmax_mixed_8000k`](24_softmax_mixed_8000k/) | MC Prop Softmax + PrevAction + CHECK=1chip | Softmax | payoff × invest 비율 | **8000k** | (vs 19) 혼합 상대 + ×4 학습량 | **100k×5: vsRand −479.3(SD 0.7) / vsTAG −111.7(SD 1.3) → BOTH−**. 학습량 ×4(8M)가 흑자를 보장하지 않음(안정적 적자)을 확정 (기존 "100k 미수행" 표기 정정) |
| 25a | [`25a_temp_baseline_2000k`](25a_temp_baseline_2000k/) | Softmax 온도 baseline | Softmax | payoff × invest 비율 | 2000k | (vs 19) 온도 스케줄 baseline | vsRand **+600.8**, vsTAG **−77.7** (100k×5) |
| 25b | [`25b_temp_hi_2000k`](25b_temp_hi_2000k/) | Softmax 고온 | Softmax | payoff × invest 비율 | 2000k | (vs 25a) 초기 온도↑ | vsRand **+647.3**, vsTAG **+97.2** (100k×5) — 온도 sweep 중 vsTAG 유일 흑자 |
| 25c | [`25c_temp_slow_2000k`](25c_temp_slow_2000k/) | Softmax 완만감쇠 | Softmax | payoff × invest 비율 | 2000k | (vs 25a) 감쇠 속도↓ | vsRand **+318.7**, vsTAG **−53.0** (100k×5) |
| 25d | [`25d_temp_floor_2000k`](25d_temp_floor_2000k/) | Softmax 하한온도 | Softmax | payoff × invest 비율 | 2000k | (vs 25a) 온도 floor 추가 | vsRand **+277.9**, vsTAG **+10.5** (100k×5, vsTAG는 0과 무차별·SD 내) |
| 26a | [`26a_persona_lag_2000k`](26a_persona_lag_2000k/) | Softmax vs **LAG** 페르소나 | Softmax | payoff × invest 비율 | 2000k | (vs 19) 상대→LAG 단독 | vsRand **−563.0**, vsTAG **+932.6** (100k×5) — LAG 특화 시 vsRand 적자 |
| 26b | [`26b_persona_man_2000k`](26b_persona_man_2000k/) | Softmax vs **Maniac** 페르소나 | Softmax | payoff × invest 비율 | 2000k | (vs 19) 상대→Maniac 단독 | vsRand **+38.7**, vsTAG **+68.9** (100k×5) |
| 26c | [`26c_persona_sta_2000k`](26c_persona_sta_2000k/) | Softmax vs **Station** 페르소나 | Softmax | payoff × invest 비율 | 2000k | (vs 19) 상대→Station 단독 | vsRand **−674.5**, vsTAG **+778.0** (100k×5) |
| 26d | [`26d_persona_nit_2000k`](26d_persona_nit_2000k/) | Softmax vs **Nit** 페르소나 | Softmax | payoff × invest 비율 | 2000k | (vs 19) 상대→Nit 단독 | vsRand **+1280.8**, vsTAG **+853.8** (100k×5) |
| 26e | [`26e_persona_tag_2000k`](26e_persona_tag_2000k/) | Softmax vs **TAG** 페르소나 | Softmax | payoff × invest 비율 | 2000k | (vs 19) 상대→TAG 단독 | vsRand **+987.1**, vsTAG **+940.4** (100k×5) — 단일 페르소나 중 최고. ablation single/on과 동일 수치(권위 확인) |
| 27a | [`27a_persona_cycle_2000k`](27a_persona_cycle_2000k/) | Softmax vs **순환** 페르소나 | Softmax | payoff × invest 비율 | 2000k | (vs 26) 5종 페르소나 순환 노출 | vsRand **+681.3**, vsTAG **+868.3** (VIC on, 100k×5) |
| 27b | [`27b_persona_mixed_2000k`](27b_persona_mixed_2000k/) | Softmax vs **혼합** 페르소나 | Softmax | payoff × invest 비율 | 2000k | (vs 26) 5종 페르소나 무작위 혼합 | vsRand **+1083.9**, vsTAG **+885.2** (VIC on, 100k×5) |

> **운영 원칙**: TD는 ε-greedy / UCB 두 버전 모두 비교. MC는 ε-greedy를 본 실험으로 사용한다. 8·9의 UCB MC는 4·5절 가설(imm 제거 / 비례 배분이 안정성에 미치는 영향)을 검증하기 위한 일회성 실험이며, 이후 MC 비교는 10·11(ε-greedy)을 기준으로 한다.

> **2번째 상대(고정 rule-based) 일관성 — 정정**: 런 16~29의 정밀평가는 모두 `base.evaluate`의 **단일 고정 rule-based 정책**(`_RULE_POLICY`, 타이트-공격형 ≈ "TAG")을 2번째 상대로 쓴다. 16번과 19번(base)의 `_RULE_POLICY`가 byte-identical임을 확인했으므로, 표의 `vsRule`(16~22)과 `vsTAG`(25~29) 라벨은 **같은 상대**를 가리키며 서로 비교 가능하다(기존 "RuleBased→TAG로 바뀌어 비교 금지" 노트는 16+ 구간엔 부정확하여 정정). 단 구버전(01~15)은 다른/이전 rule-based 상대일 수 있어 직접 비교는 주의.
>
> **수치 권위 우선순위**: 16~26은 [`_reeval_100kx5/`](_reeval_100kx5/)의 **100k×5**가 권위값(기존 100k×3·200게임 체크포인트를 대체). 28(VIC ablation)·29(Pure-vs-Prop)는 각각 100k×5. **전 런 학습 seed=42 단일**(평가 회차 SD는 학습 분산이 아님).

---

## VIC ablation (= 28번 실험) — ⚠ 원본 수치·결론은 누수 인공물로 폐기(정정)

> **★정정 (실험일지 31절):** 아래 표의 원본 수치와 "인과 입증" 결론은 **폐기**되었다. credit 코드의
> total_invest==0 균등분배 폴백(누수)이 원인 — 누수 격리런(LEAKON)이 원본 −1261.8/+791.2를 완전
> 재현했고, 누수 제거(clean) 재실행에서는 **OOD 해리가 소멸**한다(VIC-on도 OOD 음수, on/off 차이 없음).
> clean 권위값: [`28_ablation_vic_2m_clean/`](28_ablation_vic_2m_clean/). 1칩 VIC는 임계 미달로 무효 —
> 유효한 것은 **pot-스케일 VIC(30번, 아래 절)**. 아래 원본 표는 *역사 기록*으로만 보존.

[`28_ablation_vic_2m/`](28_ablation_vic_2m/) — **가상 정보 비용(VIC, CHECK에 1칩 가상 투자)** 의 인과 효과를 격리하는 2×3 ablation. 학습 방식(single / cycle / mixed) × VIC(on/off)를 각각 2M 에피소드 학습 후 **100k 게임 × 5회** 평가. 요약은 [`28_ablation_vic_2m/_summary_100kx5.csv`](28_ablation_vic_2m/_summary_100kx5.csv).

> **⚠ "Random=OOD"의 기준 — 학습 상대 명시**: 28번은 **persona로 학습**한다(single=TAG / cycle·mixed=5종 혼합, `train_ablation_vic.py`). 따라서 **vs Random은 한 번도 학습하지 않은 미학습 분포(OOD)**, vs TAG는 학습 분포 내(ID)다. 해리 논증은 이 설계에 의존한다. **주의**: 기준선 라인(01~19·21a·25)은 반대로 **Random으로 학습**(ID)했고 RuleBased/TAG가 OOD였다. 즉 "Random"의 ID/OOD 역할이 라인마다 반대이므로, "Random=OOD"는 **항상 persona-학습(26~29) 맥락**에서만 성립한다.

| 방식 | VIC | vsRand mbb (SD) | vsTAG mbb (SD) | 판정 |
|---|---|---|---|---|
| single | **on** | **+987.1** (76.7) | +940.4 (16.5) | BOTH+ robust |
| single | off | **−3339.4** (143.8) | +795.9 (15.8) | vsRandom FAIL |
| cycle | **on** | **+681.3** (51.4) | +868.3 (12.1) | BOTH+ robust |
| cycle | off | **−346.5** (17.8) | +814.8 (4.4) | vsRandom FAIL |
| mixed | **on** | **+1083.9** (110.5) | +885.2 (10.9) | BOTH+ robust |
| mixed | off | **−1261.8** (22.5) | +791.2 (20.3) | vsRandom FAIL |

> ~~**핵심**: VIC를 끄면 세 방식 모두 vsRandom이 큰 적자로 붕괴(−346 ~ −3,339)하지만 vsTAG는 +791~+815로 유지된다. CHECK 흡수 고정점이 미학습 상대(Random)에 대한 일반화만 선택적으로 파괴함을 인과적으로 입증.~~ **← 폐기(누수 인공물, 상단 정정 참조).** clean 값: single on/off −375.6/−292.0 · cycle −528.9/−424.1 · mixed −399.8/−362.0 (전부 OOD 음수, 해리 없음).

## 30번 — pot-스케일 VIC (α%×팟) ★현행 핵심 라인

[`30_vic_potfrac_2m/`](30_vic_potfrac_2m/)(seed42 α-곡선) · [`30_vic_potfrac_seedsweep/`](30_vic_potfrac_seedsweep/)(α×seed sweep) — CHECK 가상 invest를 고정 1칩 대신 **α%×팟**으로(terminal=핸드 최종 팟 / checktime=체크시점 팟). 전 런 clean(누수 제거), single/TAG 학습, 2M, 100k×5 평가. 러너 [`_run_potfrac_seed.py`](../poker-pokerkit-prev/_run_potfrac_seed.py).

| 조건 (vsRand=OOD) | seed{1-5(+42)} 평균±SD | 양수 |
|---|---|---|
| off(α=0) | −318±123 | 0/6 |
| **fixed 1칩 (E7, 2026-07-06)** | **−117±252** | **2/6 — 전이구간(부호 요동)** |
| fixed 5/20/60칩 (E3) | +1230±693 / +1659±825 / +806±451 | 5/5 각 |
| terminal α=10/20/30% | +223±306 / +888±894 / +1235±406 | 4/6 · 5/6 · **6/6** |
| terminal α=35~50% | +988~+1396 (plateau) | 5/5 각 |
| **checktime α=10/20/30%** | −134±216 / +797±486 / **+1546±535** | 1/6 · 5/6 · **6/6** |

> vsTAG(ID)는 전 조건 +852~959로 평평(보존). **checktime(결정시점 팟, 미래정보 없음)이 α=30%에서 terminal과 동급 재현** → hindsight 비판 소거. α=10%에서 checktime이 약한 것은 체크시점 팟<최종 팟이라 실효 ε이 작기 때문(임계 해석과 정합).
> **야간 체인 E1~E6 결과(실험일지 33절)로 32절 미해결 4건 종결:** ① 올체크 격리(E1) → 효과 본체=CHECK credit ② 홀드아웃(E2) → "일반화" 기각·상대 의존(STA −177) ③ fixed-K(E3) → 상수 ε도 임계만 넘으면 유효(hindsight 완전 소거) ④ 메커니즘(E4) → 턴 체크 65%→소액 벳 65% 수동화 해소.
> **E7 (fixed-1칩 seed sweep, `fixed_k1_s{1-5}`, 2026-07-06):** 기존 "1칩 무효(0/1, seed42 −376)"는 **단일 seed의 오도**였음 — 6-seed 평균 −117±252·양수 2/6의 **전이구간**(s3 +275·s5 +108 양수). 용량-반응 단조성은 유지(−318 → −117 → +1230 → +1659). 논문 v3.1 전 지점 정정 반영. 로그 `_logs/night_e7{t,e}_k1_s{1-5}.log`.

## Pure-vs-Prop 통제실험 (= 29번)

[`29_pure_softmax_mixed_2m/`](29_pure_softmax_mixed_2m/) — 28번 mixed와 **100% 매칭, 기여도 배분만 PROP→PURE(표준 MC, 말단보상 γ-할인 역전파)** 단일 변경. 100k×5(eval seed 1000–1004). 요약 [`_pure_vs_prop_100kx5.log`](_pure_vs_prop_100kx5.log).

| 기여도 배분 | vsRand mbb (SD) | vsTAG mbb (SD) | 판정 |
|---|---|---|---|
| **PURE** mixed | **+12.0** (38.8) | **+76.4** (8.8) | 약·브레이크이븐 |
| **PROP** mixed VIC-on | **+1083.9** (110.5) | +885.2 (10.9) | 동시 흑자 ✅ |
| **PROP** mixed VIC-off | **−1261.8** (22.5) | +791.2 (20.3) | vsRand 붕괴(ZCA) |

> **핵심**: PURE는 ZCA가 없어도(Q(CHECK)가 ±100칩 분포) **어디서나 약함**(+12/+76). VIC의 가치 = "ZCA 제거" 자체가 아니라 **저분산 비례 기여도를 보존한 채 고정점만 해제**하는 데 있음. "표준 MC를 썼으면 됐다"는 반박을 PURE(두 지표 10~14배 약함)로 무력화.

## 100k×5 통일 재평가 ([`_reeval_100kx5/`](_reeval_100kx5/))

16~26번 중 100k×5 정밀평가가 없거나(16~18·24) 불완전하던(19·25·26 ×3) 런을 **동일 프로토콜**(100k 게임 × 5회, eval seed 1000–1004, raw greedy, 2번째 상대=고정 rule-based `_RULE_POLICY`)로 재평가해 평가 분산을 통제. 요약 [`_reeval_100kx5/_summary_reeval_100kx5.csv`](_reeval_100kx5/_summary_reeval_100kx5.csv).

주요 정정: **16/17/18 vsRule 강한 적자**(+10 등 200게임 착시 정정), **24 BOTH−**, **21a = 19 동일설정(vs Random, seed 42)이라 동일 모델**(손상 아님; 20도 19 모델의 외부평가라 같은 pkl). 22번은 pkl 미보존, 01~11은 구버전 스키마라 현 평가코드와 비호환이라 제외. **한계**: 전 런 학습 seed=42 단일이므로 회차 SD는 *평가* 분산일 뿐 *학습* 분산이 아님(hole A 미해결).

## (Softmax × VIC) 2×2 통제 — 메인 라인(Random 학습)

[`28b_softmax_novic_random_2m/`](28b_softmax_novic_random_2m/) — 19번(softmax+VIC **on**)과 **100% 매칭, `CHECK_VIRTUAL_INVEST`만 1→0**(VIC off) 단일 변경. softmax·Random학습·2M·seed42·100k×5 모두 동일. 러너 [`_run_softmax_novic_random.py`](../poker-pokerkit-prev/_run_softmax_novic_random.py).

| 탐색 | VIC | 런 | vsRand(=ID) | vsRule(=OOD) | 판정 |
|---|---|---|---|---|---|
| Softmax | **on** | 19 | +277.0 | **+112.1** | BOTH+ |
| Softmax | **off** | 28b_softmax_novic_random_2m | **+760.4** (40.1) | **−27.2** (22.6) | OOD 브레이크이븐(−), ID↑ |

> **핵심**: softmax를 켠 채 **VIC만 끄면** vsRule(이 라인의 OOD)이 +112→−27로 떨어지고 vsRandom(ID)은 +277→+760으로 오른다. ① **softmax 단독으로는 OOD 일반화를 못 만든다(=VIC가 softmax를 대체당하지 않음)**, ② VIC는 *학습상대 과적합(ID↑)을 미학습 상대 일반화(OOD↑)로 바꾸는 정규화*처럼 작동. **단 효과는 약함**(vsRule off −27.2±22.6은 0 근방) — 극적 붕괴(−346~−3339)는 persona 학습(28번)에서만. → ZCA 피해 크기는 OOD 상대 성격에 의존(다중 OOD 검증 동기).

## 각 실험 데이터의 의의

각 런의 CSV가 **무엇을 입증·반증했는가**를 정리한다. 숫자 자체보다 그 데이터가 다음 실험의 설계를 어떻게 바꿨는지가 핵심이다.

- **1번** — 베이스라인. MC + ε-decay + imm 조합이 학습 초반(약 10k ep) 정점을 찍은 뒤 무너지는 것을 처음 관측. "성능이 오르다 떨어진다"는 현상 자체를 데이터로 고정해, 이후 모든 실험의 비교 기준점이 된다.
- **2번** — 같은 골격에서 알고리즘만 TD로 바꾸면 붕괴가 사라짐을 보임. 붕괴가 환경·추상화가 아니라 **업데이트 방식(MC vs TD)** 에서 온다는 첫 단서.
- **3번** — MC에서 탐색만 ε→UCB로 교체해도 여전히 붕괴. 따라서 붕괴 원인은 **탐색이 아니다**를 입증(탐색 가설 기각).
- **4번** — imm을 제거(Pure MC)하자 붕괴가 사라짐. 붕괴의 진짜 원인이 **imm(즉시 비용 누적)** 임을 분리 입증. 연구 전체에서 가장 결정적인 한 줄 변경.
- **5번** — Pure를 비례 배분으로 바꿔도 안정적이며 vs Rule mbb가 0 근처. **보상의 대칭성**이 안정성의 열쇠라는 가설을 강화.
- **6·7번** — 같은 결론이 40k가 아니라 400k 장기 학습에서도 유지되는지 확인(TD ε vs UCB). TD에서는 ε-greedy가 UCB보다 우월(mbb 기준)함을 데이터로 확정.
- **8·9번** — UCB MC를 400k까지 끌어 4·5번 가설이 장기에서도 성립함을 재확인하는 검증용. 운영 알고리즘이 아니라 "원인 분리 장비"로서의 데이터.
- **10번** — Pure MC를 운영 탐색(ε-greedy)로 옮긴 기준선. vs Rule mbb -1,810으로 아직 적자지만 붕괴는 없음.
- **11번** — 비례 배분 + ε-greedy가 vs Rule mbb **-152, SE 44**로 break-even에 근접. **"적게 지는" 보수적 정책**이 가능함을 입증한 첫 흑자 후보. 이후 모든 확장의 베이스가 됨.
- **12·12c번** — 상태에 PrevAction을 더하자 오히려 mbb가 악화(-807, -523). 상태 차원 확장이 **셀당 방문 감소 → MC 분산 증가**라는 비용을 동반함을 데이터로 확인. 학습량을 800k로 늘려도 완전 회복 안 됨.
- **13번** — TD에 PrevAction을 더하면 maximization bias가 폭주(mbb -6,734). 확장된 상태 공간에서 **TD의 부트스트랩 편향이 MC보다 취약**함을 입증. 최종적으로 MC 라인을 선택한 근거.
- **14번** — Pure MC + ε-decay + PrevAction에서 1번과 같은 붕괴 패턴 재현. ε-decay 문제가 보상 방식과 무관하게 재현됨을 확인.
- **15번** — 14번을 1.2M까지 늘려도 ε-decay 락인이 풀리지 않음. **"Pure MC + ε-decay는 학습량으로 해결 불가"** 를 확정. Softmax 탐색으로 전환하는 직접 근거가 된 데이터.
- **16번** — CHECK=1chip(VIC) 추가. 기존엔 "vs Rule mbb **+10** 첫 양수 전환"으로 흡수 고정점 처방의 역증명으로 썼으나, **100k×5 정밀평가에서 vsRule −1,145.8(SD 28.2)로 강한 적자**임이 드러나 이 서사는 무효(+10은 200게임 체크포인트 착시). 16은 VIC-on **단독** ε-greedy/1.2M 런으로 vsRand +4,981.6 / vsRule −1,145.8 = **OOD+/ID−**의 다른 양식이며, ZCA/VIC 인과는 ablation(28번)에만 귀속한다. 16은 'VIC 원형의 정성 사례'로만 분리 표기.
- **17·18번** — 보상 형태를 binary / potnorm으로 바꾼 ablation. 둘 다 16번(prop)보다 mbb 열위(-788, -2,055). **비례 배분이 네 가지 보상 형태 중 최적**임을 비교로 입증.
- **19번** — ε-greedy를 Softmax(온도 감쇠)로 교체 + 2M 학습. 100k×3 vs Rule **+124.6**. **100k×5: vsRand +277.0 / vsRule +112.1 = BOTH+** — Random·RuleBased 둘 다 흑자인 **첫 진짜 일반화 성공**. 15번 ε-decay 한계를 Softmax가 넘어선 **최종 모델**.
- **20번** — 19번 모델을 외부 엔진(PyPokerEngine)으로 평가. HonestPlayer 100k×3 평균 **+447.0 mbb/g**. 자작 룰베이스 편향 우려를 차단하고 **외부 봇 상대로도 통계적 유의 흑자**임을 교차검증한 데이터.
- **21a/21b/21c번** — 상대 유형(Random/RuleBased/Self-play) 단독 고정 3-way ablation. **21a(Random)는 base 19와 동일 설정(vs Random, seed 42)이라 19와 동일 모델**(`eval_results.pkl` byte-identical = 결정론적 재현, 손상 아님; 20도 19 모델 외부평가라 동일 pkl). 100k×5: **21a(=19) +277/+112 · 21b(RuleBased) +350/+960 = 둘 다 BOTH+**, 21c(Self-play) +4,404/−4,609로 vsRule 극단 열세. 즉 **Random·RuleBased 단독 학습은 둘 다 일반화(vsRule+), Self-play 단독만 실패**. ⚠ 따라서 기존 "RuleBased 단독만 흑자 → 19는 RuleBased 특화 과적합" 결론은 **재검토 필요**(19는 vs Random 학습이고 21a=19도 vsRule +112 흑자, 200게임 −915는 착시). 깊은 셀(턴·리버) 도달률 분석(reachability 보정)에서 구조적 불가능 셀 45.5% 제거 후 도달률 78.8~91.2% → 커버리지 병목이 예산이 아니라 **상대 분포 쏠림**임을 정량 확인(이 부분은 유효).
- **22번** — UCB1 탐색(C=50)을 CHECK=1chip + PrevAction 구조에 적용한 스모크(200k). 커버리지 56.9% 확보했으나 UCB_C=50이 Q 스케일(±60~124) 대비 과대 → 탐색 지배 상태로 수렴 미달. vs Rand win% 단조 하락(62.5%→27.5%). **2M 연장 불필요** 판정(동일 C로 연장해도 구조 문제 미해결). 적정 UCB_C ≈ Q_max×0.1 = 10~15, 단 순수 UCB보다 **Softmax+UCB 하이브리드**가 더 근본적 해결책으로 방향 전환.
- **24번** — 19번 혼합 상대 설정을 8M까지 늘린 학습량 확장. **100k×5: vsRand −479.3(SD 0.7) / vsTAG −111.7(SD 1.3) = BOTH−**(SD 극소로 확정적). 학습량 ×4가 흑자를 보장하지 않고 오히려 안정적 적자임을 확증. (기존 "100k 미수행" 표기는 정정됨 — 평가는 수행되어 `_reeval_100kx5/`에 보관)
- **25a~25d번** — Softmax 온도 sweep(baseline/고온/완만감쇠/하한온도). 100k×5: vsRand 네 조건 모두 흑자(+278~+647), vsTAG는 **25b(고온)만 +97.2 흑자**, 25d +10.5(0과 무차별), 25a −77.7·25c −53.0 적자. 탐색 온도를 높게 유지해야 강상대(TAG)에 견딘다는 단서.
- **26a~26e번** — 단일 페르소나(LAG/Maniac/Station/Nit/TAG) 특화 학습. 100k×5: vsRand 부호 갈림(LAG −563·Station −674 적자 vs Nit +1,281·TAG +987 흑자), vsTAG는 전부 흑자. 단일상대 특화는 그 상대엔 강하나 **미학습 상대(Random) 일반화가 상대 분포에 따라 무너짐** = OOD/ID 해리를 페르소나 단위로 재확인. (26e는 100k×5에서 ablation single/on과 정확히 일치.)
- **27a/27b번** — 5종 페르소나를 순환(cycle)·혼합(mixed) 노출하여 학습. 둘 다 vsRand·vsTAG 모두 흑자(27a +681/+868, 27b +1084/+885)로, 단일 페르소나의 일반화 취약성을 다양한 상대 노출로 완화. ⚠ **이 두 런은 VIC ablation(28번)의 cycle/mixed(VIC on)과 동일 런**이므로, 27과 28을 별개 데이터로 이중 계상하지 말 것(수치 동일).
- **VIC ablation (28번)** — 위 [VIC ablation 절](#vic-ablation--28번-실험-논문-핵심) 참조. 본 연구의 인과 주장(VIC가 미학습 상대 일반화를 선택적으로 살린다)을 2×3 격리 설계 + 100k×5 평가로 입증한 **논문 핵심 데이터**.
- **Pure-vs-Prop (29번)** — 위 [Pure-vs-Prop 절](#pure-vs-prop-통제실험--29번) 참조. 28번 mixed와 100% 매칭, 기여도 배분만 PURE로 바꾼 단일변경. PURE는 어디서나 약함(+12/+76)으로 "표준 MC를 썼으면 됐다"는 반박을 무력화하고, VIC의 가치가 "저분산 기여도 보존 + 고정점 해제"임을 분리.
- **100k×5 통일 재평가** — 위 [재평가 절](#100k5-통일-재평가-_reeval_100kx5) 참조. 16~26 정밀평가 통일로 16(+10)·24(100k미수행)·21a(=19 동일설정 확인, 손상 오인 정정) 등 **문서 수치를 권위값으로 정정**한 감사 데이터.

## 폴더 내 파일

- `eval_results.csv` — 평가 시점별 메트릭
- `train_log.txt` *(400k만)* — 학습 중 표준 출력. 헤더 + 평가 줄 + 최종 Q-table
- `stderr.txt` *(400k만)* — 비어있으면 정상 종료

## 부속 자료

- [`_smoke/`](_smoke/) — 500 에피소드 사전 검증 CSV들과 Start-Process용 runner 스크립트(`_run_*.py`)
- [`_logs/`](_logs/) — 학습·평가 실행 시 남은 stdout/stderr 로그(`*.log`, `*.err`), PID 기록(`*_pids.txt`), 25/26번 부분 평가 덤프(`eval_100k_*.txt`, UTF-16). 결과 데이터가 아닌 실행 부산물이므로 분리 보관
- [`_ablation_smoke/`](_ablation_smoke/) — VIC ablation 스모크(소규모 사전 검증) 런
- [`28_ablation_vic_2m/`](28_ablation_vic_2m/) — VIC ablation(28번) 본 실험 6개 런 + `_summary_100kx5.csv`
- [`29_pure_softmax_mixed_2m/`](29_pure_softmax_mixed_2m/) — Pure-vs-Prop(29번) PURE 런
- [`_reeval_100kx5/`](_reeval_100kx5/) — 16~26번 100k×5 통일 재평가 로그 + `_summary_reeval_100kx5.csv` + `aggregate.py`
- [`28b_softmax_novic_random_2m/`](28b_softmax_novic_random_2m/) — (Softmax × VIC) 2×2 통제. 19번과 100% 매칭, VIC만 off. 메인 라인에서 "softmax≠VIC 대체" 입증
- [`_pure_vs_prop_100kx5.log`](_pure_vs_prop_100kx5.log) — 29번 PURE vs PROP(on/off) 100k×5 정밀평가 로그

## 소스 코드 매핑

| CSV 출처 | 학습 스크립트 |
|---|---|
| 01 | [`poker-pokerkit-mc/train_eval.py`](../poker-pokerkit-mc/train_eval.py) |
| 02, 07 | [`poker-pokerkit-ucb/train_eval_td.py`](../poker-pokerkit-ucb/train_eval_td.py) |
| 06 | [`poker-pokerkit/train_eval.py`](../poker-pokerkit/train_eval.py) |
| 03 | [`poker-pokerkit-ucb/train_eval_mc.py`](../poker-pokerkit-ucb/train_eval_mc.py) |
| 04, 08 | [`poker-pokerkit-ucb/train_eval_mc_pure.py`](../poker-pokerkit-ucb/train_eval_mc_pure.py) |
| 05, 09 | [`poker-pokerkit-ucb/train_eval_mc_prop.py`](../poker-pokerkit-ucb/train_eval_mc_prop.py) |
| 10 | [`poker-pokerkit-ucb/train_eval_mc_pure_eps.py`](../poker-pokerkit-ucb/train_eval_mc_pure_eps.py) |
| 11 | [`poker-pokerkit-ucb/train_eval_mc_prop_eps.py`](../poker-pokerkit-ucb/train_eval_mc_prop_eps.py) |
| 12, 12c | [`poker-pokerkit-prev/train_eval_mc_prop_eps_prev.py`](../poker-pokerkit-prev/train_eval_mc_prop_eps_prev.py) |
| 13 | [`poker-pokerkit-prev/train_eval_td_eps_prev.py`](../poker-pokerkit-prev/train_eval_td_eps_prev.py) |
| 14, 15 | [`poker-pokerkit-prev/train_eval_mc_pure_eps_prev.py`](../poker-pokerkit-prev/train_eval_mc_pure_eps_prev.py) |
| 16 | [`poker-pokerkit-prev/train_eval_mc_prop_check1_1200k.py`](../poker-pokerkit-prev/train_eval_mc_prop_check1_1200k.py) |
| 17 | [`poker-pokerkit-prev/train_eval_mc_binary_1200k.py`](../poker-pokerkit-prev/train_eval_mc_binary_1200k.py) |
| 18 | [`poker-pokerkit-prev/train_eval_mc_potnorm_1200k.py`](../poker-pokerkit-prev/train_eval_mc_potnorm_1200k.py) |
| 19 | [`poker-pokerkit-prev/train_eval_mc_prop_softmax_2000k.py`](../poker-pokerkit-prev/train_eval_mc_prop_softmax_2000k.py) |
| 20 | [`poker-pokerkit-prev/evaluate_pypokerengine.py`](../poker-pokerkit-prev/evaluate_pypokerengine.py) |
| 21a, 21b, 21c | [`poker-pokerkit-prev/train_softmax_2000k_opp.py`](../poker-pokerkit-prev/train_softmax_2000k_opp.py) |
| 22 | [`poker-pokerkit-prev/train_eval_mc_prop_ucb_smoke.py`](../poker-pokerkit-prev/train_eval_mc_prop_ucb_smoke.py) |
| 24 | [`poker-pokerkit-prev/train_softmax_8000k_mixed.py`](../poker-pokerkit-prev/train_softmax_8000k_mixed.py) |
| 25a~25d | [`poker-pokerkit-prev/train_softmax_temp_sweep.py`](../poker-pokerkit-prev/train_softmax_temp_sweep.py) |
| 26a~26e | [`poker-pokerkit-prev/train_softmax_persona_2000k.py`](../poker-pokerkit-prev/train_softmax_persona_2000k.py) |
| 27a, 27b | [`poker-pokerkit-prev/train_softmax_persona_mixed_2000k.py`](../poker-pokerkit-prev/train_softmax_persona_mixed_2000k.py) |
| VIC ablation (28) | [`poker-pokerkit-prev/train_ablation_vic.py`](../poker-pokerkit-prev/train_ablation_vic.py) |
| Pure-vs-Prop (29) | [`poker-pokerkit-prev/train_pure_softmax_ablation.py`](../poker-pokerkit-prev/train_pure_softmax_ablation.py) |
| 25~27 / VIC / reeval 평가 | [`poker-pokerkit-prev/eval_persona_100k.py`](../poker-pokerkit-prev/eval_persona_100k.py) |

자세한 분석은 [`../실험일지.md`](../실험일지.md) 참조.
