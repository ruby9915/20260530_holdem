# -*- coding: utf-8 -*-
"""단일 학습 러너 — 실험 = 설정 조합. 스크립트 사본 증식 금지.

usage:
  python train.py --out DIR --card legacy8 --credit prop --vic off --seed 1
  python train.py --out DIR --card ehs20 --credit prop --vic checktime --vic-amount 0.30 --seed 3

설정 전체가 out/config.json 에 기록된다 (재현성).
체크포인트 평가(200게임)는 학습곡선 참고용 — 결론은 evaluate.py(100k×5)에서만.
단 이 평가는 전역 random 스트림을 소비하므로 --eval-every/--eval-games 는
계측 인자가 아니라 학습 궤적을 바꾸는 실효 하이퍼파라미터다 (재개 시 잠금 대상).

장기 런은 --ckpt-every 로 out/ckpt.pkl 을 주기 저장하고, 재시작 시 자동 재개한다.
재개 런의 최종 q/n 은 무중단 런과 비트 단위로 동일하다 (저장 지점을 평가 직후로 고정).
"""
import argparse
import csv
import hashlib
import json
import math
import os
import pickle
import random
import shutil
import statistics
import sys
import time
from pathlib import Path

from actions import N_ACTIONS_OF
from cards import make_cards
from game import BIG_BLIND, play_eval_episode, play_train_episode
from personas import PERSONA_POLICIES
from qtable import QTable

TEMP_START, TEMP_END, TEMP_DECAY_END = 10.0, 0.5, 0.8   # 레거시 스케줄


def temperature_at(episode: int, total: int) -> float:
    progress = min(1.0, episode / (total * TEMP_DECAY_END))
    return TEMP_START + (TEMP_END - TEMP_START) * progress


def mbb_se(payoffs):
    n = len(payoffs)
    mean = sum(payoffs) / n
    std = statistics.stdev(payoffs) if n > 1 else 0.0
    scale = 1000.0 / BIG_BLIND
    return mean * scale, (std / math.sqrt(n)) * scale


def checkpoint_eval(qt, cards, n_games: int, actions_version: str = 'A8'):
    out = {}
    for kind in ('random', 'eval_tag'):
        pays = [play_eval_episode(qt, cards, kind, learner_id=i % 2,
                                  actions_version=actions_version)
                for i in range(n_games)]
        mbb, se = mbb_se(pays)
        out[kind] = (sum(1 for p in pays if p > 0) / n_games, mbb, se)
    return out


# 27/28번 재현용 혼합 학습상대 풀·가중치 (레거시 동일)
TRAIN_PERSONAS = ['tag', 'lag', 'man', 'sta', 'nit']
MIX_WEIGHTS    = [0.20, 0.25, 0.15, 0.25, 0.15]


# ── 체크포인트/재개 ────────────────────────────────────────
CKPT_SCHEMA = 'ladder-ckpt-v1'

# 재개 시 반드시 일치해야 하는 설정 — 하나라도 다르면 결정론이 깨진다.
# eval_every/eval_games 도 포함: 체크포인트 평가가 전역 스트림을 소비하므로
# 값이 달라지면 이후 딜·행동표본이 통째로 어긋난다 (직관에 반하므로 명시).
LOCKED_KEYS = ('seed', 'episodes', 'eval_every', 'eval_games', 'card', 'actions',
               'credit', 'vic', 'vic_amount', 'opponent', 'scheme', 'pot_apply',
               'q_init', 'temp_floor', 'uniform_penalty')


# 학습 궤적에 관여하는 소스 파일 — 재개 시 코드가 바뀌었으면 경고 (config 로는 못 잡는다).
SRC_FILES = ('train.py', 'game.py', 'qtable.py', 'cards.py', 'personas.py',
             'actions.py', 'defs.py', 'cfr_opponent.py')


def src_digests() -> dict:
    """학습 경로 소스의 sha256 — 중단 중 코드가 바뀐 채로 이어붙는 사고를 탐지."""
    here = Path(__file__).parent
    out = {}
    for name in SRC_FILES:
        p = here / name
        if p.exists():
            out[name] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def run_config(cfg) -> dict:
    """config.json·meta 용 설정 — 운영 전용 인자는 제외해 기존 런과 동일하게 유지."""
    return {k: v for k, v in vars(cfg).items() if k not in ('ckpt_every', 'no_resume')}


def _replace_retry(src, dst) -> bool:
    """Windows 공유위반(WinError 5/32) 대비 재시도 — 백신·색인기가 파일을 잡는 순간이 있다.

    저장 실패는 다음 주기에 만회되지만 프로세스 사망은 만회가 안 된다 → 끝내 실패하면 False.
    """
    delay = 0.05
    for k in range(6):
        try:
            os.replace(src, dst)
            return True
        except OSError as e:
            err = e
            time.sleep(delay)
            delay *= 2
    print(f"  [ckpt] WARN: replace 실패 {src} -> {dst} ({err}) - 이번 저장 건너뜀",
          flush=True)
    return False


