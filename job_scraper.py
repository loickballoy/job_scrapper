#!/usr/bin/env python3
"""
job_scraper.py — Agrège les offres d'emploi depuis les APIs publiques
Greenhouse / Lever / Ashby, filtre par localisation + mots-clés de poste,
et ne remonte que les NOUVELLES offres depuis le dernier run (via SQLite).

Usage :
    python3 job_scraper.py                 # run normal, affiche les nouvelles offres
    python3 job_scraper.py --all            # affiche tout, pas juste les nouvelles
    python3 job_scraper.py --json out.json  # exporte aussi en JSON

Conçu pour tourner en cron/watcher sur un homelab (Docker fourni à côté).
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests

import os

DB_PATH = Path(os.environ.get("DB_DIR", str(Path(__file__).parent))) / "jobs_seen.sqlite3"

# ----------------------------------------------------------------------
# CONFIG — À ADAPTER : ajoute tes entreprises ici.
# Pour trouver le slug : va sur leur page carrière, regarde vers quoi ça
# redirige. Ex: boards.greenhouse.io/adyen -> slug = "adyen", ats = "greenhouse"
# ----------------------------------------------------------------------
COMPANIES = [
    # (nom affiché, ats, slug)
    ("Adyen", "greenhouse", "adyen"),
    ("ClickHouse", "greenhouse", "clickhouse"),
    # Exemples ci-dessous à vérifier/remplacer par les vrais slugs de tes cibles :
    # ("NomBoite", "lever", "slug-lever"),
    # ("NomBoite", "ashby", "slug-ashby"),
]

# Mots-clés de localisation à garder (insensible à la casse, match partiel)
LOCATION_KEYWORDS = [
    "amsterdam", "netherlands", "nederland",
    "zurich", "zürich", "geneva", "genève", "switzerland", "suisse",
    "london", "united kingdom", "uk",
    "toronto", "vancouver", "canada",
    "remote",
]

# Mots-clés de poste à garder (insensible à la casse, match partiel sur le titre)
TITLE_KEYWORDS = [
    "software engineer", "swe", "graduate", "new grad", "embedded",
    "c++", "low-latency", "low latency", "systems engineer",
    "performance engineer", "quant", "quantitative",
]

REQUEST_TIMEOUT = 15
SLEEP_BETWEEN_REQUESTS = 1.0  # politesse envers les APIs


# ----------------------------------------------------------------------
# Fetchers par ATS — chacun retourne une liste de dicts normalisés
# ----------------------------------------------------------------------

def fetch_greenhouse(company, slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    data = r.json()
    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "id": f"greenhouse:{slug}:{j['id']}",
            "company": company,
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "updated_at": j.get("updated_at", ""),
        })
    return jobs, None


def fetch_lever(company, slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    data = r.json()
    jobs = []
    for j in data:
        cat = j.get("categories", {}) or {}
        jobs.append({
            "id": f"lever:{slug}:{j.get('id')}",
            "company": company,
            "title": j.get("text", ""),
            "location": cat.get("location", ""),
            "url": j.get("hostedUrl", ""),
            "updated_at": str(j.get("createdAt", "")),
        })
    return jobs, None


def fetch_ashby(company, slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    data = r.json()
    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "id": f"ashby:{slug}:{j.get('id')}",
            "company": company,
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "url": j.get("jobUrl", ""),
            "updated_at": j.get("publishedAt", ""),
        })
    return jobs, None


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
}


# ----------------------------------------------------------------------
# Filtrage
# ----------------------------------------------------------------------

def matches_keywords(text, keywords):
    text_low = text.lower()
    return any(kw in text_low for kw in keywords)


def job_matches(job):
    loc_ok = matches_keywords(job["location"], LOCATION_KEYWORDS)
    title_ok = matches_keywords(job["title"], TITLE_KEYWORDS)
    return loc_ok and title_ok


# ----------------------------------------------------------------------
# SQLite : détecter les nouvelles offres entre deux runs
# ----------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            id TEXT PRIMARY KEY,
            company TEXT,
            title TEXT,
            location TEXT,
            url TEXT,
            first_seen_at INTEGER
        )
    """)
    conn.commit()
    return conn


def filter_new(conn, jobs):
    new_jobs = []
    now = int(time.time())
    for job in jobs:
        cur = conn.execute("SELECT 1 FROM seen_jobs WHERE id = ?", (job["id"],))
        if cur.fetchone() is None:
            new_jobs.append(job)
            conn.execute(
                "INSERT INTO seen_jobs (id, company, title, location, url, first_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                (job["id"], job["company"], job["title"], job["location"], job["url"], now),
            )
    conn.commit()
    return new_jobs


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Affiche toutes les offres matchées, pas juste les nouvelles")
    parser.add_argument("--json", type=str, help="Exporte aussi le résultat vers ce fichier JSON")
    args = parser.parse_args()

    conn = init_db()
    all_matched = []

    for company, ats, slug in COMPANIES:
        fetcher = FETCHERS.get(ats)
        if fetcher is None:
            print(f"[!] ATS inconnu pour {company}: {ats}", file=sys.stderr)
            continue

        jobs, error = fetcher(company, slug)
        if error:
            print(f"[!] {company} ({ats}:{slug}) — échec : {error}", file=sys.stderr)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        matched = [j for j in jobs if job_matches(j)]
        all_matched.extend(matched)
        print(f"[ok] {company}: {len(jobs)} offres totales, {len(matched)} matchent tes filtres")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    to_show = all_matched if args.all else filter_new(conn, all_matched)

    print(f"\n{'=== TOUTES LES OFFRES MATCHÉES ===' if args.all else '=== NOUVELLES OFFRES ==='}")
    if not to_show:
        print("(rien de nouveau)")
    for job in to_show:
        print(f"\n{job['company']} — {job['title']}")
        print(f"  📍 {job['location']}")
        print(f"  🔗 {job['url']}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(to_show, f, indent=2, ensure_ascii=False)
        print(f"\nExporté vers {args.json}")

    conn.close()


if __name__ == "__main__":
    main()