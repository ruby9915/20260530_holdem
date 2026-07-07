# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 따르는 프로젝트 지침이다. 매 세션 자동 로드된다.

## ⚠ 최우선: `저자지시.md` (에이전트 수정 금지)

루트의 [저자지시.md](저자지시.md)는 **저자가 직접 관리하는 최우선 지시 파일**이다. 에이전트는 세션 시작 시와 방향이 걸린 결정 전에 이 파일을 먼저 읽고 따르되, **절대 수정하지 않는다** (편집·정리·형식 통일 포함 전부 금지). 이 파일과 CLAUDE.md를 포함한 다른 문서가 충돌하면 저자지시.md가 우선한다.

## 프로젝트 한 줄 요약

헤즈업(1대1) 노리밋 텍사스 홀덤을 **Tabular Q-learning**으로 학습시키는 연구. 목표는 "강한 봇"이 아니라 **무엇이 학습 안정성·분포 강건성(OOD 일반화)을 결정하는가**를 단일변수 통제실험으로 규명하는 것. 결과는 JKSCI 논문으로 작성 중.

## 핵심 발견 (논문 주장)

- **ZCA (Zero-Credit Absorption)**: 비례배분(PROP) 기여도에서 비용 0인 CHECK는 credit≈0 → Q(CHECK)가 ±1.4칩 면도날 띠로 붕괴(영-고정점). 이 0이 음수 행동을 greedy로 흡수.
- **VIC (Virtual Information Cost)**: CHECK에 1칩 가상 투자를 부여해 **0-고정점의 흡수(argmax 지배)를 해소**(Q(CHECK)는 0 근방 유지·미세 음 이동; VIC-on도 pinned~99%, dominance만 25%→8%). 진짜 미학습 행동의 0(탐색 가치)은 보존. **VIC는 미학습 상대(Random=OOD) 일반화의 필요조건**(단 학습 seed=1 한계 — [[남은-과제-seed-sweep]]).
- **OOD/ID 해리**: VIC를 끄면 vs Random(OOD)만 선택적으로 붕괴(−346~−3,339)하고 vs TAG(ID)는 +로 유지(부호반전). 이것이 핵심 진단 기여.
- **Pure-vs-Prop**: 표준 MC(PURE)로 ZCA를 우회하면 어디서나 약함(+12/+76). VIC는 "저분산 비례 기여도를 보존한 채 흡수만 해소"하는 데 가치가 있음.

## 코드 구조

현재 메인 작업 코드는 **`poker-pokerkit-prev/`** (PrevAction 상태 확장 + softmax + 2M 에피소드). 구버전 폴더(`poker-pokerkit`, `-mc`, `-ucb`)는 초기 비교실험용이며 pkl 스키마가 달라 현 평가 코드와 호환 안 됨.

| 파일 | 역할 |
|---|---|
| `poker-pokerkit-prev/abstraction.py` | PokerKit state → (Round4 × Position2 × State8 × Action8) 변환. PrevAction 확장 시 셀 2,048개 |
| `poker-pokerkit-prev/qlearning.py` | Q-table 클래스. `update_q`(TD), `update_mc`(MC 역전파) |
| `poker-pokerkit-prev/rulebased_personas.py` | 평가/학습 상대 페르소나 (TAG/LAG/Maniac/Station/Nit) |
| `poker-pokerkit-prev/train_eval_mc_prop_softmax_2000k.py` | **19번 = base 모듈**. 다른 train 스크립트가 `import ... as base`로 재사용 |
| `poker-pokerkit-prev/train_ablation_vic.py` | VIC ablation 본 실험 (논문 핵심) |
| `poker-pokerkit-prev/train_pure_softmax_ablation.py` | Pure-vs-Prop 통제실험 (29번) |
| `poker-pokerkit-prev/eval_persona_100k.py` | 100k×N 정밀 평가 |
| `poker-pokerkit-prev/analyze_qcheck.py` | Q(CHECK) ZCA 지문 진단기 |

