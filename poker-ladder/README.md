# poker-ladder — 강건성 사다리 신규 코드 (35절 사전등록 + 개정 v2)

> **원칙: 과거는 동결, 신규는 분리.** `poker-pokerkit-prev/`는 읽기 전용 아카이브.
> 이 폴더는 레거시를 import 하지 않는다 — 필요 로직은 복사 후 0단 등가성으로 검증.
> 실험 = 설정 조합(`train.py` CLI). 스크립트 사본·monkey-patch·플래그 누적 금지.

## 구조

| 파일 | 역할 | 사다리에서 |
|---|---|---|
| `defs.py` | Round/Position/PrevAction + 분류기 | 불변 |
| `actions.py` | 행동축 A8 (2단에서 A12 추가 예정) | 2단 변수 |
| `cards.py` | 카드축: legacy8(동결) / EHS-K (JSON 경계 + canonical 캐시) | 1·3단 변수 |
| `personas.py` | 상대 5종 + 평가상대(random/EVAL_TAG) — **legacy8 고정** | 불변 (5단에서 CFR+ 추가) |
| `qtable.py` | 차원 파라미터화 Q-테이블 | 불변 |
| `game.py` | 에피소드 루프 + credit(PROP/PURE) + VIC(off/fixed/checktime), 전 조건 clean | 불변 |
| `train.py` | 단일 러너 (config.json 기록) | — |
| `evaluate.py` | 100k×5 정밀 평가 (BASE_SEED=1000) | — |
| `tests/` | 불변식 (ZCA Q(CHECK)==0 등) | — |
| `data/` | E[HS] 버킷 경계 JSON + 생성기 | — |

## 상대는 legacy8 동결 (단일변수의 핵심)

페르소나·평가상대는 자기 결정에 **레거시 8버킷**을 쓴다. 학습자 카드축(K)을 바꿔도
상대 행동 분포는 불변 — 그래야 Δ가 학습자 추상화 효과로 귀속된다.
학습 TAG(라운드 공통)와 평가 TAG(라운드별)는 레거시 그대로 서로 다른 정책.

## 실행 예

```powershell
# 0단 등가성 (K=8 레거시 축, 새 코드): off / chec_a30 × seed
python train.py --out ../results/32_ehs_k20/rung0/off_s1 --card legacy8 --credit prop --vic off --seed 1
python train.py --out ../results/32_ehs_k20/rung0/chec_a30_s1 --card legacy8 --credit prop --vic checktime --vic-amount 0.30 --seed 1
# 1단 (K=20)
python train.py --out ../results/32_ehs_k20/k20/off_s1 --card ehs20 --credit prop --vic off --seed 1
# 정밀 평가
python evaluate.py ../results/32_ehs_k20/rung0/off_s1
```

## 0단 통과 기준 (새 코드 ↔ 레거시 등가성, 통계적)

RNG 호출 순서가 달라 bit-exact 비교는 불가 — **분리 패턴의 재현**으로 판정:
off 5seed vsRand 전패(0/5) ∧ chec_a30 5seed 전승(5/5) ∧ vsTAG 양쪽 +800~950대
(레거시 권위값: off −318±123 (0/6) / chec_a30 +1546±535 (6/6)).
통과 후에만 1단(K=20) 착수. 상세 판정 규약: 실험일지 35절.
