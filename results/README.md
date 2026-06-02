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
| 13 | [`13_td_eps_prev_400k`](13_td_eps_prev_400k/) | **TD(0)** ε + PrevAction | ε-greedy | bootstrap | 400k | (vs 6) +PrevAction | 완주 — TD maximization bias 폭주 (vs Rule mbb -6,734) |
| 14 | [`14_mc_pure_eps_prev_400k`](14_mc_pure_eps_prev_400k/) | MC Pure ε + PrevAction | ε-greedy | payoff only | 400k | (vs 10) +PrevAction | 완주 — Pure MC + ε-decay 붕괴 패턴 재확인 |
| 15 | [`15_mc_pure_eps_prev_1200k`](15_mc_pure_eps_prev_1200k/) | MC Pure ε + PrevAction | ε-greedy | payoff only | **1200k** | (vs 14) ×3 | 완주 — 학습량 늘려도 ε-decay 락인 지속, **Pure MC + ε-decay는 학습 불가 확정** |
| 16 | [`16_mc_prop_check1_eps_prev_1200k`](16_mc_prop_check1_eps_prev_1200k/) | MC Prop ε + PrevAction + **CHECK=1chip** | ε-greedy | payoff × invest 비율 | 1200k | (vs 12) +CHECK=1chip 가상투자, ×3 | 완주 (vs Rule mbb **+10**, vs Rand mbb +7,168) — CHECK 흡수상태 해소 |
| 17 | [`17_mc_binary_eps_prev_1200k`](17_mc_binary_eps_prev_1200k/) | MC Binary ε + PrevAction + CHECK=1chip | ε-greedy | sign(payoff) × invest 비율 | 1200k | (vs 16) 보상 prop→binary | 완주 (vs Rule mbb **-788**) — peak 크지만 최종 수익성 16번 미만 |
| 18 | [`18_mc_potnorm_eps_prev_1200k`](18_mc_potnorm_eps_prev_1200k/) | MC PotNorm ε + PrevAction + CHECK=1chip | ε-greedy | (invest / total) × (payoff / pot) | 1200k | (vs 16) 보상 prop→potnorm | 완주 (vs Rule mbb **-2,055**) — 승률은 높지만 mbb 개선 제한적 |
| 19 | [`19_mc_prop_softmax_prev_2000k`](19_mc_prop_softmax_prev_2000k/) | MC Prop Softmax + PrevAction + CHECK=1chip | **Softmax** | payoff × invest 비율 | **2000k** | (vs 16) ε→Softmax(온도감쇠), ×1.67 | 100k×3 평균 vs Rule mbb **+124.6** — 최종 모델, 유의미 흑자 |
| 20 | [`20_mc_prop_softmax_pypokerengine`](20_mc_prop_softmax_pypokerengine/) | 19번 최종 모델 vs PyPokerEngine Random/Honest | 평가 전용 | 외부 오픈소스 봇 교차검증 | 10k / 100k | (vs 19) 평가 엔진 pokerkit→PyPokerEngine | Honest 100k×3 평균 **+447.0 mbb/g**, Random 100k×3 평균 **+25.9 mbb/g** — 외부 봇 상대도 흑자 |

> **운영 원칙**: TD는 ε-greedy / UCB 두 버전 모두 비교. MC는 ε-greedy를 본 실험으로 사용한다. 8·9의 UCB MC는 4·5절 가설(imm 제거 / 비례 배분이 안정성에 미치는 영향)을 검증하기 위한 일회성 실험이며, 이후 MC 비교는 10·11(ε-greedy)을 기준으로 한다.

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
- **16번** — CHECK=1chip 가상 투자를 추가하자 vs Rule mbb가 **+10**으로 첫 양수 전환. 6절에서 진단한 **CHECK 흡수 고정점**이 실제 원인이었음을 처방으로 역증명.
- **17·18번** — 보상 형태를 binary / potnorm으로 바꾼 ablation. 둘 다 16번(prop)보다 mbb 열위(-788, -2,055). **비례 배분이 네 가지 보상 형태 중 최적**임을 비교로 입증.
- **19번** — ε-greedy를 Softmax(온도 감쇠)로 교체 + 2M 학습. 100k×3 교차 평가 평균 vs Rule mbb **+124.6**. 15번에서 확정한 ε-decay 한계를 Softmax가 넘어섬을 입증한 **최종 모델**.
- **20번** — 19번 모델을 외부 엔진(PyPokerEngine)으로 평가. HonestPlayer 100k×3 평균 **+447.0 mbb/g**. 자작 룰베이스 편향 우려를 차단하고 **외부 봇 상대로도 통계적 유의 흑자**임을 교차검증한 데이터.

## 폴더 내 파일

- `eval_results.csv` — 평가 시점별 메트릭
- `train_log.txt` *(400k만)* — 학습 중 표준 출력. 헤더 + 평가 줄 + 최종 Q-table
- `stderr.txt` *(400k만)* — 비어있으면 정상 종료

## 부속 자료

- [`_smoke/`](_smoke/) — 500 에피소드 사전 검증 CSV들과 Start-Process용 runner 스크립트(`_run_*.py`)

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

자세한 분석은 [`../실험일지.md`](../실험일지.md) 참조.
