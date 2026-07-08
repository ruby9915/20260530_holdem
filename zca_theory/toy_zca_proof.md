# ZCA 영-고정점의 형식적 특성화 — toy MDP 증명

> 목적: "비례배분(proportional) 기여도 배분 하에서 비용 0 행동의 MC 고정점은 참값이 아니라 0이고,
> 이 0이 열등 행동을 greedy 정책에서 *영구히* 흡수한다(ZCA). 이는 낙관적 초기화의
> *일시적* 흡수와 질적으로 구별되며, 가상비용(VIC)이 임계 이상이면 이를 해소한다"를 *최소 모델*에서
> 수식으로 증명하고 수치로 검증한다. 검증 스크립트: [`verify_toy_zca.py`](verify_toy_zca.py).

본 문서의 주장은 *고정점(분석적 사실)*에 대한 것으로, 학습 seed·평가 표본과 무관하다(2,048셀 실험의
seed 분산은 *OOD 일반화 성능*의 성질이지 본 고정점의 성질이 아니다).

---

## 1. Toy MDP

결정 상태 $s$ 에서 행동 $a_1 \in \mathcal{A}(s)$ 를 한 번 선택한다. 각 행동은 **투자액** $\mathrm{inv}(a_1)\ge 0$ 을 가지며,
비용 0 행동(이하 **CHECK**)은 $\mathrm{inv}(\text{CHECK})=0$ 이다. 선택 후 궤적은 **투자액 $c>0$ 인 후속 행동을
적어도 하나 포함**하고(예: 강제 BET₂, $\mathrm{inv}=c$), 종단 보상 $P$ 로 끝난다. 할인 $\gamma=1$, 보상은 종단에서만 발생.

행동 $a_1$ 분기의 종단 보상 평균을 $\mu_{a_1} := \mathbb{E}[P \mid a_1] $ 로 둔다. 종단 보상만 있으므로
$a_1$ 의 **참값**은 $q^\*(s,a_1)=\mu_{a_1}$. 에피소드 총투자액은 $I = \mathrm{inv}(a_1) + c$ (toy에서 $c$ 고정).

---

## 2. 기여도 배분 (세 방식)

$a_1$ 에 배분되는 return $R(s,a_1)$:

| 방식 | $R(s,a_1)$ |
|---|---|
| **표준 MC** | $P$ (종단보상 그대로) |
| **비례배분(PROP)** | $\dfrac{\mathrm{inv}(a_1)}{I}\,P = \dfrac{\mathrm{inv}(a_1)}{\mathrm{inv}(a_1)+c}\,P$ |
| **VIC** | PROP과 동일하되 $\mathrm{inv}(\text{CHECK}) \leftarrow \varepsilon>0$ (가상 투자) |

MC 업데이트 $Q \leftarrow Q + \alpha\,(R-Q)$ 의 고정점은 $Q(s,a_1)=\mathbb{E}[R(s,a_1)]$.

> *각주(엄밀성).* 이 고정점 등식은 sample-average 또는 감소하는 $\alpha$ 의 *기대업데이트* 고정점이다.
> 상수 $\alpha$ 면 $Q$ 는 평균 둘레의 분포로 수렴하나 그 평균은 $\mathbb{E}[R]$ 로 유지된다. 특히 CHECK는
> $R\equiv 0$ (분산 0)이라 상수 $\alpha$ 에서도 *정확히* 0 — 결론은 $\alpha$ 방식과 무관.

---

## 3. Lemma 1 (표준 MC — 일치성)

표준 MC에서 $Q_{\text{std}}(s,a_1) \to \mathbb{E}[P\mid a_1] = \mu_{a_1} = q^\*(s,a_1)$.

*증명.* $R=P$ 이므로 고정점은 $\mathbb{E}[P\mid a_1]=\mu_{a_1}$. ∎

> 즉 표준 MC는 모든 행동의 Q를 **참값**으로 수렴시킨다.

---

## 4. Lemma 2 (비례배분 — 비용 0 행동의 영-고정점)

비례배분에서, 임의의 행동 $a_1$ 에 대해
$$Q_{\text{prop}}(s,a_1) = \frac{\mathrm{inv}(a_1)}{\mathrm{inv}(a_1)+c}\,\mu_{a_1}.$$
특히 **CHECK**($\mathrm{inv}=0$)는
$$\boxed{\,Q_{\text{prop}}(s,\text{CHECK}) = \frac{0}{0+c}\,\mu_{\text{CHECK}} = 0\quad(\forall\, \mu_{\text{CHECK}}).\,}$$

*증명.* $\mathbb{E}[R]=\frac{\mathrm{inv}(a_1)}{\mathrm{inv}(a_1)+c}\mathbb{E}[P\mid a_1]$. CHECK는 분자 0. ∎

