import csv
import statistics as st

CONDS = [
    'single_tag_vic_on', 'single_tag_vic_off',
    'cycle_vic_on', 'cycle_vic_off',
    'mixed_vic_on', 'mixed_vic_off',
]


def tail(path, n=10):
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    return rows[-n:]


print(f'{"condition":22} | vsRandom mbb(mean +-SD [-3SD]) | vsTAG mbb(mean +-SD [-3SD]) | win% R/T | verdict')
print('-' * 110)
for c in CONDS:
    t = tail(f'results/ablation_vic_2m/{c}/eval_results.csv')
    rm = [float(r['mbb/g_vs_random']) for r in t]
    bm = [float(r['mbb/g_vs_rulebased']) for r in t]
    rw = [float(r['win%_vs_random']) for r in t]
    bw = [float(r['win%_vs_rulebased']) for r in t]
    rmu, rsd = st.mean(rm), st.pstdev(rm)
    bmu, bsd = st.mean(bm), st.pstdev(bm)
    rlo, blo = rmu - 3 * rsd, bmu - 3 * bsd
    v = 'BOTH+ robust' if rlo > 0 and blo > 0 else ('both+ mean-only' if rmu > 0 and bmu > 0 else 'FAIL')
    print(f'{c:22} | {rmu:8.0f} +-{rsd:6.0f} [{rlo:8.0f}] | {bmu:7.0f} +-{bsd:6.0f} [{blo:8.0f}] | {st.mean(rw)*100:4.0f}/{st.mean(bw)*100:4.0f} | {v}')
