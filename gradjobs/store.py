"""Persistance : data/jobs.json (offres, versionné) et data/cache/state.json (état, non versionné)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, Iterable

from . import config


def load_jobs(path: Path) -> Dict[str, dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("jobs", {})
    except (OSError, ValueError):
        return {}


def load_filters_version(path: Path) -> str:
    """Empreinte des filtres qui ont produit data/jobs.json ("" si inconnue)."""
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("filters_version", "")
    except (OSError, ValueError):
        return ""


def filters_fingerprint() -> str:
    """Hash de config.py + filters.py : change dès qu'on touche aux filtres."""
    import hashlib
    from . import filters
    h = hashlib.sha256()
    for mod in (config, filters):
        h.update(Path(mod.__file__).read_bytes())
    return h.hexdigest()[:12]


def save_jobs(path: Path, jobs: Dict[str, dict], today: date, filters_version: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {k: jobs[k] for k in sorted(jobs)}
    payload = {"updated": today.isoformat(), "filters_version": filters_version, "jobs": ordered}
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def load_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    state.setdefault("invalid", {})     # "ats:slug" -> date ISO du dernier 404
    state.setdefault("rejected", {})    # clé d'offre -> marqueur "updated" au moment du rejet
    return state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def merge(prev: Dict[str, dict], outcomes: Iterable, today: date) -> Dict[str, dict]:
    """Fusionne les résultats du run dans l'existant.

    Une offre n'est marquée fermée que si son board a été lu avec succès ce jour-là et
    qu'elle n'y figure plus : une erreur réseau ne ferme donc rien.
    """
    today_iso = today.isoformat()
    jobs = {k: dict(v) for k, v in prev.items()}
    ok_boards = set()
    seen_open = set()

    for out in outcomes:
        if out.status != "ok":
            continue
        ok_boards.add((out.ats, out.slug))
        for rec in out.accepted:
            old = jobs.get(rec["key"])
            rec = dict(rec)
            rec["first_seen"] = old["first_seen"] if old else today_iso
            rec["last_seen"] = today_iso
            rec["status"] = "open"
            rec["closed_on"] = None
            jobs[rec["key"]] = rec
            seen_open.add(rec["key"])
        for key in out.kept:
            if key in jobs:
                jobs[key]["last_seen"] = today_iso
                jobs[key]["status"] = "open"
                jobs[key]["closed_on"] = None
                seen_open.add(key)

    for key, rec in jobs.items():
        if rec.get("status") == "open" and (rec["ats"], rec["slug"]) in ok_boards and key not in seen_open:
            rec["status"] = "closed"
            rec["closed_on"] = today_iso

    for key in list(jobs):
        rec = jobs[key]
        if rec.get("status") == "closed" and rec.get("closed_on"):
            if (today - date.fromisoformat(rec["closed_on"])).days > config.CLOSED_KEEP_DAYS:
                del jobs[key]
    return jobs