"""VIC ablation 정밀평가(100k×5) 결과를 파싱해 요약 CSV로 저장."""
import re
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

CONDS = [
    ('single', 'on',  'single_tag_vic_on'),
    ('single', 'off', 'single_tag_vic_off'),
    ('cycle',  'on',  'cycle_vic_on'),
    ('cycle',  'off', 'cycle_vic_off'),
    ('mixed',  'on',  'mixed_vic_on'),
    ('mixed',  'off', 'mixed_vic_off'),
]

# "==> ... vsRand mean +987.1 (...SD 76.7) | vsTAG mean +940.4 (...SD 16.5)"
PAT = re.compile(
    r"vsRand mean\s+([+-][\d.]+)\s*\(.*?SD\s+([\d.]+)\)\s*\|\s*"
    r"vsTAG mean\s+([+-][\d.]+)\s*\(.*?SD\s+([\d.]+)\)"
)

rows = []
for scheme, vic, name in CONDS:
    log = RESULTS / f"eval100k_{name}.log"
    text = log.read_text(encoding="utf-8", errors="replace")
    m = None
    for line in text.splitlines():
        if "==>" in line and "vsRand mean" in line:
            m = PAT.search(line)
    if not m:
        print(f"[WARN] no match: {name}")
        continue
    r_mean, r_sd, t_mean, t_sd = (float(x) for x in m.groups())
    r_lo = r_mean - 3 * r_sd
    t_lo = t_mean - 3 * t_sd
    verdict = "BOTH+ robust" if (r_lo > 0 and t_lo > 0) else (
        "vsRandom FAIL" if r_mean < 0 else "vsTAG weak")
    rows.append({
        "scheme": scheme, "vic": vic,
        "vs_random_mbb": r_mean, "vs_random_sd": r_sd, "vs_random_3sd_lo": round(r_lo, 1),
        "vs_tag_mbb": t_mean, "vs_tag_sd": t_sd, "vs_tag_3sd_lo": round(t_lo, 1),
        "verdict": verdict,
    })

out = RESULTS / "ablation_vic_2m" / "_summary_100kx5.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"saved: {out}\n")
print(f"{'scheme':8}{'VIC':5}{'vsRandom (mean,SD,-3SD)':30}{'vsTAG (mean,SD,-3SD)':30}{'verdict'}")
print("-" * 100)
for r in rows:
    print(f"{r['scheme']:8}{r['vic']:5}"
          f"{r['vs_random_mbb']:+8.1f} ±{r['vs_random_sd']:5.1f} [{r['vs_random_3sd_lo']:+8.1f}]  "
          f"{r['vs_tag_mbb']:+8.1f} ±{r['vs_tag_sd']:5.1f} [{r['vs_tag_3sd_lo']:+8.1f}]  "
          f"{r['verdict']}")