> **핵심**: CHECK의 고정점은 참값 $\mu_{\text{CHECK}}$ 과 **무관하게 0** 이다 — 구조적 편향. 방문 횟수와
> 무관하며($R\equiv 0$ 이라 아무리 업데이트해도 0), 이는 *초기화 잔재가 아니라 매 에피소드 재고정되는
> 고정점*이다. 비용>0 행동은 $\mu_{a_1}$ 을 $\frac{\mathrm{inv}}{\mathrm{inv}+c}<1$ 로 *수축*하되 **부호는 보존**한다.

---

## 5. Theorem (흡수 — 영-고정점이 열등 행동을 greedy에서 지배)

CHECK와 BET($\mathrm{inv}=b>0$)이 있고
$$q^\*(s,\text{CHECK})=\mu_C \;<\; \mu_B=q^\*(s,\text{BET}) \quad\text{(BET이 진짜로 더 좋음)},\qquad \mu_B<0\;\text{(BET도 −EV)}$$
이면, 비례배분 greedy는 **열등한 CHECK를 선택**한다. 표준 MC greedy는 **최적 BET을 선택**한다.

*증명.*
- 비례배분: $Q_{\text{prop}}(\text{CHECK})=0$ (Lemma 2), $Q_{\text{prop}}(\text{BET})=\frac{b}{b+c}\mu_B<0$ ($\mu_B<0$).
  따라서 $Q_{\text{prop}}(\text{CHECK})=0 > Q_{\text{prop}}(\text{BET})$ → CHECK 선택. 그러나 $\mu_C<\mu_B$ 이므로 **열등**.
- 표준 MC: $Q_{\text{std}}=\mu$ (Lemma 1)이므로 $\mu_C<\mu_B$ → BET 선택 → **최적**. ∎

> **일반화**: $\mu_a<0$ 인 *모든* 행동 $a$ 는 CHECK의 구조적 0 에 지배된다. 흡수 오류 조건:
> $\exists\,a:\ q^\*(s,a)>q^\*(s,\text{CHECK})\ \wedge\ \mu_a<0$ (CHECK보다 나으나 −EV인 행동의 존재).

> **흡수의 scope — ★정정 (2026-07-03, V1).** 이전 판은 "어떤 행동이라도 +EV면 무해"라 적었으나 이는
> **Lemma 2 자신과 모순**된다(Lemma 2는 $\forall\mu_C$, 부호 무관). 거울상 모드가 존재한다:
>
> **Theorem′ (거울상 — +EV 체크 은폐).** $\mu_C>\mu_B>0$ (CHECK가 참-최선, BET도 +EV)이면 비례배분
> greedy는 $Q_{\text{prop}}(\text{CHECK})=0<\frac{b}{b+c}\mu_B$ 라 **열등한 +EV BET을 선택**한다(참-최선
> 체크가 0에 눌려 은폐됨 — 트랩·팟컨트롤 라인의 상실). VIC 복원 임계는 흡수 모드와 **동형**:
> $\varepsilon>\varepsilon_{\min}=\frac{kc}{1-k}$, $k=\frac{b}{b+c}\frac{\mu_B}{\mu_C}\in(0,1)$.
> 수치 검증 [`verify_toy_mirror.py`](verify_toy_mirror.py) ($\mu_C{=}{+}5,\mu_B{=}{+}1$: $\varepsilon_{\min}=0.111$ 일치).
>
> 따라서 정확한 진술은: **ZCA는 CHECK의 참값이 0이 아닌 모든 노드에서 순위를 왜곡하는 *양방향
> 오순위*다** — $\mu_C<0$ 쪽에선 나쁜 체크의 과대평가(흡수·Theorem), $\mu_C>0$ 쪽에선 좋은 체크의
> 과소평가(은폐·Theorem′). 무해한 것은 $\mu_C\approx 0$ 근방뿐.
>
> **(가설 · 미검증) OOD 선택성과의 연결.** 2,048셀 실험에서 VIC-off가 *미학습(OOD) 상대에서만* 붕괴한 것을
> 위 scope와 잇고 싶은 유혹이 있으나, 본 toy는 그 연결을 *증명하지 않는다*. 한 가지 그럴듯한 가설은
> "ZCA → 체계적 수동화(열등 CHECK 흡수) → 착취 가능한 약상대를 공격하지 않아 +EV 포기"이다(단순히
> "OOD에선 모든 노드가 −EV"라는 설명은 약상대 상대 +EV 기회가 많다는 점에서 의심스럽다). 어느 쪽이든
> **고정점 사실(seed·표본 무관)과 OOD 성능 인과(seed 의존·미검증)는 별개 층위**이며, 후자는 실제 MDP
> seed-sweep 통제비교의 몫이다([[남은-과제-seed-sweep]]).

