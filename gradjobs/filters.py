"""Décide si une offre est une offre graduate / early-career pertinente.

Ordre de décision (le moins cher d'abord, pour éviter de télécharger des descriptions inutiles) :
    prefilter()  : région -> titre senior -> stage -> pertinence du rôle      (pas de description)
    finalize()   : ancienneté -> expérience exigée -> signal débutant         (description)
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from . import config

# Bornes de mot "alphanumériques" (plus fiables que \b autour de "." ou "+").
B = r"(?<![A-Za-z0-9])"
E = r"(?![A-Za-z0-9])"


def _rx(pattern: str, flags: int = re.I) -> "re.Pattern[str]":
    return re.compile(pattern, flags)


# --------------------------------------------------------------------------- titres

# Mots toujours seniors.
STRONG_SENIOR_RX = _rx(
    rf"{B}(?:senior|sr\.?|(?<!technical )staff|principal|lead|head of|directors?|vp|vice president|"
    rf"architects?|distinguished|fellow|chief|expert){E}"
)
# Mots seniors seulement en l'absence de marqueur débutant explicite dans le titre
# ("Software Engineer 2 New Grad", "Founding Engineer - Early Careers" existent réellement).
WEAK_SENIOR_RX = _rx(
    rf"{B}(?:founding|managers?|mid[- ]?level|intermediate|experienced){E}"
    rf"|{B}(?:ii|iii|iv){E}"                                                # Engineer II / III / IV
    rf"|{B}(?:sde|swe|engineer|developer|level|l)\s*-?\s*(?:[2-9]|1\d){E}"     # SDE 2, Engineer 3, L4
)

INTERN_RX = _rx(
    r"(?<![A-Za-z])(?:interns?|internships?|werkstudent(?:in)?|working students?|praktik(?:um|ant(?:in)?)|"
    r"stagiaires?|stage|co-?op|apprentice(?:ship)?s?|alternance|placement year|industrial placement|"
    r"summer (?:analyst|student|associate)|(?:bachelor|master|diploma)(?:'s)? thesis|"
    r"masterarbeit|abschlussarbeit)(?![A-Za-z])"
)

EARLY_RX = _rx(
    rf"{B}(?:graduates?|(?:new[- ]?)?(?:college|university)[- ]?grad(?:uate)?s?|new[- ]?grads?|new[- ]?graduates?|"
    rf"entry[- ]?level|junior|jr\.?|early[- ]?careers?|"
    rf"campus|trainee|recent graduates?|rotational|grad(?:uate)? (?:programme?|scheme)|"
    rf"associate (?:software|systems?|firmware|embedded|backend|engineer|developer)|"
    rf"(?:engineer|developer|sde|swe)\s*-?\s*(?:0|i|1)){E}"
)

# --------------------------------------------------------------------------- rôle

ROLE_INCLUDE_RX = _rx(
    r"software|firmware|embedded|c\+\+|(?<![a-z])cpp(?![a-z])|back[- ]?end|front[- ]?end|full[- ]?stack|"
    r"platform|infrastructure|devops|(?<![a-z])sre(?![a-z])|site reliability|developer|programmer|"
    r"(?<![a-z])swe(?![a-z])|(?<![a-z])sde(?![a-z])|systems? (?:engineer|developer|software)|"
    r"security engineer|cyber|compiler|kernel|(?<![a-z])drivers?(?![a-z])|low[- ]latency|"
    r"performance engineer|machine learning engineer|(?<![a-z])ml engineer|data engineer|robotics|"
    r"test engineer|qa engineer|automation engineer|verification engineer|(?<![a-z])rtos(?![a-z])|linux"
)
# Un titre "… Engineer" sans mot technique est accepté seulement si le département est technique.
ENGINEER_RX = _rx(r"engineer")
TECH_DEPT_RX = _rx(
    r"engineering|software|technology|r&d|platform|infrastructure|security|data|tech\b|development"
)
ROLE_EXCLUDE_RX = _rx(
    r"sales|marketing|recruit(?:er|ing|ment)|talent (?:acquisition|partner|sourc\w+)|legal|counsel|finance|"
    r"accountant|accounting|human resources|"
    r"(?<![a-z])hr(?![a-z])|customer (?:success|support)|account (?:executive|manager)|"
    r"business (?:developer|development|analyst)|designer|copywriter|social media|paralegal|"
    r"procurement|supply chain|mechanical|civil engineer|chemical|biomedical|construction|nurse|clinical|"
    r"product manager|technical writer|content"
)

# --------------------------------------------------------------------------- description

_NUM = r"\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten"
_NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
RANGE_RX = _rx(rf"{B}({_NUM})\s*(?:-|–|—|to)\s*({_NUM})\s*\+?\s*(?:years?|yrs?){E}")
SINGLE_RX = _rx(rf"{B}({_NUM})\s*\+?\s*(?:years?|yrs?){E}")
ZERO_RX = _rx(
    r"no (?:prior |previous |professional |industry |commercial )?experience|"
    r"without (?:any )?(?:prior )?experience|(?<![0-9])(?:0|zero)\+?\s*(?:years?|yrs?)"
)
EXPERIENCE_CTX_RX = _rx(
    r"experience|exp\.|working (?:in|with|as)|worked|professional|industry|background|hands[- ]on|"
    r"track record|proven|in a (?:similar|related|relevant)|in (?:software|engineering|development)"
)
UPPER_BOUND_RX = _rx(r"(?:up to|less than|fewer than|under|max(?:imum)?(?: of)?|within|no more than)\s*$")
NOT_REQUIRED_RX = _rx(r"^.{0,60}?(?:preferred|desirable|a plus|nice to have|bonus|advantage|ideally|combined|collective)")
OPTIONAL_BEFORE_RX = _rx(r"(?:ideally|preferably|optionally)\s*(?:\w+\s+){0,2}$")

EARLY_PHRASES_RX = _rx(
    r"entry[- ]level|new[- ]grad(?:uate)?s?|recent(?:ly)? graduat(?:e|es|ed)|early[- ]career|"
    r"graduating (?:in|by|this)|final[- ]year|fresh graduates?|graduate (?:program|programme|scheme|role|position)|"
    r"no (?:prior|previous) (?:professional )?experience|(?<![0-9])0\s*[-–]\s*\d+\s*years|"
    r"(?<![0-9])0\+?\s*years"
)

# --- drapeaux (heuristiques, à titre indicatif) ---
NO_SPONSOR_RX = _rx(
    r"(?:will not|won't|unable to|cannot|can't|do not|does not|not able to|not in a position to)\s+"
    r"(?:provide|offer|sponsor|support)\w*\s+(?:any\s+)?(?:work\s+|employment\s+)?(?:visa\s+)?sponsorship|"
    r"(?:will not|won't|unable to|cannot|can't|do not|does not)\s+sponsor\w*\s+(?:work\s+|employment\s+)?visas?|"
    r"no (?:visa )?sponsorship|without (?:the need for )?(?:visa )?sponsorship|"
    r"must (?:already )?(?:be|have) (?:legally )?(?:authori[sz]ed|eligible|the right) to work"
)
CLEARANCE_RX = _rx(
    r"security clearance|u\.?s\.? citizen(?:ship)?|(?<![a-z])itar(?![a-z])|top secret|ts/sci|"
    r"u\.?s\.? persons?"
)
RELOCATION_RX = _rx(r"relocation (?:support|assistance|package|budget|allowance|help|bonus)")
_LANGS = ("german|dutch|french|swedish|norwegian|danish|finnish|italian|spanish|portuguese|"
          "polish|mandarin|cantonese|japanese|korean|arabic")
LANG_A_RX = _rx(
    rf"(?:fluent|native|proficien(?:t|cy)|business[- ]level|working knowledge|(?<![a-z])c1(?![a-z0-9])|"
    rf"(?<![a-z])c2(?![a-z0-9]))\W+(?:\w+\W+){{0,4}}?{B}({_LANGS}){E}"
)
LANG_B_RX = _rx(
    rf"{B}({_LANGS}){E}\W+(?:\w+\W+){{0,4}}?(?:fluent|native|required|mandatory|proficien(?:t|cy)|"
    rf"(?<![a-z])c1(?![a-z0-9])|(?<![a-z])c2(?![a-z0-9]))"
)
LANG_OPTIONAL_RX = _rx(r"^.{0,50}?(?:a plus|nice to have|preferred|bonus|advantage|is an asset|desirable)")


# --------------------------------------------------------------------------- utilitaires

_TAG_BREAK_RX = re.compile(r"<\s*(?:br|/p|/li|/h\d|/div|/ul|/ol)\s*/?>", re.I)
_TAG_RX = re.compile(r"<[^>]+>")


def clean_text(raw: str) -> str:
    """HTML (parfois échappé deux fois, cas Greenhouse) -> texte brut."""
    if not raw:
        return ""
    s = raw
    for _ in range(2):                       # &lt;p&gt; -> <p>
        if "<" in s:
            break
        s = html.unescape(s)
    s = _TAG_BREAK_RX.sub("\n", s)
    s = _TAG_RX.sub(" ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v\u00a0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def _to_int(tok: str) -> int:
    return int(tok) if tok.isdigit() else _NUMWORDS[tok.lower()]


def min_years_required(text: str) -> Optional[int]:
    """Plus grande exigence d'expérience trouvée (borne basse des fourchettes), ou None.

    Heuristique : un nombre d'années compte seulement s'il est près du mot "experience",
    n'est pas une borne haute ("up to 2 years") et n'est pas marqué optionnel ("preferred").
    """
    if not text:
        return None
    found: List[int] = []
    taken: List[tuple] = []

    def consider(m: "re.Match[str]", value: int) -> None:
        s, e = m.span()
        ctx = text[max(0, s - 100): e + 100]
        if not EXPERIENCE_CTX_RX.search(ctx):
            return
        if UPPER_BOUND_RX.search(text[max(0, s - 25): s]):
            return
        if NOT_REQUIRED_RX.search(text[e: e + 80]) or OPTIONAL_BEFORE_RX.search(text[max(0, s - 30): s]):
            return
        found.append(value)

    for m in RANGE_RX.finditer(text):
        taken.append(m.span())
        consider(m, _to_int(m.group(1)))
    for m in SINGLE_RX.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
        consider(m, _to_int(m.group(1)))

    if found:
        return max(found)
    return 0 if ZERO_RX.search(text) else None


def has_early_phrase(text: str) -> bool:
    return bool(text and EARLY_PHRASES_RX.search(text))


def compute_flags(text: str) -> List[str]:
    flags: List[str] = []
    if not text:
        return flags
    if NO_SPONSOR_RX.search(text):
        flags.append("🛂")
    if CLEARANCE_RX.search(text):
        flags.append("🇺🇸")
    langs = set()
    for rx in (LANG_A_RX, LANG_B_RX):
        for m in rx.finditer(text):
            if LANG_OPTIONAL_RX.search(text[m.end(): m.end() + 60]):
                continue
            langs.add(m.group(1).capitalize())
    if langs:
        flags.append("🗣️ " + "/".join(sorted(langs)))
    if RELOCATION_RX.search(text):
        flags.append("✈️")
    return flags


# --------------------------------------------------------------------------- régions

_REGIONS_COMPILED = None


def _regions():
    global _REGIONS_COMPILED
    if _REGIONS_COMPILED is None:
        _REGIONS_COMPILED = [
            (name, emoji, re.compile(pattern, re.I))
            for name, emoji, pattern in config.REGIONS
            if name in config.ENABLED_REGIONS
        ]
    return _REGIONS_COMPILED


def reset_region_cache() -> None:
    """À appeler si on change config.ENABLED_REGIONS / config.REGIONS à chaud (tests)."""
    global _REGIONS_COMPILED
    _REGIONS_COMPILED = None


def region_of(locations: List[str]) -> Optional[str]:
    text = " ; ".join(l for l in locations if l)
    if not text:
        return None
    for name, _emoji, rx in _regions():
        if rx.search(text):
            return name
    return None


def region_emoji(name: str) -> str:
    for n, emoji, _ in config.REGIONS:
        if n == name:
            return emoji
    return ""


# --------------------------------------------------------------------------- décision

def title_level(title: str) -> str:
    """'senior' | 'intern' | 'early' | 'neutral' (l'ordre est volontairement conservateur)."""
    if STRONG_SENIOR_RX.search(title):
        return "senior"
    if INTERN_RX.search(title):
        return "intern"
    if EARLY_RX.search(title):
        return "early"                       # un marqueur débutant explicite l'emporte sur les mots seniors faibles
    if WEAK_SENIOR_RX.search(title):
        return "senior"
    return "neutral"


_HEAD_SPLIT_RX = re.compile(r"\s[-–—|]\s|,|\(|:")


def _title_head(title: str) -> str:
    """Début du titre, avant le premier séparateur : 'Software Engineer 1 - Rights & Accounting' -> 'Software Engineer 1'."""
    return _HEAD_SPLIT_RX.split(title, maxsplit=1)[0]


def is_relevant_role(title: str, department: str = "") -> bool:
    # L'exclusion ne regarde que le début du titre : le nom d'une équipe après le tiret
    # ("... - Rights & Accounting") ne doit pas disqualifier un vrai poste d'ingénieur logiciel.
    if ROLE_EXCLUDE_RX.search(_title_head(title)):
        return False
    if ROLE_INCLUDE_RX.search(title):
        return True
    return bool(ENGINEER_RX.search(title) and department and TECH_DEPT_RX.search(department))


@dataclass
class Prefilter:
    region: Optional[str] = None
    level: str = "neutral"
    reject: Optional[str] = None


@dataclass
class Decision:
    accepted: bool
    reason: str
    level_via: str = ""          # "title" | "description"
    years: Optional[int] = None
    flags: List[str] = field(default_factory=list)


def prefilter(job) -> Prefilter:
    """Filtres qui n'ont pas besoin de la description."""
    region = region_of(job.locations)
    if region is None:
        return Prefilter(reject="location")
    level = title_level(job.title)
    if level == "senior":
        return Prefilter(region=region, level=level, reject="senior title")
    if level == "intern" and not config.INCLUDE_INTERNSHIPS:
        return Prefilter(region=region, level=level, reject="internship")
    if not is_relevant_role(job.title, job.department):
        return Prefilter(region=region, level=level, reject="role")
    return Prefilter(region=region, level=level)


def finalize(job, pre: Prefilter, today: Optional[date] = None) -> Decision:
    """Filtres qui utilisent la description (déjà chargée dans job.description)."""
    today = today or date.today()
    if job.posted and (today - job.posted).days > config.MAX_POSTING_AGE_DAYS:
        return Decision(False, "stale posting")

    text = clean_text(job.description)
    years = min_years_required(text)
    flags = compute_flags(text)

    if years is not None and years > config.MAX_YEARS_REQUIRED:
        return Decision(False, f"requires {years}+ years", years=years, flags=flags)

    if pre.level in ("early", "intern"):
        return Decision(True, "early-career title", "title", years, flags)

    # Titre neutre : il faut une preuve dans la description.
    if has_early_phrase(text) or (years is not None and years <= config.MAX_YEARS_REQUIRED):
        return Decision(True, "early-career signal in description", "description", years, flags + ["🔎"])
    if config.INCLUDE_UNSPECIFIED_LEVEL:
        return Decision(True, "level unspecified (included by config)", "description", years, flags + ["🔎"])
    return Decision(False, "no early-career signal", years=years, flags=flags)