def save_ckpt(path, cfg, ep, rows, qt, persona_rng, cfr_opp, elapsed) -> bool:
    """원자적 저장 — tmp 기록·fsync 후 os.replace 단일 교체. 직전 세대는 .prev 로 복사 보관.

    복원 대상은 6가지: 전역 random / persona_rng / CfrOpponent.rng·계수기 /
    q·n / 진행 인덱스 ep·rows. EHS 캐시는 순수 memoization 이라 저장하지 않는다.
    회전을 이동이 아니라 복사로 하는 이유: 이동이면 ckpt.pkl 이 부재하는 창이 생기고
    하필 그 순간 죽으면 재개가 조용히 실패한다. os.replace 하나면 그 창이 없다.
    """
    d = {'schema': CKPT_SCHEMA, 'config': run_config(cfg), 'src': src_digests(),
         'ep': ep, 'rows': rows, 'elapsed': elapsed,
         'q': qt.q, 'n': qt.n,
         'global_rng': random.getstate(),
         'persona_rng': persona_rng.getstate(),
         'cfr': None}
    if cfr_opp is not None:
        # pol(649MB memmap)·트리 배열은 절대 넣지 않는다 — 재개 시 __init__ 이 재로드.
        d['cfr'] = {'rng': cfr_opp.rng.getstate(),
                    'translations': cfr_opp.translations,
                    'decisions': cfr_opp.decisions,
                    'desyncs': cfr_opp.desyncs,
                    'cur': cfr_opp.cur,
                    'seat': getattr(cfr_opp, 'seat', None)}
    p = Path(path)
    tmp = p.with_suffix(p.suffix + '.tmp')
    try:
        with open(tmp, 'wb') as f:
            pickle.dump(d, f, protocol=pickle.HIGHEST_PROTOCOL)
            f.flush()
            os.fsync(f.fileno())          # 정전/BSOD 시 rename 만 커밋되는 것 방지
        if p.exists():
            shutil.copy2(p, str(p) + '.prev')
    except OSError as e:
        print(f"  [ckpt] WARN: 저장 실패 ({e}) - 이번 저장 건너뜀", flush=True)
        return False
    return _replace_retry(tmp, p)


def _read_ckpt(path) -> dict:
    with open(path, 'rb') as f:
        d = pickle.load(f)
    if d.get('schema') != CKPT_SCHEMA:
        raise SystemExit(f"[ckpt] schema 불일치: {d.get('schema')} (기대 {CKPT_SCHEMA})")
    return d


def load_ckpt(path, cfg):
    """체크포인트 로드 + config 대조.

    반환: 재개용 dict, 또는 None(쓸 만한 ckpt 없음 → 처음부터).
    config 불일치는 즉시 중단(조용히 섞으면 안 된다). 파일 손상은 .prev 폴백 →
    그것도 못 쓰면 .bad 로 밀어내고 경고 후 처음부터 (교착 방지).
    """
    p, prev = Path(path), Path(str(path) + '.prev')
    d, used = None, None
    for cand in (p, prev):
        if not cand.exists():
            continue
        try:
            d, used = _read_ckpt(cand), cand
            break
        except SystemExit:
            raise
        except Exception as e:
            bad = Path(str(cand) + '.bad')
            bad.unlink(missing_ok=True)
            try:
                os.replace(cand, bad)
            except OSError:
                pass
            print(f"[ckpt] WARN: {cand.name} 손상 ({type(e).__name__}: {e}) "
                  f"-> {bad.name} 로 격리", flush=True)
    if d is None:
        if p.exists() or prev.exists():
            print('[ckpt] WARN: 쓸 수 있는 체크포인트가 없다 - 처음부터 학습한다',
                  flush=True)
        return None
    if used == prev:
        print(f"[ckpt] WARN: ckpt.pkl 을 못 써서 .prev(직전 세대) 로 재개한다 "
              f"- 진행분 일부가 되감긴다", flush=True)
    d['_src_path'] = used

    now, old = run_config(cfg), d['config']
    diff = [f"{k}: ckpt={old.get(k)!r} != now={now.get(k)!r}"
            for k in LOCKED_KEYS if old.get(k) != now.get(k)]
    if diff:
        raise SystemExit(
            '[ckpt] config 불일치 — 재개 거부 (이어붙이면 결정론이 깨진다):\n  '
            + '\n  '.join(diff)
            + f"\n  처음부터 다시 시작하려면 --no-resume (또는 {path} 삭제)")
    return d