---

## 6. Proposition (낙관적 초기화와의 구분)

$Q$ 를 0으로 초기화한 표준 MC를 생각하자. 학습 *중*에는 미방문 행동이 0(낙관적)이라 greedy가 음수 행동
위로 0을 선호할 수 있으나(일시적 탐색), 충분한 방문 후 $Q\to\mu$ (Lemma 1)이므로 그 0-선호는 **소거**되고
최적 행동이 선택된다. 즉 낙관적 초기화의 흡수는 *수렴 전 일시적*이고 **고정점은 참값**이다.

대조적으로 비례배분에서 $Q_{\text{prop}}(\text{CHECK})=0$ 은 *수렴 후에도 유지되는 고정점*이며 참값 $\mu_C$ 과
다르다(Lemma 2). 따라서:

> **ZCA ≠ 낙관적 초기화.** 표면("0이 음수를 흡수")은 같으나, 낙관적 초기화는 *"아직 안 배워서"*(일시적,
> 고정점=참값), ZCA는 *"구조적으로 못 배워서"*(영구적, 고정점=0≠참값). 이 *고정점의 차이*가 본 기여의 커널.

---

## 7. Proposition (VIC 복원 — 임계 가상비용)

CHECK에 가상 투자 $\varepsilon>0$ 을 부여하면 $Q_{\text{vic}}(\text{CHECK})=\frac{\varepsilon}{\varepsilon+c}\mu_C$.
Theorem의 설정($\mu_C<\mu_B<0$)에서, greedy가 BET(최적)을 선택할 필요충분조건은
$$\frac{b}{b+c}\,\mu_B \;>\; \frac{\varepsilon}{\varepsilon+c}\,\mu_C.$$
$\mu_C<0$ 이므로 이를 $\varepsilon$ 에 대해 풀면, $k:=\frac{b}{b+c}\cdot\frac{\mu_B}{\mu_C}\in(0,1)$ 에 대해
$$\boxed{\,\varepsilon \;>\; \varepsilon_{\min}=\frac{k\,c}{1-k}.\,}$$

*해석.* (i) $\varepsilon$ 이 임계 $\varepsilon_{\min}$ 보다 크면 CHECK가 음으로 내려가 BET에 자리를 내준다(복원).
(ii) $\varepsilon$ 이 너무 작으면 $Q_{\text{vic}}(\text{CHECK})\approx 0$ 으로 ZCA 잔존. (iii) 대칭 경우 $\varepsilon=b,\ \text{동일}\ c$
에서 $\frac{\varepsilon}{\varepsilon+c}=\frac{b}{b+c}$ 이므로 조건은 $\mu_B>\mu_C$(가정상 참) → **항상 복원**.
$\varepsilon_{\min}$ 은 작을 수 있어, *"무시할 만한 1칩"이 임계만 넘으면 충분*하다는 VIC 설계와 정합.

> **단서(메커니즘 정직성)**: VIC의 credit은 $\frac{\varepsilon}{\varepsilon+c}\mu_C$ 로 *부호·내용 의존*(참값 쪽으로 당김)인
> 반면, 무정보 처방(잡음·tie-break)은 고정점 0을 바꾸지 않고 argmax만 흔든다.

### 7.1 탈출 메커니즘 통제비교 (toy)

[`verify_toy_breakers.py`](verify_toy_breakers.py), 동일 toy($\mu_C=-5,\mu_B=-1$, $b=c=1$). 비례배분 위에
얹은 네 처방을 비교한다:

| 메커니즘 | $Q(\text{CHECK})$ | $Q(\text{BET})$ | $P(\text{pick BET})$ | greedy | 판정 |
|---|---|---|---|---|---|
| std (대조) | −5.0 | −1.0 | 1.00 | BET | ZCA 없음 |
| **prop (ZCA)** | −0.0 | −0.5 | 0.00 | CHECK | 흡수 |
| **VIC** ($\varepsilon=1$) | −2.5 | −0.5 | 1.00 | BET | **복원·informed** |
| noise ($\sigma=1$) | −0.0 | −0.5 | **0.36** | CHECK | **미복원** |
| tie-break | −0.0 | −0.5 | 0.00 | CHECK | **미복원** |
| fixed-pen ($\kappa=1$) | −1.0 | −0.5 | 1.00 | BET | 복원·무정보 |

