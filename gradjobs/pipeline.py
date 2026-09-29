"""Orchestration : lit les boards en parallèle, filtre, et produit des enregistrements d'offres."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

from . import config, filters
from .adapters import RawJob


@dataclass
class Context:
    fetchers: dict
    today: date
    prev_records: Dict[str, dict] = field(default_factory=dict)
    rejected_cache: Dict[str, str] = field(default_factory=dict)
    company_names: Dict[str, str] = field(default_factory=dict)
    use_cache: bool = True


@dataclass
class BoardOutcome:
    ats: str
    slug: str
    status: str                                   # "ok" | "not_found" | "error"
    accepted: List[dict] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)  # offres inchangées depuis le dernier run
    rejected: Dict[str, str] = field(default_factory=dict)
    stats: Counter = field(default_factory=Counter)


def prettify(slug: str) -> str:
    return re.sub(r"[-_.]+", " ", slug).strip().title()


def display_name(job: RawJob, names: Dict[str, str]) -> str:
    return job.company or names.get(f"{job.ats}:{job.slug}") or prettify(job.slug)


def make_record(job: RawJob, region: str, decision: filters.Decision, company: str) -> dict:
    return {
        "key": f"{job.ats}:{job.slug}:{job.job_id}",
        "ats": job.ats,
        "slug": job.slug,
        "company": company,
        "title": " ".join(job.title.split()),
        "locations": job.locations,
        "region": region,
        "url": job.url,
        "posted": job.posted.isoformat() if job.posted else None,
        "updated": job.updated,
        "flags": decision.flags,
        "min_years": decision.years,
        "level_via": decision.level_via,
        "employment_type": job.employment_type,
    }


def process_board(ctx: Context, ats: str, slug: str,
                  explain: Optional[List[Tuple[RawJob, str, str]]] = None) -> BoardOutcome:
    """Lit un board et applique les filtres. `explain` : si fourni, reçoit (offre, verdict, raison) pour chaque offre."""
    fetcher = ctx.fetchers[ats]
    result = fetcher.fetch(slug)
    out = BoardOutcome(ats, slug, result.status)
    if result.status != "ok":
        return out

    for job in result.jobs:
        key = f"{ats}:{slug}:{job.job_id}"

        # Offre inchangée depuis le dernier run : on réutilise la décision sans rien retélécharger.
        if ctx.use_cache and explain is None and job.updated:
            prev = ctx.prev_records.get(key)
            if prev and prev.get("status") == "open" and prev.get("updated") == job.updated:
                out.kept.append(key)
                continue
            if ctx.rejected_cache.get(key) == job.updated:
                out.stats["cached reject"] += 1
                continue

        pre = filters.prefilter(job)
        if pre.reject:
            out.stats[pre.reject] += 1
            if explain is not None:
                explain.append((job, "REJECT", pre.reject))
            continue

        if getattr(fetcher, "needs_detail", False):
            if not fetcher.fetch_detail(job):
                out.stats["detail error"] += 1
                if explain is not None:
                    explain.append((job, "ERROR", "detail fetch failed"))
                continue

        decision = filters.finalize(job, pre, ctx.today)
        if not decision.accepted:
            out.stats[decision.reason] += 1
            if job.updated:
                out.rejected[key] = job.updated
            if explain is not None:
                explain.append((job, "REJECT", decision.reason))
            continue

        out.stats["accepted"] += 1
        out.accepted.append(make_record(job, pre.region, decision, display_name(job, ctx.company_names)))
        if explain is not None:
            explain.append((job, "ACCEPT", f"{decision.reason}; years={decision.years}; flags={' '.join(decision.flags)}"))
    return out


def run_boards(ctx: Context, targets: List[Tuple[str, str]], workers: Dict[str, int],
               log: Callable[[str], None] = print) -> List[BoardOutcome]:
    """Un pool de threads par ATS, pour respecter la limite propre à chacun (Ashby est le plus strict)."""
    by_ats: Dict[str, List[str]] = defaultdict(list)
    for ats, slug in targets:
        by_ats[ats].append(slug)

    executors = {ats: ThreadPoolExecutor(max_workers=workers.get(ats, 5)) for ats in by_ats}
    futures = {}
    for ats, slugs in by_ats.items():
        for slug in slugs:
            futures[executors[ats].submit(process_board, ctx, ats, slug)] = (ats, slug)

    outcomes: List[BoardOutcome] = []
    total = len(futures)
    for i, fut in enumerate(as_completed(futures), 1):
        ats, slug = futures[fut]
        try:
            outcomes.append(fut.result())
        except Exception as exc:                      # un board défaillant ne doit pas arrêter le run
            log(f"[error] {ats}:{slug}: {type(exc).__name__}: {exc}")
            outcomes.append(BoardOutcome(ats, slug, "error"))
        if i % 1000 == 0 or i == total:
            log(f"[run] {i}/{total} boards lus")
    for ex in executors.values():
        ex.shutdown(wait=True)
    return outcomes