"""Génère README.md : un tableau par région, à la manière de SimplifyJobs."""
from __future__ import annotations

import html
from datetime import date
from typing import Dict, List

from . import config, filters

LEGEND = """\
| Symbol | Meaning |
|---|---|
| 🛂 | The posting mentions it does **not** sponsor visas / requires existing work authorization |
| 🇺🇸 | Mentions a security clearance or US citizenship |
| 🗣️ | A non-English language appears to be required (heuristic) |
| ✈️ | Relocation support is mentioned |
| 🔎 | Early-career level **inferred from the description**, not stated in the title |
| 🔒 | The posting has disappeared from the company's job board |

Flags are keyword heuristics computed from the posting text: always read the original posting.
"""

FOOTER = """\
## How this list is built

1. **Discovery.** ~16,000 company job boards on Greenhouse, Lever and Ashby (company lists below).
2. **Fetch.** Each board is read from the ATS's public job-board API. Nothing is scraped from HTML pages.
3. **Filter.** Only postings that pass *all* of the following are kept:
   - located in one of the enabled regions;
   - not a senior/staff/lead/manager role, and not an internship (configurable);
   - a software / firmware / embedded / systems / infrastructure / security role;
   - early-career: the title says so (graduate, new grad, junior, entry level, Engineer I...), **or** the
     description does (entry level, recent graduate, 0-N years);
   - the description does not require more than **{max_years} years** of experience.
4. **Publish.** This file is regenerated automatically; a posting that disappears is shown 🔒 for
   {closed_keep} days and then removed.

Everything above is configurable in [`gradjobs/config.py`](gradjobs/config.py).

## Run it yourself

```bash
pip install -r requirements.txt
python -m gradjobs check --ats greenhouse --slug stripe --explain   # see why each posting is kept or rejected
python -m gradjobs run --limit 200                                  # small test run
python -m gradjobs run                                              # full run, rewrites this README
pytest                                                              # unit tests
```

Limits worth knowing: only Greenhouse, Lever and Ashby are covered (not Workday, SmartRecruiters,
Personio, company-specific career sites...), so this is **not exhaustive**. Company display names come from
the ATS when it provides one, otherwise from the board slug.

## Credits and licenses

- Company lists (which boards exist) come from
  [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator), built from Common Crawl
  index data. Their datasets are licensed **CC BY-NC 4.0** (non-commercial, attribution required). They are
  downloaded at run time and are not redistributed in this repository.
- Job data comes from the public job-board APIs of Greenhouse, Lever and Ashby, and belongs to the respective
  employers. This project is not affiliated with any of them.
- Layout inspired by [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions).
"""


def _esc(text: str) -> str:
    return html.escape(" ".join(str(text).split()), quote=False).replace("|", "\\|")


def _ref_date(rec: dict) -> date:
    return date.fromisoformat(rec.get("posted") or rec["first_seen"])


def _age(rec: dict, today: date) -> str:
    days = max(0, (today - _ref_date(rec)).days)
    return f"{days}d" if days < 30 else f"{days // 30}mo"


def _locations(rec: dict, limit: int = 3) -> str:
    locs = [l for l in rec.get("locations", []) if l]
    shown = "<br>".join(_esc(l) for l in locs[:limit])
    if len(locs) > limit:
        shown += f"<br>+{len(locs) - limit} more"
    return shown


def _row(rec: dict, today: date) -> str:
    closed = rec.get("status") == "closed"
    flags = " ".join(rec.get("flags") or [])
    apply_cell = "🔒" if closed else f"[Apply]({rec['url']})"
    return (f"| {_esc(rec['company'])} | {_esc(rec['title'])} | {_locations(rec)} | {_esc(flags)} "
            f"| {apply_cell} | {_age(rec, today)} |")


def render_readme(jobs: Dict[str, dict], today: date) -> str:
    regions = [(n, e) for n, e, _ in config.REGIONS if n in config.ENABLED_REGIONS]
    open_jobs = [j for j in jobs.values() if j.get("status") == "open"]
    companies = {(j["ats"], j["slug"]) for j in open_jobs}
    new_week = sum(1 for j in open_jobs if (today - date.fromisoformat(j["first_seen"])).days <= 7)

    lines: List[str] = []
    lines.append("# Graduate & Early-Career Software Jobs")
    lines.append("")
    names = ", ".join(n for n, _ in regions)
    lines.append(f"Graduate, junior and entry-level software / embedded / systems roles in **{names}**, "
                 f"collected automatically from company job boards.")
    lines.append("")
    lines.append(f"**Last updated:** {today.isoformat()} &nbsp;|&nbsp; **{len(open_jobs)}** open roles at "
                 f"**{len(companies)}** companies &nbsp;|&nbsp; **{new_week}** added in the last 7 days")
    lines.append("")
    lines.append("## Legend")
    lines.append("")
    lines.append(LEGEND)

    index = " · ".join(
        f"[{e} {n} ({sum(1 for j in jobs.values() if j['region'] == n)})](#{n.lower().replace(' ', '-').replace('(', '').replace(')', '')})"
        for n, e in regions
    )
    lines.append(index)
    lines.append("")

    for name, emoji in regions:
        rows = [j for j in jobs.values() if j["region"] == name]
        anchor_title = f"{emoji} {name}"
        lines.append(f"## {anchor_title}")
        lines.append("")
        if not rows:
            lines.append("_No matching roles right now._")
            lines.append("")
            continue
        rows.sort(key=lambda r: (r.get("status") == "closed", -_ref_date(r).toordinal(), r["company"].lower(), r["title"].lower()))
        lines.append("| Company | Role | Location | Flags | Apply | Age |")
        lines.append("|---|---|---|---|---|---|")
        lines.extend(_row(r, today) for r in rows)
        lines.append("")

    lines.append(FOOTER.format(max_years=config.MAX_YEARS_REQUIRED, closed_keep=config.CLOSED_KEEP_DAYS))
    return "\n".join(lines).rstrip() + "\n"