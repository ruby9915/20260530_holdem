# 선행연구 검증 기록 (Claude 직접 원문 대조)

검증일: 2026-06-03 · 검증자: Claude(웹 원문 직접 조회) · 대상: Gemini 딥리서치 보고서(`RL 연구 선행 연구 조사.md`)의 사실 확인

> **도구 한계 명시.** Claude에는 Gemini Deep Research 같은 전용 자동 웹 딥리서치 에이전트가 없다. 이 기록은 **arXiv·Google Scholar 원문을 건별로 직접 가져와(fetch) 대조**한 수동 검증이다. 따라서 "전수 탐색"이 아니라 **"핵심 근접 후보의 실재·내용 검증"**이다. 망라성은 Gemini 보고서 §8 한계와 동일하게 제한적.

---

## 1. 검증 요약 (한눈에)

| 항목 | Gemini 보고서 주장 | Claude 원문 검증 | 판정 |
|---|---|---|---|
| Kujur 2026 (16312) | 실재, self-play 적대적 행동 제거 | **실재 확인**, 초록 일치 | ✅ |
| Kujur 2026 (16315) 자매논문 | 표에 등장(threshold/collapse) | **실재 확인**, "fixed-opponent control" 명시 | ✅ (중요) |
| DAGS (14379) | "Rudolph et al. 2025", HUNL, 인간 데이터 | **저자·연도·도메인 오류** | ❌ 정정 |
| Xie coverage (2210.04157) | "Xie 2023" | 실재, 단 **2022** 제출(126 cites) | ⚠️ 연도 |
| 큰 결론 "정확히 일치 선례 없음(NO)" | 단정 | 타당하나 톤 과함 → "to our knowledge" | ⚠️ 톤 |

---

## 2. 원문 검증 상세

### 2.1 Kujur, arXiv:2605.16312 — "When Actions Disappear" ✅
- **제출 2026-05-04, Arahan Kujur.** 초록 직접 확인.
- 내용: self-play에서 공격자가 victim의 합법 행동을 선택적으로 **제거(masking)**. 포커 6~5,531 정보상태 + 비포커 2개. Q-learning/PPO/NFSP/DQN에서 통함. 지표 **reach-weighted contingent action capacity (CAC_w/CAC_v)**.
- **귀하와 차이**: 능동적 적대 공격자 존재(귀하는 고정·비학습) / 측정은 신경망 추정(귀하는 256셀 exact 전수) / 함수근사 포함(귀하는 순수 tabular).

### 2.2 Kujur, arXiv:2605.16315 — "A Structural Threshold in Decision Capacity..." ✅ (가장 위험)
- **제출 2026-05-04(같은 날), Arahan Kujur. 16312의 자매 논문.** 초록 직접 확인.
- 초록 핵심: "eliminating all positive-reach contingent decisions causes rapid convergence to a deterministic exploitation attractor... **A frozen baseline and fixed-opponent control confirm that the mechanism is co-adaptation under constraint, not the perturbation itself.**"
- → **고정 상대를 직접 통제군으로 사용**. 귀하 세팅과 가장 가까운 단일 문장.
- **그래도 차이 유지**: (a) fixed-opponent는 *공격 효과를 분리하는 보조 통제군*일 뿐, 주제는 적대적 rule perturbation; (b) 지표는 CAC_w(행동 용량)이지 $d^\pi(s)$ 셀 단위 전수 coverage 천장이 아님; (c) 함수근사 하에서 오히려 심화("intensifies under function approximation"), 귀하는 순수 tabular exact.
- **조치**: Related Work에 16312·16315 **두 편 함께** 인용 + 차별점 명시(리뷰어가 둘 다 들고 옴).

### 2.3 DAGS, arXiv:2605.14379 ❌ → 정정
- Gemini 보고서: "Rudolph et al. 2025, HUNL, 오프라인 인간 플레이 데이터".
- **원문 사실**: 저자 **JB Lanier, Nathan Monette, Pierre Baldi, Roy Fox**, 제출 **2026-05-14**. 도메인 **Kuhn Poker·Goofspiel + counterexample game**(HUNL 아님), 데이터는 **synthetic datasets**(인간 데이터는 *가정상의 동기*). 목적: regularized policy gradient의 탐색 가속(시작상태 샘플링) → exploitability 감소.
- → Gemini 보고서의 저자/연도/도메인 모두 부정확. **그대로 인용 금지.** 다만 "도달 어려운 상태 진입"이라는 reachability 인식은 인접하므로 인용 시 *정정된 서지정보*로.

### 2.4 Xie et al., arXiv:2210.04157 — "The Role of Coverage in Online RL" ⚠️
- 실재 확인(Scholar, 126회 인용). 저자 Xie, Foster, Bai, Jiang, Kakade.
- **제출 2022**(보고서의 "2023"은 학회 게재연도 혼동). 본 프로젝트 문서는 **Xie 2022로 통일**.

### 2.5 추가 발견(인접 후보) — Durugkar 2023
- "Estimation and control of visitation distributions for reinforcement learning" (UT Austin 학위논문). "for a fixed agent policy π, transition visitation..."를 다룸.
- 인접점: visitation distribution을 **측정·통제** 대상으로 본다. **차이**: 고정 *상대*가 coverage 천장을 강제한다는 구도가 아니라, 일반 RL에서 visitation을 추정/제어하는 방법론. exact 256셀 포커 세팅 아님.

---

## 3. "정확히 일치하는 조합" 판정 (정직)

- 직접 검증한 핵심 근접 논문(Kujur 16312/16315, DAGS, Xie, Durugkar) **모두 귀하 조합과 어긋난다**: 고정·비학습 상대 + 순수 tabular 256셀 exact 전수 $d^\pi(s)$ + "예산·탐색·커버리지 3종 처방을 차례 반증" 의 **동시 충족**은 미발견.
- **단, "단 한 편도 없다(NO)"로 단정하지 않는다.** 수동 검증의 망라성 한계 + Gemini §8 한계(초기 추상화 문헌의 용어 차이 / 동시기 미공개 / 도메인명 없는 순수 이론)로, **"to our knowledge, 보고된 바 없음" + 차별점 표**가 정직한 최종 표현.

## 4. 후속 조치 체크리스트
- [ ] Related Work에 Kujur **16312 + 16315** 동시 인용, CAC_w vs $d^\pi(s)$ exact 차이 명시.
- [ ] DAGS 인용 시 서지정보 **Lanier et al. 2026, Kuhn/Goofspiel**로 정정(HUNL 아님 표기).
- [ ] coverage 이론 연도 **Xie 2022**로 통일.
- [ ] 논문 본문에 "최초/유일" 금지, **to our knowledge** 표현 유지.

---

## 부록: 검증에 사용한 1차 출처(직접 fetch)
- https://arxiv.org/abs/2605.16312 (Kujur, When Actions Disappear)
- https://arxiv.org/abs/2605.16315 (Kujur, Structural Threshold in Decision Capacity)
- https://arxiv.org/abs/2605.14379 (Lanier et al., DAGS)
- https://arxiv.org/abs/2210.04157 (Xie et al., Role of Coverage)
- Google Scholar 검색(visitation/coverage/fixed opponent) — Durugkar 2023 등 인접 후보 식별
