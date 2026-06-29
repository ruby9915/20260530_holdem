# -*- coding: utf-8 -*-
"""seed sweep 100k×1 평가 로그 집계. config별 seed간 평균±SD + OOD 부호 일치.
OOD 정의: VIC ablation(persona학습)=vsRand / Random라인=vsRule."""
import io, os, re, glob, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
PAT = re.compile(r"==>\s*\S+\s*vsRand mean\s*(?P<r>[+-]?[\d.]+).*?vsTAG mean\s*(?P<t>[+-]?[\d.]+)")

# tag 예: vic_single_off_s1 / rand_on_s3
def parse_tag(tag):
    if tag.startswith("vic_"):
        m = re.match(r"vic_(single|cycle|mixed)_(on|off)_s(\d+)", tag)
        return ("ablation", m.group(1), m.group(2), int(m.group(3)))
    m = re.match(r"rand_(on|off)_s(\d+)", tag)
    return ("rand", "random", m.group(1), int(m.group(2)))

rows = {}  # (line,scheme,vic) -> list of (seed, vsRand, vsRule)
for log in glob.glob(os.path.join(HERE, "*.log")):
    tag = os.path.basename(log)[:-4]
    txt = io.open(log, encoding="utf-8", errors="ignore").read()
    m = None
    for m in PAT.finditer(txt):
        pass
    if not m:
        print("PARSE_FAIL", tag); continue
    line, scheme, vic, seed = parse_tag(tag)
    rows.setdefault((line, scheme, vic), []).append((seed, float(m["r"]), float(m["t"])))

def fmt(vals):
    mu = st.mean(vals); sd = st.pstdev(vals) if len(vals) > 1 else 0.0
    return f"{mu:+8.1f} ± {sd:5.1f}"

print(f"{'config':24}{'n':>3} {'vsRand(±SD)':>18} {'vsRule(±SD)':>18}  OOD부호일치")
print("-"*86)
order = [("ablation",s,v) for s in ("single","cycle","mixed") for v in ("on","off")] + \
        [("rand","random",v) for v in ("on","off")]
for key in order:
    if key not in rows: continue
    line, scheme, vic = key
    data = sorted(rows[key])
    seeds = [s for s,_,_ in data]
    rand = [r for _,r,_ in data]
    rule = [t for _,_,t in data]
    # OOD metric: ablation→vsRand, rand→vsRule
    ood = rand if line == "ablation" else rule
    n = len(ood)
    neg = sum(1 for x in ood if x < 0)
    pos = n - neg
    # off면 "붕괴(음)" 기대, on이면 "흑자(양)" 기대
    agree = f"{neg}/{n} 음(붕괴)" if vic == "off" else f"{pos}/{n} 양(흑자)"
    p = 0.5**n  # 한쪽으로 n/n일 때 단측 p
    pstr = f" p={p:.4f}" if (neg == n or pos == n) else ""
    name = f"{scheme}/{vic}({line[:3]})"
    print(f"{name:24}{n:>3} {fmt(rand):>18} {fmt(rule):>18}  {agree}{pstr}")
print("-"*86)
print("OOD: ablation=vsRand(미학습 Random) / rand라인=vsRule(미학습 RuleBased).")
print("필요조건 지지: 모든 off config에서 OOD가 n/n 음(붕괴), on은 n/n 양.")
