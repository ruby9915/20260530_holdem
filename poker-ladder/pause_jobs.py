# -*- coding: utf-8 -*-
"""ladder 런 일시정지/재개 (저자 컴퓨터 사용 양보용).

usage: python pause_jobs.py suspend | resume | status
  대상: cmdline 에 poker-ladder 의 train/evaluate/slumbot_eval 이 포함된 python 프로세스.
  suspend = CPU 즉시 반환 (RAM 은 유지 — 재부팅·로그오프하면 진행 손실!)
  resume  = 정지 지점부터 그대로 계속.
"""
import sys

import psutil

TARGETS = ('train.py', 'evaluate.py', 'slumbot_eval.py', 'match.py',
           'precompute_matrices.py', 'precompute_ehs_buckets.py',
           'hunl_solver.py', 'hunl_solver2.py', 'bot_eval.py', 'lbr_eval.py')


def find():
    out = []
    for p in psutil.process_iter(['name', 'cmdline', 'status']):
        try:
            cmd = ' '.join(p.info['cmdline'] or [])
            if 'python' in (p.info['name'] or '').lower() and \
               any(t in cmd for t in TARGETS) and 'pause_jobs' not in cmd:
                out.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'status'
    procs = find()
    for p in procs:
        try:
            tag = ' '.join(p.cmdline()[-3:])[-70:]
            if mode == 'suspend' and p.status() != psutil.STATUS_STOPPED:
                p.suspend(); print(f"  suspended pid={p.pid} {tag}")
            elif mode == 'resume':
                p.resume(); print(f"  resumed   pid={p.pid} {tag}")
            else:
                print(f"  pid={p.pid} [{p.status()}] {tag}")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"  skip pid={p.pid}: {e}")
    print(f"{mode}: {len(procs)}개 프로세스")


if __name__ == '__main__':
    main()
