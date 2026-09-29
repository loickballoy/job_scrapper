"""Commandes :

    python -m gradjobs discover [--force]
    python -m gradjobs run [--ats greenhouse,lever,ashby] [--limit N] [--dry-run] [--no-cache]
    python -m gradjobs check --ats greenhouse --slug stripe [--explain]
    python -m gradjobs render
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from . import config, discover, store
from .adapters import build_fetchers
from .http import HttpClient
from .pipeline import Context, process_board, run_boards
from .render import render_readme

ROOT = Path(".")
DATA = ROOT / "data"
CACHE = DATA / "cache"
JOBS_FILE = DATA / "jobs.json"
STATE_FILE = CACHE / "state.json"
EXTRA_SLUGS = DATA / "extra_slugs.txt"
NAMES_FILE = DATA / "company_names.json"
README = ROOT / "README.md"


def _load_names() -> Dict[str, str]:
    try:
        return json.loads(NAMES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _targets(slug_lists: Dict[str, List[str]], ats_filter, limit, state, today, use_cache) -> List[Tuple[str, str]]:
    targets = []
    for ats, slugs in sorted(slug_lists.items()):
        if ats_filter and ats not in ats_filter:
            continue
        kept = []
        for slug in slugs:
            marked = state["invalid"].get(f"{ats}:{slug}")
            if use_cache and marked and (today - date.fromisoformat(marked)).days < config.INVALID_RECHECK_DAYS:
                continue                                    # 404 récent : inutile de re-tester
            kept.append(slug)
        if limit:
            kept = kept[:limit]
        targets += [(ats, s) for s in kept]
    return targets


def cmd_discover(args) -> int:
    http = HttpClient(config.USER_AGENT)
    lists = discover.load_slug_lists(http, CACHE, date.today(), force=args.force)
    lists = discover.merge_slugs(lists, discover.load_extra_slugs(EXTRA_SLUGS))
    for ats, slugs in sorted(lists.items()):
        print(f"{ats:<11} {len(slugs):>6} entreprises")
    return 0


def cmd_run(args) -> int:
    today = date.today()
    http = HttpClient(config.USER_AGENT)
    ats_filter = set(args.ats.split(",")) if args.ats else None

    lists = discover.load_slug_lists(http, CACHE, today)
    lists = discover.merge_slugs(lists, discover.load_extra_slugs(EXTRA_SLUGS))
    if not any(lists.values()):
        print("Aucune entreprise à interroger (téléchargement des listes impossible ?).", file=sys.stderr)
        return 1

    state = store.load_state(STATE_FILE)
    prev = store.load_jobs(JOBS_FILE)
    use_cache = not args.no_cache
    targets = _targets(lists, ats_filter, args.limit, state, today, use_cache)
    print(f"[run] {len(targets)} boards à lire ({len(prev)} offres déjà connues)")

    ctx = Context(
        fetchers=build_fetchers(http), today=today, prev_records=prev,
        rejected_cache=state["rejected"], company_names=_load_names(), use_cache=use_cache,
    )
    workers = dict(config.WORKERS)
    if args.workers:
        workers = {a: args.workers for a in workers}
    outcomes = run_boards(ctx, targets, workers)

    # --- résumé -----------------------------------------------------------
    status = Counter(o.status for o in outcomes)
    reasons = Counter()
    for o in outcomes:
        reasons.update(o.stats)
    print(f"[run] boards : {dict(status)}")
    print("[run] décisions : " + ", ".join(f"{k}={v}" for k, v in reasons.most_common(10)))
    errors = status.get("error", 0)
    if outcomes and errors > config.MAX_ERROR_RATE * len(outcomes):
        print(f"[error] {errors}/{len(outcomes)} boards en erreur (réseau bloqué, limitation de débit, API modifiée ?). "
              f"Run non fiable : rien n'est écrit. Diagnostique avec `python -m gradjobs check --ats greenhouse --slug stripe`.",
              file=sys.stderr)
        return 2
    if outcomes and errors > 0.2 * len(outcomes):
        print(f"[warn] {errors}/{len(outcomes)} boards en erreur. Leurs offres restent inchangées (rien n'est fermé sur erreur).",
              file=sys.stderr)

    if args.dry_run:
        n = sum(len(o.accepted) for o in outcomes)
        print(f"[dry-run] {n} offres acceptées ; rien n'est écrit.")
        return 0

    # --- état + fusion + rendu ---------------------------------------------
    for o in outcomes:
        key = f"{o.ats}:{o.slug}"
        if o.status == "not_found":
            state["invalid"][key] = today.isoformat()
        elif o.status == "ok":
            state["invalid"].pop(key, None)
            state["rejected"].update(o.rejected)
    jobs = store.merge(prev, outcomes, today)
    store.save_jobs(JOBS_FILE, jobs, today)
    store.save_state(STATE_FILE, state)
    README.write_text(render_readme(jobs, today), encoding="utf-8")
    opened = sum(1 for j in jobs.values() if j["status"] == "open")
    print(f"[run] {opened} offres ouvertes, {len(jobs) - opened} fermées récemment -> README.md et data/jobs.json écrits")
    return 0


def cmd_check(args) -> int:
    """Lit UN board et explique la décision pour chaque offre : sert à régler les filtres."""
    http = HttpClient(config.USER_AGENT)
    ctx = Context(fetchers=build_fetchers(http), today=date.today(), use_cache=False,
                  company_names=_load_names())
    explain: list = []
    out = process_board(ctx, args.ats, args.slug, explain=explain)
    if out.status != "ok":
        print(f"{args.ats}:{args.slug} -> {out.status}"
              + ("  (slug inexistant chez cet ATS)" if out.status == "not_found"
                 else "  (erreur réseau / limitation de débit / réponse inattendue)"))
        return 1
    print(f"{args.ats}:{args.slug} -> {len(explain)} offres lues, {len(out.accepted)} acceptées")
    if args.explain:
        for job, verdict, reason in explain:
            locs = "; ".join(job.locations)[:60]
            print(f"  {verdict:<6} {job.title[:60]:<60} | {locs:<60} | {reason}")
    else:
        for rec in out.accepted:
            print(f"  {rec['region']:<16} {rec['title'][:60]:<60} {rec['url']}")
        print("  (ajoute --explain pour voir aussi les offres rejetées et pourquoi)")
    return 0


def cmd_render(args) -> int:
    today = date.today()
    jobs = store.load_jobs(JOBS_FILE)
    README.write_text(render_readme(jobs, today), encoding="utf-8")
    print(f"README.md régénéré depuis {len(jobs)} offres")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gradjobs", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="télécharge les listes d'entreprises")
    d.add_argument("--force", action="store_true", help="ignorer le cache")
    d.set_defaults(func=cmd_discover)

    r = sub.add_parser("run", help="lit les boards, filtre, met à jour data/jobs.json et README.md")
    r.add_argument("--ats", help="liste séparée par des virgules (défaut : tous)")
    r.add_argument("--limit", type=int, help="ne lire que les N premiers boards par ATS (test)")
    r.add_argument("--workers", type=int, help="threads par ATS (défaut : voir config.WORKERS)")
    r.add_argument("--dry-run", action="store_true", help="n'écrit rien")
    r.add_argument("--no-cache", action="store_true", help="ignorer les décisions et les 404 mémorisés")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("check", help="lit un seul board et explique les décisions")
    c.add_argument("--ats", required=True, choices=sorted(config.SLUG_LIST_URLS))
    c.add_argument("--slug", required=True)
    c.add_argument("--explain", action="store_true")
    c.set_defaults(func=cmd_check)

    g = sub.add_parser("render", help="régénère README.md depuis data/jobs.json")
    g.set_defaults(func=cmd_render)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())