두 가지가 갈린다:
1. **strict ZCA 발동 여부.** ZCA의 흡수는 $0 > Q(\text{BET})<0$ 인 *부등식*이지 *동률*이 아니다.
   따라서 "동률일 때만 CHECK 후순위"인 **tie-break은 미발동**($0\ne-0.5$) → 흡수 잔존. tie-break은
   *동률 하위경우*(예: 두 행동 모두 미방문 $0=0$, 실측 FOLD=CALL=0)만 풀고 strict 흡수는 못 푼다.
   **잡음**도 고정점 0이 $Q(\text{BET})=-0.5$ 보다 *높아서*, 결정시 잡음을 줘도 열등 CHECK를 다수
   ($1-0.36=64\%$) 선택 → 미복원. → **VIC는 tie-break·잡음의 동등물이 아니다.**
   *(단서: 여기 **잡음**는 결정시 tie-break 잡음다. 학습중 zero-mean 보상 잡음는 MC 고정점 $\mathbb{E}[R]$ 을
   바꾸지 않아 $Q_{\text{prop}}(\text{CHECK})\to0$ 그대로 → 역시 ZCA를 못 깬다(Prop 6에 귀속). 즉 결정시·학습중
   어느 잡음도 strict 흡수를 탈출하지 못한다.)*
2. **informed 여부.** VIC와 fixed-penalty는 둘 다 복원하나, VIC의 고정점은 $\frac{\varepsilon}{\varepsilon+c}\mu_C$ 로
   *참값 $\mu_C$ 부호·크기에 연동*(informed)인 반면 fixed-penalty는 상수 $-\kappa$ 로 *무정보*. 서로 다른
   $\mu_C$ 를 갖는 다중 CHECK-류 상태에 단일 $\kappa$ 는 부적응(어떤 상태는 과교정/미교정)이나
   VIC는 상태별 $\mu_C$ 에 자동 적응한다. 단 이 *적응 이점이 성능에 유의*한지는 실제 MDP의
   통제비교 사안(toy는 존재·방향만 보임).

> **요약**: 흡수 *탈출* 자체는 VIC·fixed-pen 둘 다 가능하나, **tie-break·잡음는 strict ZCA를 못 푼다**(고정점 0 불변).
> VIC만 "strict 흡수 해소 + 고정점 informed" 둘을 동시 충족. *고유 가치*(informed 적응이 OOD 성능에 유의한가)는
> 실제 MDP seed-sweep 통제비교에서 별도 판정한다(범위상 향후 과제).

---

## 8. 수치 검증

[`verify_toy_zca.py`](verify_toy_zca.py), $b=c=1,\ \mu_C=-5,\ \mu_B=-1,\ \varepsilon=1$, 400k 에피소드:

| 방식 | $Q(\text{CHECK})$ | $Q(\text{BET})$ | greedy | 판정 |
|---|---|---|---|---|
| 표준 MC | **−4.99** ($\approx\mu_C$) | −1.00 | BET | 정상(최적) |
| 비례배분(ZCA) | **0.000** ($\ne\mu_C$) | −0.50 | CHECK | **흡수(열등)** |
| VIC | −2.50 | −0.50 | BET | **복원** |

$\varepsilon=b=1,\ c=1$ 이므로 $\varepsilon>\varepsilon_{\min}$ 충족 → 복원(Prop. 7-iii). Lemma 2·Theorem·Prop. 7 모두 일치.

---

## 9. 범위와 한계 (정직)

- 본 증명은 *toy MDP*(단일 결정점, 고정 후속투자 $c$)에서의 **고정점 사실**이다. 실제 2,048셀 MDP에서는
  $c$ 가 궤적마다 변하고 다단계 부트스트랩이 없으나(MC), 핵심 — *비용 0 행동의 비례 credit이 구조적 0* — 은 동일.
- 본 정리는 **존재·특성화**(ZCA 고정점이 생기고 열등 흡수를 만든다)이지, *"VIC가 유일·최선 처방"*이 아니다.
  VIC는 *임계 이상이면 작동하는 한 처방*이며(Prop. 7). 단, §7.1에서 **잡음·tie-break은 strict ZCA를
  아예 탈출하지 못함이 해석적으로 판명**(고정점 0 불변·동률 미발동)되어 VIC와 동등물이 아니다. *경험적*
  통제비교로 남는 것은 좁혀져 — **VIC의 informed 적응이 fixed-penalty(무정보 탈출) 대비 *성능*에서 유의한가**
  (실제 MDP, seed-sweep)뿐이다.
- 따라서 방어 가능한 주장: **"투자비례 기여도 배분은 분산감소의 합리적 선택이나 비용 0 행동에 구조적
  영-고정점(ZCA)을 남기고(증명), 이는 낙관적 초기화와 구별되며(Prop. 6), 최소 가상비용 VIC가 임계 이상에서
  이를 해소한다(Prop. 7)."** — 임팩트 크기와 무관하게 반박 불가한 형식적 결과.
