# -*- coding: utf-8 -*-
"""행렬 슬럼봇 배치 진행률 조회 (저자지시: 진행 상황 실시간 확인 가능하게).
usage: python slumbot_progress.py   (poker-ladder 디렉터리에서, 아무 때나 실행)"""
import glob
import io
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

TOTAL = 10000
logs = sorted(glob.glob('../results/_logs/slumbot_mx_*.log'))
if not logs:
    print('아직 로그 없음 (배치 시작 전이거나 첫 핸드 이전)')
done_hands = 0
for path in logs:
    name = path.split('slumbot_mx_')[-1][:-4]
    txt = io.open(path, encoding='utf-8', errors='ignore').read()
    final = re.search(r'==>.*mbb/g (\S+)', txt)
    prog = re.findall(r'(\d+)/(\d+) \| mbb/g (\S+)', txt)
    if final:
        done_hands += TOTAL
        print(f'{name:14s} 100% 완료  mbb/g {final.group(1)}')
    elif prog:
        h, tot, mbb = prog[-1]
        done_hands += int(h)
        print(f'{name:14s} {100*int(h)//int(tot):3d}% ({h}/{tot})  현재 mbb/g {mbb}')
    else:
        print(f'{name:14s}   0% (접속 중)')
grand = 20 * TOTAL
print(f'-- 전체: {100*done_hands//grand}% ({done_hands:,}/{grand:,} 핸드, 20런 기준)')
