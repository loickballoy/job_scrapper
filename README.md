# Graduate & Early-Career Electrical Systems Engineering Jobs

Graduate, junior and entry-level electrical systems engineering roles in **Switzerland, Canada, United Kingdom, France**, collected automatically from company job boards.

**Last updated:** 2026-09-30 &nbsp;|&nbsp; **5** open roles at **2** companies &nbsp;|&nbsp; **5** added in the last 7 days

## Legend

| Symbol | Meaning |
|---|---|
| 🛂 | The posting mentions it does **not** sponsor visas / requires existing work authorization |
| 🇺🇸 | Mentions a security clearance or US citizenship |
| 🗣️ | A non-English language appears to be required (heuristic) |
| ✈️ | Relocation support is mentioned |
| 🔎 | Early-career level **inferred from the description**, not stated in the title |
| 🔒 | The posting has disappeared from the company's job board |

Flags are keyword heuristics computed from the posting text: always read the original posting.

[🇨🇭 Switzerland (0)](#switzerland) · [🇨🇦 Canada (0)](#canada) · [🇬🇧 United Kingdom (4)](#united-kingdom) · [🇫🇷 France (1)](#france)

## 🇨🇭 Switzerland

_No matching roles right now._

## 🇨🇦 Canada

_No matching roles right now._

## 🇬🇧 United Kingdom

| Company | Role | Location | Flags | Apply | Age |
|---|---|---|---|---|---|
| Soho House &amp; Co. | Kitchen Porter - Electric House, West London | Electric House - 191 Portobello Rd, London W11 2ED | 🔎 | [Apply](https://job-boards.eu.greenhouse.io/sohohouseco/jobs/4981698101) | 1d |
| Soho House &amp; Co. | Runner - Electric House, West London | Electric House - 191 Portobello Rd, London W11 2ED; England, United Kingdom | 🔎 | [Apply](https://job-boards.eu.greenhouse.io/sohohouseco/jobs/4971337101) | 16d |
| Soho House &amp; Co. | Barback - Electric House, West London | Electric House - 191 Portobello Rd, London W11 2ED | 🔎 | [Apply](https://job-boards.eu.greenhouse.io/sohohouseco/jobs/4931385101) | 1mo |
| Soho House &amp; Co. | Waiter/ Waitress - Electric House X Speedboat Bar | Electric House - 191 Portobello Rd, London W11 2ED | 🔎 | [Apply](https://job-boards.eu.greenhouse.io/sohohouseco/jobs/4943026101) | 1mo |

## 🇫🇷 France

| Company | Role | Location | Flags | Apply | Age |
|---|---|---|---|---|---|
| The Exploration Company | AIT Electrical Engineer | Bordeaux, France | ✈️ 🔎 | [Apply](https://jobs.ashbyhq.com/the-exploration-company/7f288d6c-fd70-47fe-abd0-bfb738a3b08f) | 1mo |

## How this list is built

1. **Discovery.** ~16,000 company job boards on Greenhouse, Lever and Ashby (company lists below).
2. **Fetch.** Each board is read from the ATS's public job-board API. Nothing is scraped from HTML pages.
3. **Filter.** Only postings that pass *all* of the following are kept:
   - located in one of the enabled regions;
   - not a senior/staff/lead/manager role, and not an internship (configurable);
   - an electrical-systems engineering role (power, HV/MV/LV, power electronics, control-command, EWIS...),
     IT / software roles excluded; generic "Systems Engineer" titles are kept only if the description is electrical;
   - early-career: the title says so (graduate, new grad, junior, entry level, Engineer I...), **or** the
     description does (entry level, recent graduate, 0-N years);
   - the description does not require more than **2 years** of experience.
4. **Publish.** This file is regenerated automatically; a posting that disappears is shown 🔒 for
   7 days and then removed.

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
