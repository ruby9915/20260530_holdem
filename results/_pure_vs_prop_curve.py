import csv
runs = {
 'PURE': 'results/pure_softmax_mixed_2m/eval_results.csv',
 'PROP_VICon': 'results/ablation_vic_2m/mixed_vic_on/eval_results.csv',
 'PROP_VICoff': 'results/ablation_vic_2m/mixed_vic_off/eval_results.csv',
}


def rolling(xs, w=10):
    out = []
    for i in range(len(xs)):
        s = xs[max(0, i - w + 1):i + 1]
        out.append(sum(s) / len(s))
    return out


def be(eps, roll):
    for e, v in zip(eps, roll):
        if e > 0 and v > 0:
            return e
    return None


hdr = f"{'run':<12}{'BE_rand_ep':>12}{'BE_tag_ep':>12}{'finalQ_rand':>13}{'finalQ_tag':>12}"
print(hdr)
print('-' * len(hdr))
for name, p in runs.items():
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    ep = [int(r['episode']) for r in rows]
    rnd = [float(r['mbb/g_vs_random']) for r in rows]
    tag = [float(r['mbb/g_vs_rulebased']) for r in rows]
    rr, rt = rolling(rnd), rolling(tag)
    ber, bet = be(ep, rr), be(ep, rt)
    q = max(1, len(rows) // 4)
    fr = sum(rnd[-q:]) / q
    ft = sum(tag[-q:]) / q
    print(f"{name:<12}{str(ber):>12}{str(bet):>12}{fr:>13.1f}{ft:>12.1f}")
