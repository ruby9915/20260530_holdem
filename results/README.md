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

| # | 폴더 | 모델 | 탐색 | 보상 신호 | 에피소드 | 결과 요약 |
|---|---|---|---|---|---|---|
| 1 | [`01_mc_eps_imm_40k`](01_mc_eps_imm_40k/) | MC | ε-greedy | terminal + imm | 40k | 정책 붕괴 (vs Rand 32%) |
| 2 | [`02_td_ucb_40k`](02_td_ucb_40k/) | TD(0) | UCB1 | step reward | 40k | 안정 (vs Rand 75%) |
| 3 | [`03_mc_ucb_imm_40k`](03_mc_ucb_imm_40k/) | MC | UCB1 | terminal + imm | 40k | 붕괴 (vs Rand 36%) |
| 4 | [`04_mc_pure_40k`](04_mc_pure_40k/) | MC | UCB1 (가설검증용) | payoff only | 40k | 안정 (vs Rand 80%) |
| 5 | [`05_mc_prop_40k`](05_mc_prop_40k/) | MC | UCB1 (가설검증용) | payoff × invest 비율 | 40k | mbb 안정 (vs Rule mbb≈0) |
| 6 | [`06_td_eps_400k`](06_td_eps_400k/) | TD(0) | ε-greedy | step reward | 400k | 완주 (vs Rand 79.5%, vs Rule mbb -3,823) |
| 7 | [`07_td_ucb_400k`](07_td_ucb_400k/) | TD(0) | UCB1 | step reward | 400k | 완주 (vs Rand 71%, vs Rule mbb -4,953) |
| 8 | [`08_mc_pure_400k`](08_mc_pure_400k/) | MC | UCB1 (가설검증용) | payoff only | 400k | 완주 — 가설 검증용으로만 |
| 9 | [`09_mc_prop_400k`](09_mc_prop_400k/) | MC | UCB1 (가설검증용) | payoff × invest 비율 | 400k | 완주 — 가설 검증용으로만 |
| 10 | [`10_mc_pure_eps_400k`](10_mc_pure_eps_400k/) | MC | **ε-greedy** | payoff only | 400k | 완주 (vs Rule mbb -1,810) |
| 11 | [`11_mc_prop_eps_400k`](11_mc_prop_eps_400k/) | MC | **ε-greedy** | payoff × invest 비율 | 400k | 완주 (vs Rule mbb **-152**, SE=44) |
| 12 | [`12_mc_prop_eps_prev_400k`](12_mc_prop_eps_prev_400k/) | MC Prop ε + **PrevAction** | ε-greedy | payoff × invest 비율 | 400k | 완주 (vs Rule mbb -807) |
| 12c | [`12c_mc_prop_eps_prev_800k`](12c_mc_prop_eps_prev_800k/) | MC Prop ε + PrevAction | ε-greedy | payoff × invest 비율 | **800k** | SE 검증용 연장 (vs Rule mbb -523) |
| 13 | [`13_td_eps_prev_400k`](13_td_eps_prev_400k/) | **TD(0)** ε + PrevAction | ε-greedy | bootstrap | 400k | 완주 — TD maximization bias 폭주 (vs Rule mbb -6,734) |

> **운영 원칙**: TD는 ε-greedy / UCB 두 버전 모두 비교. MC는 ε-greedy를 본 실험으로 사용한다. 8·9의 UCB MC는 4·5절 가설(imm 제거 / 비례 배분이 안정성에 미치는 영향)을 검증하기 위한 일회성 실험이며, 이후 MC 비교는 10·11(ε-greedy)을 기준으로 한다.

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

자세한 분석은 [`../실험일지.md`](../실험일지.md) 참조.