def check_src(ck, out) -> None:
    """재개 시 소스 변경 탐지 — 거부하지 않고 경고 + 디렉터리에 증거를 남긴다.

    거부하면 주석 한 줄 고친 것만으로 20시간 배치가 죽는다. 대신 provenance 를
    남겨 사후에 '이 런은 코드가 섞였다'를 판별할 수 있게 한다.
    """
    old = ck.get('src')
    if not old:
        return                       # 구버전 ckpt (src 미기록) — 대조 불가
    now = src_digests()
    changed = sorted(k for k in set(old) | set(now) if old.get(k) != now.get(k))
    if not changed:
        return
    lines = [f"  {k}: ckpt={old.get(k)} != now={now.get(k)}" for k in changed]
    msg = ('[ckpt] WARN: 재개 대상과 소스가 다르다 - 이 런의 Q 는 두 코드 버전이 섞인다:\n'
           + '\n'.join(lines))
    print(msg, flush=True)
    (Path(out) / 'RESUME_SRC_CHANGED.txt').write_text(
        msg + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--card', default='legacy8')          # legacy8 | ehs20 | ehs50
    ap.add_argument('--credit', default='prop', choices=['prop', 'pure'])
    ap.add_argument('--vic', default='off',
                    choices=['off', 'fixed', 'checktime', 'terminal'])
    ap.add_argument('--vic-amount', type=float, default=0.0)  # fixed=칩, checktime/terminal=α(비율)
    ap.add_argument('--actions', default='A8', choices=['A8', 'A12'])  # 2단 행동축
    ap.add_argument('--opponent', default='tag',
                    choices=list(PERSONA_POLICIES) + ['random', 'cfrplus'])
    ap.add_argument('--scheme', default='single',
                    choices=['single', 'cycle', 'mixed'])    # 27/28번 재현
    ap.add_argument('--pot-apply', default='all',
                    choices=['all', 'invested_only', 'allcheck_only'])  # E1 격리
    ap.add_argument('--q-init', type=float, default=0.0)      # E8-② 낙관적 초기화
    ap.add_argument('--temp-floor', type=float, default=0.0)  # E8-① 탐색 강화
    ap.add_argument('--uniform-penalty', type=float, default=0.0)  # E8-③ 일률 벌점
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--episodes', type=int, default=2_000_000)
    ap.add_argument('--eval-every', type=int, default=8_000)
    ap.add_argument('--eval-games', type=int, default=200)
    ap.add_argument('--ckpt-every', type=int, default=250_000)  # 0 이면 저장만 비활성(재개는 유지)
    ap.add_argument('--no-resume', action='store_true')         # 기존 ckpt 삭제하고 처음부터
    cfg = ap.parse_args()

    # 복구 안내는 한국어 — 배치가 리다이렉트하면 cp949 로 깨진다 (진행 로그는 ASCII라 무증상).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass

    if cfg.vic != 'off' and cfg.vic_amount <= 0:
        raise SystemExit('--vic fixed/checktime/terminal 에는 --vic-amount > 0 필요')
    if cfg.scheme != 'single' and cfg.opponent != 'tag':
        raise SystemExit('--scheme cycle/mixed 는 --opponent 지정과 배타 (풀 고정)')

    out = Path(cfg.out)
    out.mkdir(parents=True, exist_ok=True)

    # 재개 여부는 무거운 make_cards/QTable 생성 전에 판정 (config 불일치는 조기 실패)
    ckpt_path = out / 'ckpt.pkl'
    ckpt_side = [Path(str(ckpt_path) + s) for s in ('.prev', '.tmp')]
    resume = None
    if cfg.no_resume:
        # 플래그의 의도는 '이 계보를 버린다' — 남겨두면 다음 재시작이 조용히 주워간다.
        for p in (ckpt_path, *ckpt_side):
            p.unlink(missing_ok=True)
    elif ckpt_path.exists() or ckpt_side[0].exists():
        resume = load_ckpt(ckpt_path, cfg)

    # config.json 은 재개 판정 뒤에 쓴다 — 거부된 시도가 틀린 설정을 남기면 provenance 오염.
    (out / 'config.json').write_text(
        json.dumps(run_config(cfg), indent=1, ensure_ascii=False), encoding='utf-8')

    random.seed(cfg.seed)
    persona_rng = random.Random(cfg.seed)          # 페르소나 선택 전용 (레거시 동일)
    cards = make_cards(cfg.card)
    qt = QTable(cards.n_states, init_q=cfg.q_init,
                n_actions=N_ACTIONS_OF[cfg.actions])
    rows = []

    cfr_opp = None
    if cfg.opponent == 'cfrplus':
        from cfr_opponent import CfrOpponent
        cfr_opp = CfrOpponent(rng_seed=cfg.seed)

    def opponent_for(i: int):
        if cfg.scheme == 'cycle':
            return PERSONA_POLICIES[TRAIN_PERSONAS[i % len(TRAIN_PERSONAS)]]
        if cfg.scheme == 'mixed':
            name = persona_rng.choices(TRAIN_PERSONAS, weights=MIX_WEIGHTS, k=1)[0]
            return PERSONA_POLICIES[name]
        if cfg.opponent == 'cfrplus':
            return cfr_opp
        return 'random' if cfg.opponent == 'random' else PERSONA_POLICIES[cfg.opponent]

    tag = (f"card={cfg.card} actions={cfg.actions} credit={cfg.credit} "
           f"vic={cfg.vic}({cfg.vic_amount}) opp={cfg.scheme}:{cfg.opponent} "
           f"seed={cfg.seed}")
    print(f"[ladder-train] {tag} ep={cfg.episodes:,} -> {out}", flush=True)

    ep, elapsed = 0, 0.0
    if resume is not None:
        # 순서 주의: 객체 생성을 모두 마친 뒤 맨 마지막에 전역 setstate.
        check_src(resume, out)
        ep, rows, elapsed = resume['ep'], resume['rows'], resume['elapsed']
        qt.q, qt.n = resume['q'], resume['n']
        if cfr_opp is not None and resume['cfr']:
            c = resume['cfr']
            cfr_opp.rng.setstate(c['rng'])
            cfr_opp.translations = c['translations']
            cfr_opp.decisions = c['decisions']
            cfr_opp.desyncs = c['desyncs']
            cfr_opp.cur = c['cur']
            if c['seat'] is not None:
                cfr_opp.seat = c['seat']
        persona_rng.setstate(resume['persona_rng'])
        random.setstate(resume['global_rng'])
        print(f"[ckpt] resume ep={ep:,}/{cfg.episodes:,} "
              f"({ep/cfg.episodes*100:.1f}%) elapsed={elapsed:.0f}s "
              f"<- {resume['_src_path']}", flush=True)

    t0 = time.perf_counter() - elapsed        # el/eta 를 누계 기준으로 유지
    last_ck = ep
    while ep < cfg.episodes:
        nxt = min(ep + cfg.eval_every, cfg.episodes)
        for i in range(ep + 1, nxt + 1):
            temp = max(cfg.temp_floor, temperature_at(i, cfg.episodes))
            play_train_episode(qt, cards, opponent_for(i), temp,
                               cfg.credit, cfg.vic, cfg.vic_amount,
                               learner_id=i % 2, pot_apply=cfg.pot_apply,
                               uniform_penalty=cfg.uniform_penalty,
                               actions_version=cfg.actions)
        ep = nxt
        ev = checkpoint_eval(qt, cards, cfg.eval_games, cfg.actions)
        (wr, mr, _), (wt, mt, _) = ev['random'], ev['eval_tag']
        rows.append((ep, wr, mr, wt, mt))
        el = time.perf_counter() - t0
        eta = el / ep * (cfg.episodes - ep)
        print(f"  ep={ep:>9,} ({ep/cfg.episodes*100:4.1f}%) "
              f"T={temperature_at(ep, cfg.episodes):5.2f} | "
              f"vsRand {mr:>+8.0f} | vsTAG {mt:>+8.0f} | "
              f"{el:6.0f}s eta {eta:6.0f}s", flush=True)

        # 저장 지점 = 평가 직후·다음 학습 블록 직전 (에피소드 경계).
        # 평가 전에 뜨면 재개 시 평가 소비분만큼 전역 스트림이 어긋난다.
        if cfg.ckpt_every > 0 and ep - last_ck >= cfg.ckpt_every and ep < cfg.episodes:
            if save_ckpt(ckpt_path, cfg, ep, rows, qt, persona_rng, cfr_opp, el):
                last_ck = ep          # 실패 시 갱신하지 않아 다음 블록에서 재시도
                print(f"  [ckpt] ep={ep:,} saved", flush=True)

    with open(out / 'train_curve.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['episode', 'win_vs_random', 'mbb_vs_random',
                    'win_vs_evaltag', 'mbb_vs_evaltag'])
        w.writerows(rows)

    qt.save(out / 'qtable.pkl', meta=run_config(cfg))
    # 최종 산출물이 안전하게 기록된 뒤에만 체크포인트 정리 (.tmp 잔여물 포함)
    for p in (ckpt_path, *ckpt_side):
        p.unlink(missing_ok=True)
    print(f"[ladder-train] done {time.perf_counter()-t0:.0f}s | saved {out}/qtable.pkl", flush=True)


if __name__ == '__main__':
    main()
