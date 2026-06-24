"""Structured candidate profile extraction for VPS local search.

The VPS search layer uses this module to turn cached scorecards or raw resume
text into cheap, queryable signals: years, location, languages, and skills.
These signals are intentionally conservative; Gemini scorecards remain the
final authority for strict result filtering.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Optional

from search_criteria import (
    KNOWN_PLACES,
    SPOKEN_LANGUAGES,
    SearchCriteria,
    _location_match,
    _norm,
    _parse_years_string,
    evaluate_criteria,
)


UNKNOWN_LOCATION_VALUES = {
    "",
    "n/a",
    "na",
    "none",
    "unknown",
    "not available",
    "not provided",
    "not specified",
    "not mentioned",
    "not disclosed",
}

LANGUAGE_UNCERTAIN_TOKENS = {
    "implied", "assumed", "inferred", "not provided", "not specified",
    "not mentioned", "n/a", "na", "unknown",
}

SKILL_NOISE_VALUES = {
    "", "n/a", "na", "none", "not applicable", "not provided",
    "not specified", "unknown",
}

LOCATION_CONTACT_RE = re.compile(
    r"\b(?:phone|mobile|email|e-mail|contact|telephone|tel|call|calls|"
    r"whatsapp|number)\b",
    re.IGNORECASE,
)

COMMON_SKILLS = {
    # Software / data
    "python", "java", "javascript", "typescript", "react", "angular",
    "vue", "node", "django", "flask", "fastapi", "spring", "sql",
    "postgresql", "mysql", "mongodb", "redis", "aws", "azure", "gcp",
    "docker", "kubernetes", "terraform", "linux", "git", "ci/cd",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn",
    "power bi", "tableau", "excel", "data analysis", "data science",
    # Finance / accounting
    "accounting", "accounts payable", "accounts receivable", "payroll",
    "financial reporting", "bank reconciliation", "general ledger",
    "tally", "quickbooks", "sap", "sap fico", "vat", "audit",
    "auditing", "budgeting", "forecasting", "invoicing",
    # HR / operations / sales
    "recruitment", "talent acquisition", "hr operations", "onboarding",
    "employee relations", "performance management", "customer service",
    "sales", "crm", "lead generation", "digital marketing",
    "project management", "procurement", "inventory", "logistics",
}


def parse_years(value: Any) -> Optional[float]:
    """Parse years from scorecard/text values."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"unknown", "not provided", "not specified", "n/a"}:
        return None
    if "less than" in text and re.search(r"\b1\s+year", text):
        return 0.5

    years = None
    explicit_years = re.search(r"(\d{1,2}(?:\.\d+)?)\s*(?:years?|yrs?)\b", text)
    if explicit_years:
        try:
            years = float(explicit_years.group(1))
        except ValueError:
            years = None
    if years is None:
        years = _parse_years_string(text)
    months = None
    m = re.search(r"(\d{1,2})\s*(?:months?|mos?)\b", text)
    if m:
        try:
            months = int(m.group(1)) / 12.0
        except ValueError:
            months = None
    if years is not None and months is not None and "year" in text:
        return round(years + months, 2)
    if years is not None:
        return years
    if months is not None:
        return round(months, 2)
    return None