## 문서 (작업 전 반드시 참조)

- `실험일지.md` — 1~29번 실험 시간순 일지 + 설계 분석 (가장 상세, 2,195줄)
- `results/README.md` — 실험 인덱스 표. 각 런이 무엇을 입증/반증했는지 + 소스코드 매핑
- `results/<NN>_*/eval_results.csv` — 런별 평가 메트릭. 400k+ 런은 `train_log.txt`도 보관
- `results/28_ablation_vic_2m/_summary_100kx5.csv` — VIC ablation 요약 (논문 핵심 데이터)

## 운영 원칙 (이 연구의 방법론 — 반드시 지킬 것)

1. **한 번에 한 변수만 변경.** 알고리즘/탐색/보상신호/상태차원/학습량 중 하나만 바꾸고 효과 측정. 새 실험은 직전 베이스라인 대비 Δ를 명시.
2. **실험 추가 시 두 곳 모두 갱신**: `results/README.md` 인덱스 표 + `실험일지.md` 일지. 인덱스와 일지가 어긋나면 안 됨.
3. **결론은 100k×5 정밀 평가에서만 신뢰.** 200게임 체크포인트 평가는 vs Random에서 잡음 지배 → 부호반전 흔함. vs Random 주장은 100k×5에서만.
4. **평가 지표 주의**: 25번 이후 2번째 상대가 RuleBased→TAG로 바뀜. `vsTAG` 컬럼을 11~22번 `vsRule`과 직접 비교 금지.
5. **정직성 우선.** 일지에 "방어 가능한 주장"과 "남은 구멍"을 Tier로 구분해 기록하는 관행 유지. 데이터가 약하면 약하다고 적는다. 결과를 과장하지 않는다.
6. **학습 seed.** 28·29번이 seed=42 단일 학습이라는 한계(가장 큰 구멍) 인지. 새 주장 시 학습 seed sweep 고려.
7. **보수적으로 사고한다.** 결과를 낙관적으로 바라보지 않는다. 데이터가 주장을 지지하는지 의심하는 쪽에서 출발하고, 가장 약한 고리·반례·대안가설을 먼저 찾는다. 흑자·개선·성공을 확정 전제로 깔지 말고, "이 수치가 틀렸거나 운이라면?"을 항상 먼저 따진다.

## 문서 작성 문체 (KCI/KSCI 한국 학계 기준)

이 프로젝트의 모든 한국어 문서(논문 초안, `실험일지.md`, `results/README.md`, 보고서)는 **KCI/KSCI 등재지 수준의 한국 학술 문체**로 쓴다. 영어 외래어를 음차(transliteration)로 옮긴 어휘 대신, 한국 학계에서 실제로 통용되는 번역어를 쓴다.

- **원칙**: 한국어 정착 번역어가 있으면 그것을 쓴다. 음차 표기(스킴, 셋업, 케이스 등)는 지양.
- **예외**: 번역 시 의미가 훼손되거나 학계에서 원어 그대로 통용되는 용어는 원어 유지 — Monte Carlo, softmax, bootstrap, payoff, mbb/g, Q-learning, ablation, ZCA·VIC 같은 약어·고유 알고리즘명.

| 지양 (음차) | 지향 (학술 번역어) |
|---|---|
| 스킴(scheme) | 방식, 체계, 기법 |
| 셋업(setup) | 설정, 구성 |
| 케이스(case) | 경우, 사례 |
| 노이즈(noise) | 잡음 |
| 로버스트(robust) | 강건한 / 강건성 |
| 컨버전스 | 수렴 |
| 트레이드오프 | 절충, 상충 관계 |
| 디스소시에이션 | 해리 |
| 베이스라인 | 기준선 |
| 리워드 | 보상 |

판단이 애매하면 동일 분야(강화학습·기계학습) 국내 논문에서 쓰는 표기를 따른다. 이미 `실험일지.md`가 쓰는 어휘(기여도 배분, 분포 강건성, 고정점, 흡수상태, 일반화, 정형화)를 일관 기준으로 삼는다.

