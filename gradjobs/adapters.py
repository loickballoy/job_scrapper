"""Un adaptateur par ATS : appelle l'API publique du board et normalise en RawJob.

Formats vérifiés dans la documentation :
  Greenhouse : GET boards-api.greenhouse.io/v1/boards/{slug}/jobs            (liste, sans description)
               GET boards-api.greenhouse.io/v1/boards/{slug}/jobs/{id}       (détail, champ "content")
               Le champ "content" est du HTML échappé (&lt;p&gt;) -> filters.clean_text() le décode.
  Lever      : GET api.lever.co/v0/postings/{slug}?mode=json                 (liste + descriptions)
  Ashby      : GET api.ashbyhq.com/posting-api/job-board/{slug}              ({"jobs": [...]} + descriptions)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, List, Optional


@dataclass
class RawJob:
    ats: str
    slug: str
    job_id: str
    title: str
    locations: List[str]
    url: str
    department: str = ""
    description: str = ""          # HTML ou texte brut ; vide tant que le détail n'est pas chargé (Greenhouse)
    posted: Optional[date] = None
    updated: str = ""              # marqueur de changement propre à l'ATS (sert au cache de décisions)
    company: str = ""
    employment_type: str = ""


@dataclass
class BoardResult:
    status: str                    # "ok" | "not_found" | "error"
    jobs: List[RawJob] = field(default_factory=list)


def parse_date(value: Any) -> Optional[date]:
    """ISO 8601 ('2013-08-01T20:00:00Z') ou millisecondes epoch (Lever) -> date."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).date()
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, OverflowError, OSError):
        return None


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        x = (x or "").strip()
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    return out


# --------------------------------------------------------------------------- Greenhouse

class Greenhouse:
    name = "greenhouse"
    needs_detail = True            # la liste ne contient pas la description

    BASE = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, http):
        self.http = http

    def fetch(self, slug: str) -> BoardResult:
        status, data = self.http.get_json(f"{self.BASE}/{slug}/jobs")
        if status == 404:
            return BoardResult("not_found")
        if status != 200 or not isinstance(data, dict):
            return BoardResult("error")
        jobs = []
        for j in data.get("jobs") or []:
            if j.get("id") is None:
                continue
            locs = [(j.get("location") or {}).get("name", "")]
            locs += [o.get("location") or o.get("name") or "" for o in (j.get("offices") or [])]
            jobs.append(RawJob(
                ats=self.name, slug=slug, job_id=str(j["id"]),
                title=j.get("title") or "",
                locations=_dedupe(locs),
                url=j.get("absolute_url") or "",
                department=", ".join(d.get("name", "") for d in (j.get("departments") or [])),
                description=j.get("content") or "",
                posted=parse_date(j.get("first_published")),
                updated=j.get("updated_at") or "",
                company=j.get("company_name") or "",
            ))
        return BoardResult("ok", jobs)

    def fetch_detail(self, job: RawJob) -> bool:
        status, data = self.http.get_json(f"{self.BASE}/{job.slug}/jobs/{job.job_id}")
        if status != 200 or not isinstance(data, dict):
            return False
        job.description = data.get("content") or job.description
        job.posted = parse_date(data.get("first_published")) or job.posted
        job.company = data.get("company_name") or job.company
        return True


# --------------------------------------------------------------------------- Lever

class Lever:
    name = "lever"
    needs_detail = False

    BASES = ("https://api.lever.co/v0/postings", "https://api.eu.lever.co/v0/postings")

    def __init__(self, http):
        self.http = http

    def fetch(self, slug: str) -> BoardResult:
        data = None
        for base in self.BASES:                       # instance globale, puis instance EU
            status, payload = self.http.get_json(f"{base}/{slug}", params={"mode": "json"})
            if status == 200 and isinstance(payload, list):
                data = payload
                break
            if status == 404:
                continue
            return BoardResult("error")
        if data is None:
            return BoardResult("not_found")

        jobs = []
        for j in data:
            if not j.get("id"):
                continue
            cat = j.get("categories") or {}
            locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
            parts = [j.get("descriptionPlain") or j.get("description") or ""]
            for lst in j.get("lists") or []:           # les exigences ("Requirements") sont ici
                parts.append(str(lst.get("text") or ""))
                parts.append(str(lst.get("content") or ""))
            parts.append(j.get("additionalPlain") or j.get("additional") or "")
            jobs.append(RawJob(
                ats=self.name, slug=slug, job_id=str(j["id"]),
                title=j.get("text") or "",
                locations=_dedupe(list(locs)),
                url=j.get("hostedUrl") or j.get("applyUrl") or "",
                department=cat.get("department") or cat.get("team") or "",
                description="\n".join(p for p in parts if p),
                posted=parse_date(j.get("createdAt")),
                updated=str(j.get("createdAt") or ""),
                employment_type=cat.get("commitment") or "",
            ))
        return BoardResult("ok", jobs)


# --------------------------------------------------------------------------- Ashby

class Ashby:
    name = "ashby"
    needs_detail = False

    BASE = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, http):
        self.http = http

    def fetch(self, slug: str) -> BoardResult:
        status, data = self.http.get_json(f"{self.BASE}/{slug}")
        if status == 404:
            return BoardResult("not_found")
        if status != 200 or not isinstance(data, dict):
            return BoardResult("error")
        jobs = []
        for j in data.get("jobs") or []:
            if not j.get("id") or j.get("isListed") is False:
                continue
            locs = [j.get("location") or ""]
            for sec in j.get("secondaryLocations") or []:
                locs.append(sec.get("location", "") if isinstance(sec, dict) else str(sec))
            addr = ((j.get("address") or {}).get("postalAddress")) or {}
            locality = ", ".join(x for x in (addr.get("addressLocality"), addr.get("addressCountry")) if x)
            if locality:
                locs.append(locality)
            if j.get("isRemote") and not any(locs):
                locs.append("Remote")
            jobs.append(RawJob(
                ats=self.name, slug=slug, job_id=str(j["id"]),
                title=j.get("title") or "",
                locations=_dedupe(locs),
                url=j.get("jobUrl") or j.get("applyUrl") or "",
                department=j.get("department") or j.get("team") or "",
                description=j.get("descriptionPlain") or j.get("descriptionHtml") or "",
                posted=parse_date(j.get("publishedAt")),
                updated=j.get("publishedAt") or "",
                employment_type=j.get("employmentType") or "",
            ))
        return BoardResult("ok", jobs)


def build_fetchers(http) -> dict:
    return {a.name: a for a in (Greenhouse(http), Lever(http), Ashby(http))}