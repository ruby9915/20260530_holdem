# -*- coding: utf-8 -*-
"""_reeval_100kx5/*.log 들을 파싱해 100k×5 재평가 요약 CSV 생성.
각 로그의 '==>' 요약 줄에서 vsRand/vsTAG 평균과 회차SD를 추출."""
import io, os, re, glob, csv

HERE = os.path.dirname(os.path.abspath(__file__))

# ==> <run> vsRand mean  +XXX.X (회차SD  Y.Y) | vsTAG mean  +ZZZ.Z (회차SD  W.W)
PAT = re.compile(
    r"==>\s*(?P<run>\S+)\s*vsRand mean\s*(?P<rm>[+-]?[\d.]+)\s*\([^\d]*?(?P<rsd>[\d.]+)\)"
    r".*?vsTAG mean\s*(?P<tm>[+-]?[\d.]+)\s*\([^\d]*?(?P<tsd>[\d.]+)\)"
)

rows = []
for log in sorted(glob.glob(os.path.join(HERE, "*.log"))):
    txt = io.open(log, encoding="utf-8", errors="ignore").read()
    m = None
    for m in PAT.finditer(txt):
        pass  # 마지막 매치 = 최종 요약
    name = os.path.basename(log)[:-4]
    if m:
        rm, rsd = float(m["rm"]), float(m["rsd"])
        tm, tsd = float(m["tm"]), float(m["tsd"])
        verdict = "BOTH+" if (rm > 0 and tm > 0) else (
                  "vsRand-" if rm <= 0 and tm > 0 else
                  "vsTAG-" if tm <= 0 and rm > 0 else "BOTH-")
        rows.append([name, f"{rm:.1f}", f"{rsd:.1f}", f"{tm:.1f}", f"{tsd:.1f}", verdict])
    else:
        rows.append([name, "NA", "NA", "NA", "NA", "PARSE_FAIL"])

out = os.path.join(HERE, "_summary_reeval_100kx5.csv")
with io.open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["run", "vsRand_mbb", "vsRand_sd", "vsTAG_mbb", "vsTAG_sd", "verdict"])
    w.writerows(rows)

print(f"{len(rows)} runs -> {out}\n")
print(f"{'run':<34}{'vsRand':>10}{'SD':>8}{'vsTAG':>10}{'SD':>8}  verdict")
for r in rows:
    print(f"{r[0]:<34}{r[1]:>10}{r[2]:>8}{r[3]:>10}{r[4]:>8}  {r[5]}")
