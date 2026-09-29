"""Découverte des entreprises : quels boards interroger.

Source principale : listes de slugs par ATS (~16 000 entreprises), téléchargées à l'exécution
depuis Feashliaa/job-board-aggregator (jeux de données CC BY-NC 4.0, jamais recopiés ici).
Complément : data/extra_slugs.txt, où tu peux ajouter des entreprises à la main.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import config

_SLUG_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,79}$")

# Motifs d'URL -> (ats, slug)
URL_PATTERNS = [
    ("greenhouse", re.compile(r"https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_app\?for=)?([A-Za-z0-9_.\-]+)")),
    ("lever", re.compile(r"https?://jobs(?:\.eu)?\.lever\.co/([A-Za-z0-9_.\-]+)")),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/([A-Za-z0-9_.\-]+)")),
]


def valid_slug(s: object) -> bool:
    return isinstance(s, str) and bool(_SLUG_OK.match(s))


def extract_slug(text: str) -> Optional[Tuple[str, str]]:
    """'https://jobs.lever.co/palantir/abc' -> ('lever', 'palantir') ; 'greenhouse:stripe' -> ('greenhouse', 'stripe')."""
    text = text.strip()
    for ats, rx in URL_PATTERNS:
        m = rx.match(text)
        if m and valid_slug(m.group(1)):
            return ats, m.group(1).lower()
    if ":" in text and not text.startswith("http"):
        ats, _, slug = text.partition(":")
        ats, slug = ats.strip().lower(), slug.strip().lower()
        if ats in config.SLUG_LIST_URLS and valid_slug(slug):
            return ats, slug
    return None


def load_extra_slugs(path: Path) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        hit = extract_slug(line)
        if hit:
            out.setdefault(hit[0], []).append(hit[1])
    return out


def _cache_file(cache_dir: Path, ats: str) -> Path:
    return cache_dir / f"slugs_{ats}.json"


def _read_cache(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_slug_lists(http, cache_dir: Path, today: date, force: bool = False, log=print) -> Dict[str, List[str]]:
    """Retourne {ats: [slug, ...]}, depuis le cache s'il est frais, sinon en téléchargeant."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    result: Dict[str, List[str]] = {}
    for ats, url in config.SLUG_LIST_URLS.items():
        path = _cache_file(cache_dir, ats)
        cached = _read_cache(path)
        fresh = False
        if cached and not force:
            try:
                age = (today - datetime.fromisoformat(cached["fetched"]).date()).days
                fresh = age <= config.SLUG_LIST_MAX_AGE_DAYS
            except (KeyError, ValueError):
                fresh = False
        if fresh:
            slugs = cached["slugs"]
        else:
            status, data = http.get_json(url)
            if status == 200 and isinstance(data, list):
                slugs = [s.lower() for s in data if valid_slug(s)]
                path.write_text(json.dumps({"fetched": today.isoformat(), "slugs": slugs}), encoding="utf-8")
                log(f"[discover] {ats}: {len(slugs)} entreprises téléchargées")
            elif cached:
                slugs = cached["slugs"]
                log(f"[discover] {ats}: téléchargement impossible (HTTP {status}), cache périmé utilisé")
            else:
                slugs = []
                log(f"[discover] {ats}: téléchargement impossible (HTTP {status}) et aucun cache")
        result[ats] = sorted(set(slugs))
    return result


def merge_slugs(*lists: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged: Dict[str, set] = {}
    for d in lists:
        for ats, slugs in d.items():
            merged.setdefault(ats, set()).update(slugs)
    return {ats: sorted(s) for ats, s in merged.items()}