### KCI 강화학습 논문 어휘 조사 반영 (2026-06-26 확정)

KCI 등재지 RL 논문 84검색 근거로 확정한 표기. **비표준·혼동 표기 → 학술 표준어**:

| 지양 (비표준/혼동) | 지향 (학술 표준어) | 근거 |
|---|---|---|
| 진짜값 / 진짜 가치 | **참값 / 참 가치** | 비표준 구어체 → 통계·RL 학술어 |
| 기대값 | **기댓값** | 사이시옷 표준어(국립국어원), 어문 규범 |
| 음성 결과 | **부정적 결과** | '음성'은 의학 진단검사(양성/음성) 차용어 오해 |
| 보상 정형화 | **보상 형성** (reward shaping) | '정형화'=formalization 혼동 (단 *기여도 정형화*의 '정형화'는 유지) |
| optimistic initialization (한국어 본문) | **낙관적 초기화** | 정착 번역어; 첫 등장 시 원어 병기 |
| 불편(이지만) 단독 | **편향이 없는** 또는 불편추정량 | '불편(uncomfortable)' 동음어 모호성 |

**유지 확정**(현행이 정확 — 바꾸지 말 것): 몬테카를로 **제어**(control problem; '통제' 아님), **통제실험/통제비교**(단일변수 통제; '대조'는 대조군 오해), **결정 상태**(MDP 상태; '결정 노드' 아님), 고정점·흡수·일반화·진단·사례연구·재현성·수렴. **greedy**는 원어 유지(용어집 합의; '탐욕적 정책' 아님).

**포커 hand = "핸드"** (음차 지양 원칙의 도메인 예외, 에이전트·에피소드와 동급). **"손"으로 번역 금지** — 신체 hand·손상(damage)·손실(loss)과 형태가 겹쳐 "전부 체크한 손" 같은 표현이 헷갈림(사용자 교정). "한 손"→"한 핸드", "손마다"→"핸드마다". 단 손상·손실 등 비-핸드 의미의 '손'은 유지.

**용어집 의도적 선택 유지**: credit assignment = **기여도 배분**(국내는 '신용/신뢰 할당'으로 양분되나 정착 표준어 부재 + PROP 맥락엔 '기여도 배분'이 더 정확), proportional credit = **비례배분**. 이중언어 초록이 영어 원어를 제공하므로 한국어 병기는 불필요.

## 환경 / 실행

- **OS**: Windows 11, 셸은 **PowerShell** (`&&` 체이닝 불가 — `;`나 `if ($?)` 사용)
- Python 3.13, 가상환경 `.venv` (pokerkit, treys, pypokerengine 설치됨)
- 활성화: `& c:\code\minimizing\.venv\Scripts\Activate.ps1`
- 학습 실행 예: `cd poker-pokerkit-prev; python train_ablation_vic.py`
- 장시간 학습(2M+ 에피소드 ≈ 10분+)은 백그라운드 실행 권장
- 의존성: pokerkit(게임 엔진), treys(포스트플랍 핸드평가), pypokerengine(외부 봇 교차검증)

## 용어집

- **PROP / PURE**: 비례배분 기여도(invest 비율×payoff) / 표준 MC(말단보상 γ-할인 역전파)
- **VIC**: CHECK에 1칩 가상 투자 (`CHECK_VIRTUAL_INVEST`)
- **ZCA**: Zero-Credit Absorption — 비용 0 행동의 0-credit이 argmax를 흡수하는 병리
- **OOD/ID**: 미학습 분포(Out-of-distribution, 예: Random) / 학습 분포 내(In-distribution, 예: TAG)
- **mbb/g**: payoff × 1000 / BIG_BLIND(=2) = payoff × 500. 평가 기본 단위
- **페르소나**: TAG(타이트-공격), LAG(루즈-공격), Maniac, Station(콜링스테이션), Nit(초타이트)