def clean_location(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if any(x in lowered for x in ("not specified", "not provided", "not mentioned")):
        return ""
    text = re.sub(
        r"\([^)]*(?:implied|assumed|inferred|phone|mobile|email|contact|"
        r"number|work experience|based on)[^)]*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = LOCATION_CONTACT_RE.split(text, maxsplit=1)[0]
    text = re.split(
        r"\.\s+(?:with|having|i\s+am|and|my|over|more|through|for)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.split(r"[\n\r;|]", text, maxsplit=1)[0]
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    normed = _norm(cleaned)
    if normed in UNKNOWN_LOCATION_VALUES:
        return ""
    return normed


def _dedupe(items: list[str], limit: int = 80) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = _norm(str(item))
        if not value or value in seen or value in SKILL_NOISE_VALUES:
            continue
        if len(value) <= 1:
            continue
        seen.add(value)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _dedupe_languages(items: list[str], limit: int = 20) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    languages = sorted(SPOKEN_LANGUAGES, key=len, reverse=True)
    for item in items:
        value = _norm(str(item))
        if not value or _is_uncertain_language_value(value):
            continue
        for lang in languages:
            if re.search(rf"\b{re.escape(lang)}\b", value):
                if lang not in seen:
                    seen.add(lang)
                    out.append(lang)
                break
        if len(out) >= limit:
            break
    return out


def _is_uncertain_language_value(value: str) -> bool:
    return any(token in _norm(value) for token in LANGUAGE_UNCERTAIN_TOKENS)


def _uncertain_language_context(text: str, start: int, end: int) -> bool:
    context = text[max(0, start - 24): min(len(text), end + 40)]
    return _is_uncertain_language_value(context)


def _flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, str):
        out.extend(x.strip() for x in re.split(r"[,;/]|\s+and\s+", value) if x.strip())
    elif isinstance(value, list):
        for item in value:
            out.extend(_flatten_strings(item))
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(_flatten_strings(item))
    else:
        out.append(str(value))
    return out


def extract_languages_from_text(text: str) -> list[str]:
    lower = (text or "").lower()
    found: list[str] = []

    # Prefer explicit language sections to avoid treating every English resume
    # as a language-certified candidate.
    for m in re.finditer(
        r"(?:languages?|known languages?|language proficiency)\s*[:\-]\s*([^\n\r]{0,180})",
        lower,
    ):
        segment = m.group(1)
        for part in re.split(r"[,;/]|\s+and\s+", segment):
            if _is_uncertain_language_value(part):
                continue
            for lang in SPOKEN_LANGUAGES:
                if re.search(rf"\b{re.escape(lang)}\b", part):
                    found.append(lang)

    # Non-English language mentions are useful even outside a language section.
    for lang in SPOKEN_LANGUAGES:
        if lang == "english":
            continue
        for m in re.finditer(rf"\b{re.escape(lang)}\b", lower):
            if not _uncertain_language_context(lower, m.start(), m.end()):
                found.append(lang)
                break
    return _dedupe_languages(found)


def extract_location_from_text(text: str) -> str:
    head = (text or "")[:5000]
    for pat in (
        r"(?:current\s+)?location\s*[:\-]\s*([A-Za-z][A-Za-z .,\-]{2,80})",
        r"(?:address|residence|based\s+in|located\s+in|residing\s+in)\s*[:\-]?\s*([A-Za-z][A-Za-z .,\-]{2,80})",
    ):
        m = re.search(pat, head, re.IGNORECASE)
        if m:
            loc = clean_location(m.group(1))
            if loc:
                return loc

    lower = head.lower()
    places = sorted(KNOWN_PLACES, key=len, reverse=True)
    for place in places:
        if re.search(rf"\b{re.escape(place)}\b", lower):
            return _norm(place)
    return ""


def extract_years_from_text(text: str) -> Optional[float]:
    lower = (text or "").lower()
    candidates: list[float] = []
    for m in re.finditer(r"\b(\d{1,2}(?:\.\d+)?)\+?\s*(?:years?|yrs?)\b", lower):
        start, end = max(0, m.start() - 60), min(len(lower), m.end() + 60)
        context = lower[start:end]
        if not re.search(r"experience|professional|work|career|employment|exp", context):
            continue
        try:
            val = float(m.group(1))
        except ValueError:
            continue
        if 0 <= val <= 45:
            candidates.append(val)
    return max(candidates) if candidates else None


def extract_skills_from_text(text: str) -> list[str]:
    lower = (text or "").lower()
    found = []
    for skill in COMMON_SKILLS:
        if re.search(rf"\b{re.escape(skill)}\b", lower):
            found.append(skill)
    return _dedupe(found)


def profile_from_text(text: str, source: str = "text") -> dict[str, Any]:
    return {
        "candidate_years": extract_years_from_text(text),
        "candidate_location": extract_location_from_text(text),
        "candidate_languages": extract_languages_from_text(text),
        "candidate_skills": extract_skills_from_text(text),
        "profile_source": source,
    }


def _scorecard_from_analysis(gemini_analysis: Any) -> dict[str, Any]:
    if isinstance(gemini_analysis, str):
        try:
            gemini_analysis = json.loads(gemini_analysis)
        except Exception:
            return {}
    if not isinstance(gemini_analysis, dict):
        return {}
    sc = gemini_analysis.get("hr_scorecard") or gemini_analysis.get("scorecard") or {}
    return sc if isinstance(sc, dict) else {}


def profile_from_analysis(gemini_analysis: Any) -> dict[str, Any]:
    sc = _scorecard_from_analysis(gemini_analysis)
    if not sc:
        return {
            "candidate_years": None,
            "candidate_location": "",
            "candidate_languages": [],
            "candidate_skills": [],
            "profile_source": "analysis_empty",
        }

    co = sc.get("candidate_overview") or {}
    years = parse_years(
        co.get("experience_years")
        or co.get("total_experience")
        or co.get("years_of_experience")
    )
    location = clean_location(co.get("location") or "")

    languages = []
    detailed = sc.get("detailed_analysis") or {}
    languages.extend(_flatten_strings(detailed.get("languages")))

    skills = []
    for block in (
        co,
        detailed,
        sc.get("keyword_coverage") or {},
    ):
        if not isinstance(block, dict):
            continue
        for key in (
            "skills", "key_skills", "primary_skills", "technical_skills",
            "core_skills", "skills_matched", "matched_skills", "tools",
            "tools_technologies", "technologies", "tech_stack",
            "programming_languages", "frameworks", "matched_keywords",
            "keywords",
        ):
            skills.extend(_flatten_strings(block.get(key)))

    timeline = sc.get("career_timeline") or []
    if isinstance(timeline, list):
        for item in timeline:
            if isinstance(item, dict):
                skills.extend(_flatten_strings(item.get("key_skills")))

    return {
        "candidate_years": years,
        "candidate_location": location,
        "candidate_languages": _dedupe_languages(languages),
        "candidate_skills": _dedupe(skills),
        "profile_source": "cache",
    }


def merge_profiles(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary or {})
    for key in ("candidate_years", "candidate_location"):
        if not merged.get(key):
            merged[key] = (fallback or {}).get(key)
    merged["candidate_languages"] = _dedupe_languages(
        list(merged.get("candidate_languages") or [])
        + list((fallback or {}).get("candidate_languages") or [])
    )
    merged["candidate_skills"] = _dedupe(
        list(merged.get("candidate_skills") or [])
        + list((fallback or {}).get("candidate_skills") or [])
    )
    if not merged.get("profile_source"):
        merged["profile_source"] = (fallback or {}).get("profile_source") or "unknown"
    return merged


def profile_from_row(row: dict[str, Any]) -> dict[str, Any]:
    years = row.get("candidate_years")
    if isinstance(years, Decimal):
        years = float(years)
    elif not isinstance(years, (int, float)):
        years = parse_years(years)
    profile = {
        "candidate_years": years,
        "candidate_location": clean_location(row.get("candidate_location")),
        "candidate_languages": _dedupe_languages(list(row.get("candidate_languages") or [])),
        "candidate_skills": _dedupe(list(row.get("candidate_skills") or [])),
        "profile_source": row.get("profile_source") or "",
    }
    if not any(profile.get(k) for k in ("candidate_years", "candidate_location", "candidate_languages", "candidate_skills")):
        profile = profile_from_text(row.get("text") or "", source="text_runtime")
    return profile


def profile_to_analysis(profile: dict[str, Any]) -> dict[str, Any]:
    years = profile.get("candidate_years")
    years_text = f"{years:g} Years" if isinstance(years, (int, float)) else None
    skills = profile.get("candidate_skills") or []
    return {
        "hr_scorecard": {
            "candidate_overview": {
                "experience_years": years_text,
                "location": profile.get("candidate_location") or "",
                "skills": skills,
            },
            "detailed_analysis": {
                "languages": profile.get("candidate_languages") or [],
                "technical_skills": skills,
                "skills": skills,
            },
            "keyword_coverage": {
                "matched_keywords": skills,
            },
        }
    }


def evaluate_profile(profile: dict[str, Any], criteria: SearchCriteria) -> tuple[dict[str, Any], str]:
    if not criteria or criteria.is_empty():
        return {"evaluated": False, "matches": [], "misses": []}, "no_criteria"

    ev = evaluate_criteria(profile_to_analysis(profile), criteria)
    if not ev.get("misses"):
        return ev, "exact"

    known_fail = bool(ev.get("hard_fail"))
    for miss in ev.get("misses") or []:
        criterion = miss.get("criterion")
        if criterion == "experience_years" and profile.get("candidate_years") is not None:
            known_fail = True
        elif criterion == "location" and profile.get("candidate_location"):
            known_fail = True
        elif criterion == "language" and profile.get("candidate_languages"):
            known_fail = True
        elif criterion == "skill" and profile.get("candidate_skills"):
            known_fail = True
    return ev, "known_fail" if known_fail else "unknown"


def profile_matches_location(profile_location: str, wanted_locations: list[str]) -> bool:
    if not profile_location:
        return False
    return any(_location_match(want, profile_location) for want in wanted_locations if want)
