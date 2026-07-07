# -*- coding: utf-8 -*-
"""실행 중인 사다리 런들의 진행률 실시간 표시 (저자지시 §5).

usage: python progress.py [로그 glob, 기본 'ladder_*.log']
  results/_logs/ 의 학습(train.py)·평가(evaluate.py) 로그를 5초마다 파싱해
  런별 % 와 전체 % 를 갱신 표시한다. 종료: Ctrl+C.
"""
import os
import re
import sys
import time
from pathlib import Path

LOGS = Path(__file__).resolve().parent.parent / 'results' / '_logs'
PATTERN = sys.argv[1] if len(sys.argv) > 1 else 'ladder_*.log'

RE_TRAIN = re.compile(r'\(\s*(\d+(?:\.\d+)?)%\)')
RE_DONE  = re.compile(r'\[ladder-train\] done')
RE_REP   = re.compile(r'rep(\d+)/(\d+)')
RE_EVAL_DONE = re.compile(r'==>')


def percent_of(path: Path) -> float:
    try:
        txt = path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return 0.0
    if RE_DONE.search(txt) or RE_EVAL_DONE.search(txt):
        return 100.0
    reps = RE_REP.findall(txt)
    if reps:                                   # 평가 로그
        k, n = reps[-1]
        return int(k) / int(n) * 100.0
    pcts = RE_TRAIN.findall(txt)               # 학습 로그
    return float(pcts[-1]) if pcts else 0.0


def bar(p: float, width: int = 30) -> str:
    fill = int(p / 100 * width)
    return '#' * fill + '-' * (width - fill)


def main():
    while True:
        files = sorted(LOGS.glob(PATTERN))
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"=== ladder progress ({time.strftime('%H:%M:%S')}) — {LOGS}\\{PATTERN} ===\n")
        if not files:
            print('  (일치하는 로그 없음 — 런 시작 전이거나 glob 확인)')
        total = 0.0
        for f in files:
            p = percent_of(f)
            total += p
            print(f"  {f.stem:<28} [{bar(p)}] {p:5.1f}%")
        if files:
            avg = total / len(files)
            print(f"\n  {'OVERALL':<28} [{bar(avg)}] {avg:5.1f}%  ({len(files)}개 런)")
        print('\n  (5초마다 갱신, Ctrl+C 종료)')
        time.sleep(5)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
