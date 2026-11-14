"""
Hard search criteria parsing and post-filtering.

Extracts structured criteria from a free-text recruiter query:
- Minimum years of experience (e.g., "5+ years", "minimum 3 years")
- Required spoken languages (e.g., "speaks French", "Arabic and English")
- Required location (e.g., "based in Dubai", "located in Mumbai", "Remote")

Applies penalties / criteria_match metadata to Gemini scorecard results so the
front-end can show why a candidate matched or missed.

This is deliberately defensive by default: normal ranking applies heavy
penalties and flags misses. Candidate-search endpoints can opt into strict
mode when the product contract is "only return exact criteria matches."
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from services import requirements_logic


# Penalty (in score points) per missed criterion. Tuned so that missing
# *one* hard criterion knocks a candidate out of the "strong fit" band.
PENALTY_PER_MISS = 25

# Cap for proportional years penalty so a 1-year shortfall isn't punished
# the same as a 10-year shortfall.
PENALTY_YEARS_PER_YEAR = 8   # 8 points per missing year of experience
PENALTY_YEARS_MAX = 30       # never deduct more than 30 for years alone

# Over-experience (candidate exceeds the requested max_years) is treated
# more strictly than under-experience: someone asking for a 3-5y mid-level
# role rarely wants an 11-year senior, so we penalise the overshoot harder.
PENALTY_OVER_YEARS_PER_YEAR = 18
PENALTY_OVER_YEARS_MAX = 100
# Severe overshoot threshold: any candidate whose years exceed
# `max_years + OVER_YEARS_HARD_FAIL_GAP` is hard-failed and removed from
# the result list entirely (e.g. asking 2-5y and getting an 11-year senior).
OVER_YEARS_HARD_FAIL_GAP = 2

# Bidirectional location synonyms: any token in a set matches any other.
# Token-overlap already handles "Dubai" <-> "Dubai, UAE". Synonym sets are
# kept narrow so that, e.g., wanting "Dubai" does NOT match "Sharjah, UAE":
# we group only true aliases of the SAME place (city aliases, or country
# aliases), never city<->country chains.
LOCATION_SYNONYMS = [
    # Country aliases only.
    {"uae", "united arab emirates", "emirates"},
    {"ksa", "saudi", "saudi arabia", "kingdom of saudi arabia"},
    {"usa", "united states", "united states of america", "u.s.", "u.s.a.", "america"},
    {"uk", "united kingdom", "great britain", "britain", "gb"},
    {"india", "bharat", "hindustan"},
    # City aliases only (old and new names of the same place).
    {"bombay", "mumbai"},
    {"bengaluru", "bangalore"},
    {"calcutta", "kolkata"},
    {"madras", "chennai"},
    {"gurgaon", "gurugram"},
    # Special bucket for remote work.
    {"remote", "anywhere", "work from home", "wfh"},
]

# Country -> cities mapping. ONE-WAY: a query asking for the country also
# matches candidates in any of its known cities. (The reverse is not true:
# asking for "Dubai" should NOT match a candidate whose location is just
# "UAE" without any city specified -- that's handled in `_location_match`.)
LOCATION_COUNTRY_CITIES: dict[str, set[str]] = {
    "uae": {"dubai", "abu dhabi", "sharjah", "ajman", "fujairah",
            "ras al khaimah", "umm al quwain"},
    "saudi arabia": {"riyadh", "jeddah", "dammam", "mecca", "medina",
                     "khobar", "tabuk", "abha"},
    "ksa": {"riyadh", "jeddah", "dammam", "mecca", "medina"},
    # India: major cities AND state names (so "Dewas, Madhya Pradesh"
    # registers as in-India).
    "india": {
        # Cities
        "bangalore", "bengaluru", "hyderabad", "chennai", "mumbai",
        "pune", "delhi", "new delhi", "gurgaon", "gurugram", "noida",
        "kolkata", "ahmedabad", "kochi", "trivandrum",
        "thiruvananthapuram", "coimbatore", "jaipur", "lucknow",
        "indore", "bhopal", "nagpur", "surat", "vadodara", "chandigarh",
        "dewas", "vizag", "visakhapatnam", "vijayawada", "mysuru",
        "mysore", "madurai", "nashik", "thane", "navi mumbai",
        # States / UTs
        "maharashtra", "karnataka", "tamil nadu", "telangana",
        "andhra pradesh", "kerala", "madhya pradesh", "uttar pradesh",
        "west bengal", "gujarat", "rajasthan", "punjab", "haryana",
        "bihar", "odisha", "assam", "jharkhand", "chhattisgarh",
        "uttarakhand", "himachal pradesh", "goa",
    },
    "uk": {"london", "manchester", "birmingham", "leeds", "glasgow",
           "edinburgh", "liverpool", "bristol", "sheffield", "cardiff",
           "belfast"},
    "united kingdom": {"london", "manchester", "birmingham", "leeds",
                       "glasgow", "edinburgh", "liverpool", "bristol"},
    "usa": {"new york", "san francisco", "seattle", "austin",
            "chicago", "boston", "los angeles", "atlanta", "denver",
            "miami", "dallas", "houston", "philadelphia", "phoenix"},
    "united states": {"new york", "san francisco", "seattle", "austin",
                      "chicago", "boston", "los angeles", "atlanta"},
    "canada": {"toronto", "vancouver", "montreal", "ottawa", "calgary",
               "edmonton"},
    "australia": {"sydney", "melbourne", "brisbane", "perth",
                  "adelaide", "canberra"},
    "pakistan": {"karachi", "lahore", "islamabad", "rawalpindi",
                 "faisalabad", "multan", "peshawar"},
    "bangladesh": {"dhaka", "chittagong", "chattogram", "sylhet"},
    "sri lanka": {"colombo", "kandy", "galle"},
    "egypt": {"cairo", "alexandria", "giza"},
    "qatar": {"doha", "al rayyan"},
    "bahrain": {"manama", "riffa"},
    "kuwait": {"kuwait city", "hawalli", "farwaniya"},
    "oman": {"muscat", "salalah", "sohar"},
    "germany": {"berlin", "munich", "hamburg", "frankfurt", "cologne",
                "stuttgart"},
    "france": {"paris", "lyon", "marseille", "toulouse", "nice"},
    "netherlands": {"amsterdam", "rotterdam", "the hague", "utrecht"},
    "singapore": {"singapore"},
    "ireland": {"dublin", "cork", "galway"},
}

# Known place names used as a *fallback* when no preposition-based pattern
# matches. Lets short queries like "5 years and india" still extract a
# location. Kept conservative to avoid false positives on common words.
KNOWN_PLACES = {
    # Countries / regions
    "india", "usa", "uk", "uae", "ksa", "singapore", "qatar", "bahrain",
    "kuwait", "oman", "egypt", "canada", "australia", "germany", "france",
    "spain", "italy", "netherlands", "ireland", "japan", "china",
    "philippines", "pakistan", "bangladesh", "srilanka", "sri lanka",
    # Major cities recruiters target
    "bangalore", "bengaluru", "hyderabad", "chennai", "mumbai", "pune",
    "delhi", "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad",
    "dubai", "abu dhabi", "sharjah", "riyadh", "jeddah", "dammam",
    "doha", "manama", "london", "manchester", "birmingham", "dublin",
    "new york", "san francisco", "seattle", "austin", "chicago", "boston",
    "toronto", "vancouver", "berlin", "munich", "paris", "amsterdam",
    "sydney", "melbourne", "singapore city", "hong kong", "tokyo",
    "karachi", "lahore", "islamabad", "colombo", "dhaka",
}

# Known spoken / written languages. Keep conservative -- only entries that
# rarely collide with skills/locations.
SPOKEN_LANGUAGES = {
    "english", "spanish", "french", "german", "italian", "portuguese",
    "arabic", "hindi", "urdu", "punjabi", "bengali", "tamil", "telugu",
    "marathi", "gujarati", "malayalam", "kannada", "mandarin", "chinese",
    "cantonese", "japanese", "korean", "russian", "dutch", "polish",
    "turkish", "vietnamese", "thai", "indonesian", "malay", "filipino",
    "tagalog", "swahili", "hebrew", "persian", "farsi", "greek",
    "czech", "swedish", "norwegian", "danish", "finnish", "romanian",
    "hungarian", "ukrainian",
}


@dataclass
class SearchCriteria:
    min_years: Optional[int] = None
    max_years: Optional[int] = None
    required_languages: list[str] = field(default_factory=list)
    location: Optional[str] = None  # canonical lower-case form (primary)
    # Additional OR'd locations when the query lists alternatives, e.g.
    # "Dubai or Abu Dhabi". Candidate matches if `location` OR any of
    # these alternatives matches.
    location_alternatives: list[str] = field(default_factory=list)
    # Hard-required skills extracted from "must have", "required:",
    # "mandatory" phrasings. Compared (substring, case-insensitive)
    # against the candidate's skills section.
    required_skills: list[str] = field(default_factory=list)
    language_expression: Optional[dict] = None
    skill_expression: Optional[dict] = None

    def is_empty(self) -> bool:
        return (self.min_years is None
                and self.max_years is None
                and not self.required_languages
                and not self.location
                and not self.location_alternatives
                and not self.required_skills
                and self.language_expression is None
                and self.skill_expression is None)

    def all_locations(self) -> list[str]:
        """Primary + alternatives as a deduplicated list."""
        out: list[str] = []
        if self.location:
            out.append(self.location)
        for alt in self.location_alternatives:
            if alt and alt not in out:
                out.append(alt)
        return out

    def to_dict(self) -> dict:
        return asdict(self)


_YEARS_PATTERNS = [
    # "5+ years", "10 + yrs", "5+y", "10+yr"
    r"(\d{1,3})\s*\+\s*(?:years?|yrs?|y)\b",
    # "5y+", "10yr+"
    r"(\d{1,3})\s*(?:years?|yrs?|y)\s*\+",
    # "minimum 3 years", "at least 4 yrs", "min 5 years", ">=5 years"
    r"(?:minimum|at\s*least|min\.?|>=|more\s+than|over)\s*(\d{1,3})\s*(?:years?|yrs?|y)\b",
    # "3-5 years", "3 to 5 yrs" -- take the LOWER bound as the minimum
    r"(\d{1,3})\s*(?:-|\u2013|\u2014|to)\s*\d{1,3}\s*(?:years?|yrs?|y)\b",
    # "5 years of experience", "3 yrs experience"
    r"(\d{1,3})\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
    # "5 years" / "5 yrs" as a bare phrase (lower priority -- last resort)
    r"(\d{1,3})\s*(?:years?|yrs?)\b",
    # "5 ans" (French)
    r"(\d{1,3})\s*ans?\b",
]

# Phrases that imply "zero years required" (entry-level / fresher).
_FRESHER_PATTERNS = [
    r"\bfresher\b",
    r"\bfresh\s+graduate\b",
    r"\bentry[-\s]level\b",
    r"\bno\s+experience\s+(?:required|needed)?\b",
]


_LANG_PATTERNS = [
    # "speaks French and Arabic", "fluent in Spanish, English", "must speak French"
    r"(?:speaks?|speaking|fluent\s+in|fluency\s+in|proficient\s+in|knows?|must\s+speak|should\s+speak|native\s+in|native\s+speakers?\s+of)\s+([A-Za-z(][A-Za-z,&/() ]+?)(?=[.;:]|\s+(?:based|located|residing|living|with|having|who|that|in\s+the|preferred|required|only|mandatory)\b|$)",
    # "Arabic-speaking", "French speaking candidate", "Arabic native"
    r"\b([A-Za-z]+)[- ]speaking\b",
    r"\b([A-Za-z]+)\s+native\b",
    # "languages: english, french", "language requirement: french"
    r"languages?(?:\s+requirements?)?\s*[:=]\s*([A-Za-z,&/() ]+?)(?=[.;]|$)",
]


_LOCATION_END = r"(?=[.,;()\[\]]|\s+(?:and|or|with|who|having|but|not|excluding|requiring|skills?|experience|speaks?|fluent)\b|$)"
_LOCATION_PATTERNS = [
    # "based in X", "located in X", "living in X"
    r"\b(?:based|located|residing|living|stationed|headquartered)\s+in\s+([A-Za-z][A-Za-z .\-]+?)" + _LOCATION_END,
    # "Dubai-based", "London based" -- case-sensitive on the leading caps to
    # avoid matching "candidate must be based" / "be based" phrasing.
    r"(?-i:\b([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+){0,2}))[- ]based\b(?!\s+in\b)",
    # "in the UAE", "in the United States"
    r"\bin\s+the\s+([A-Za-z][A-Za-z .\-]+?)" + _LOCATION_END,
    # "in Dubai area/region/city"
    r"\bin\s+([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+){0,2})\s+(?:area|region|city|preferred)",
    # "location: Dubai"
    r"\blocation\s*[:=]\s*([A-Za-z][A-Za-z .\-]+?)" + _LOCATION_END,
    # "must be in X", "should be in X", "on-site at X"
    r"\b(?:must\s+be\s+in|should\s+be\s+in|on[- ]site\s+at)\s+([A-Za-z][A-Za-z .\-]+?)" + _LOCATION_END,
    # Bare preposition "in X" / "from X" / "at X" where X is Title-Cased.
    # The (?-i:) inline modifier keeps the [A-Z] anchor case-sensitive even
    # though the outer search uses re.IGNORECASE.
    r"\b(?:in|from|at)\s+(?-i:([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+){0,2}))\b(?!\s*-\s*based)",
]


# Skill / mandatory-tech patterns. The captured chunk is then split on
# commas/and/or and each piece is treated as a required skill.
_SKILL_PATTERNS = [
    r"must\s+have\s+(?:experience\s+in\s+|knowledge\s+of\s+|skills?\s+in\s+)?([A-Za-z0-9+#.\-,/&() ]+?)(?=[;:]|\.(?=\s|$)|\sand\s+(?:should|must|be|have|located|based|in\s)|\swho\b|\swith\s+\d|$)",
    r"required\s+skills?\s*[:=]\s*([A-Za-z0-9+#.\-,/&() ]+?)(?=[;]|\.(?=\s|$)|$)",
    r"mandatory\s+(?:skills?|tech(?:nologies)?|stack)\s*[:=]?\s*([A-Za-z0-9+#.\-,/&() ]+?)(?=[;]|\.(?=\s|$)|$)",
    r"(?:hands[- ]on|strong)\s+(?:experience|background)\s+(?:in|with)\s+([A-Za-z0-9+#.\-,/&() ]+?)(?=[;:]|\.(?=\s|$)|\sand\s+(?:should|must|be|have|located|based|in\s)|\swho\b|\swith\s+\d|$)",
    r"proficient\s+in\s+([A-Za-z0-9+#.\-,/&() ]+?)(?=[;:]|\.(?=\s|$)|\sand\s+(?:should|must|be|have|located|based|in\s)|\swho\b|$)",
]

# A small whitelist of common tech tokens used to validate captured skill
# chunks. Recruiter prompts vary wildly so we don't enforce membership --
# instead, captured tokens are kept if they look like a tech keyword
# (alphanumeric, no English filler words).
_SKILL_TOKEN_BLOCKLIST = {
    "experience", "knowledge", "background", "working", "strong", "good",
    "hands", "hands-on", "deep", "solid", "proven", "and", "or", "the",
    "a", "an", "with", "in", "of", "for", "to", "on", "at", "plus",
    "must", "should", "required", "mandatory", "preferred", "team",
    "years", "year", "yrs", "role", "position", "developer", "engineer",
    "based", "located", "who", "that", "this", "these", "those",
    "candidate", "manager", "lead", "senior", "junior", "mid",
}

# Tokens that, when seen inside a parenthetical in a candidate's location
# string, indicate that the parens contain a *qualifier* (market exposure,
# relocation note, previous job) rather than the actual current location.
# When present the parens are stripped; when absent we KEEP the parens
# content and append it to the primary so multi-place strings like
# "Kurla west, 400070 (Mumbai, India)" still match "india".
_LOCATION_QUALIFIER_TOKENS = {
    "experience", "market", "working", "worked", "previous",
    "previously", "prior", "earlier", "targeting", "relocate",
    "relocation", "open", "willing", "currently", "preferred",
    "exposure", "knowledge", "familiar", "speaks", "speak",
    "background", "native", "originally", "client", "clients",
    "projects", "project",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


_LOCATION_ALIASES = {}
for _group in LOCATION_SYNONYMS:
    _canonical = next((name for name in (
        "uae", "ksa", "usa", "uk", "india", "mumbai", "bangalore",
        "kolkata", "chennai", "gurgaon", "remote",
    ) if name in _group), min(_group))
    _LOCATION_ALIASES.update({name: _canonical for name in _group})
_LOCATION_ALIAS_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(name) for name in
        sorted(_LOCATION_ALIASES, key=lambda name: (-len(name), name))) + r")(?!\w)"
)


def _canonical_location(value: str) -> str:
    return _LOCATION_ALIAS_RE.sub(lambda match: _LOCATION_ALIASES[match[0]], _norm(value))


_COUNTRY_CITIES: dict[str, set[str]] = {}
for _country, _cities in LOCATION_COUNTRY_CITIES.items():
    _COUNTRY_CITIES.setdefault(_canonical_location(_country), set()).update(
        _canonical_location(city) for city in _cities
    )
_PLACE_RE = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(name) for name in
    sorted(KNOWN_PLACES | set(LOCATION_COUNTRY_CITIES) | {
        city for cities in LOCATION_COUNTRY_CITIES.values() for city in cities
    }, key=lambda name: (-len(name), name))) + r")(?!\w)", re.IGNORECASE)


def _skill_pattern(skill: str) -> str:
    """The same bounded token pattern is used by Python and PostgreSQL."""
    normalized = _norm(skill)
    token = re.escape(normalized)
    prefix = r'(^|[^a-z0-9_+#])'
    suffix = r'($|[^a-z_+#])'
    if normalized in {'node', 'node.js', 'nodejs', 'node js'}:
        token = r'node([. ]?js)?'
        prefix = r'(^|[^a-z0-9_+#-])'
        suffix = r'($|[^a-z_+#.]|[.](\s|$))'
    elif normalized in {'react', 'react.js', 'reactjs', 'react js'}:
        token = r'react([. ]?js)?'
        suffix = r'($|[^a-z_+#.]|[.](\s|$))'
    elif normalized == '.net':
        token = r'(asp)?\.net'
    elif normalized == 'sql':
        token = r'(sql|mysql|postgresql|sqlite|mssql|sqlserver)'
    return prefix + token + suffix


def uncertain_language(value: str) -> bool:
    return bool(re.search(
        r'(?<!\w)(implied|assumed|inferred|not provided|not specified|'
        r'not mentioned|n/a|na|unknown)(?!\w)', _norm(value)
    ))


# Words that should never appear inside a parsed location value. If the
# regex captures one of these, the candidate string is a false positive
# (typically grammar like "the candidate must be based") and gets rejected.
_LOCATION_STOPWORDS = {
    "must", "should", "be", "been", "have", "has", "is", "are", "was",
    "were", "the", "a", "an", "candidate", "applicant", "developer",
    "engineer", "manager", "experience", "years", "team", "role",
    "position", "office", "job", "work", "working", "hybrid",
}


def _looks_like_location(loc: str) -> bool:
    """Reject capture strings that contain English grammar words rather
    than place names.
    """
    if not loc:
        return False
    toks = re.findall(r"[a-z]+", loc.lower())
    if not toks:
        return False
    return not any(t in _LOCATION_STOPWORDS for t in toks)


def parse_search_criteria(query: str) -> SearchCriteria:
    """Best-effort regex extraction of hard criteria from a query string."""
    if not query:
        return SearchCriteria()

    q = query.lower()
    crit = SearchCriteria()

    # Normalise simple English word-numbers ("ten years" -> "10 years") so
    # the regex year-patterns below can pick them up. Bounded 1..20 covers
    # nearly all recruiter usage.
    _word_numbers = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
        "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
        "nineteen": "19", "twenty": "20",
    }
    q_for_years = re.sub(
        r"\b(" + "|".join(_word_numbers) + r")\b\s+(years?|yrs?)\b",
        lambda m: f"{_word_numbers[m.group(1)]} {m.group(2)}",
        q,
    )

    # Years -- check fresher/entry-level first so "fresher python" -> 0.
    fresher_hit = any(re.search(pat, q) for pat in _FRESHER_PATTERNS)
    if fresher_hit:
        crit.min_years = 0
    else:
        # Range patterns first so "3-5 years" / "between 3 and 5 years"
        # sets BOTH bounds (the legacy single-min patterns would only catch
        # the lower bound, letting 11-year candidates sail past a 3-5 ask).
        _range_patterns = [
            r"(\d{1,3})\s*(?:-|\u2013|\u2014|to)\s*(\d{1,3})\s*(?:years?|yrs?|y)\b",
            r"between\s*(\d{1,3})\s*(?:and|to|-)\s*(\d{1,3})\s*(?:years?|yrs?|y)\b",
        ]
        for pat in _range_patterns:
            m = re.search(pat, q_for_years, re.IGNORECASE)
            if m:
                try:
                    lo, hi = int(m.group(1)), int(m.group(2))
                    if 0 <= lo <= hi <= 60:
                        crit.min_years = lo
                        crit.max_years = hi
                        # Mask out the matched range so the bare-phrase
                        # min loop below doesn't double-count it.
                        q_for_years = q_for_years[:m.start()] + " " + q_for_years[m.end():]
                        break
                except (TypeError, ValueError):
                    pass

        # Max-only ceilings BEFORE the min scan, so "up to 5 years" /
        # "less than 5 years" don't get min=5 from the bare-phrase pattern.
        if crit.max_years is None:
            # Inclusive ceilings: "up to 5", "maximum 5", "max 5", "<= 5",
            # "no more than 5", "at most 5".
            _max_inclusive = [
                r"(?:up\s*to|maximum|max\.?|no\s*more\s*than|<=|at\s*most)\s*(\d{1,3})\s*(?:years?|yrs?|y)\b",
            ]
            # Exclusive ceilings: "less than 5" / "under 5" / "fewer than 5".
            _max_exclusive = [
                r"(?:less\s*than|fewer\s*than|under|<)\s*(\d{1,3})\s*(?:years?|yrs?|y)\b",
            ]
            for pat in _max_inclusive:
                m = re.search(pat, q_for_years, re.IGNORECASE)
                if m:
                    try:
                        crit.max_years = max(0, int(m.group(1)))
                        q_for_years = q_for_years[:m.start()] + " " + q_for_years[m.end():]
                        break
                    except (TypeError, ValueError):
                        pass
            if crit.max_years is None:
                for pat in _max_exclusive:
                    m = re.search(pat, q_for_years, re.IGNORECASE)
                    if m:
                        try:
                            crit.max_years = max(0, int(m.group(1)) - 1)
                            q_for_years = q_for_years[:m.start()] + " " + q_for_years[m.end():]
                            break
                        except (TypeError, ValueError):
                            pass

        if crit.min_years is None:
            for pat in _YEARS_PATTERNS:
                m = re.search(pat, q_for_years, re.IGNORECASE)
                if m:
                    try:
                        crit.min_years = int(m.group(1))
                        break
                    except (TypeError, ValueError):
                        pass

    # Sanity: ensure min <= max if both were captured.
    if (crit.min_years is not None and crit.max_years is not None
            and crit.min_years > crit.max_years):
        crit.min_years, crit.max_years = crit.max_years, crit.min_years

    # Languages: collect, then filter against known list
    found_langs: set[str] = set()
    language_chunks = []
    for pat in _LANG_PATTERNS:
        for m in re.finditer(pat, query, re.IGNORECASE):
            chunk = m.group(1)
            language_chunks.append(chunk)
            # Split on separators
            for tok in re.split(r"[,&/;()]|\sand\s|\sor\s", chunk, flags=re.IGNORECASE):
                tok = _norm(tok)
                if tok in SPOKEN_LANGUAGES:
                    found_langs.add(tok)
    if found_langs:
        crit.required_languages = sorted(found_langs)
    crit.language_expression = _requirement_expression(language_chunks, _language_term)

    # Location -- primary capture first.
    for pat in _LOCATION_PATTERNS:
        m = re.search(pat, query, re.IGNORECASE)
        if m:
            loc = _norm(m.group(1))
            loc = re.split(r'\s+(?:with|who|having|but|not|excluding|requiring|skills?|experience|speaks?|fluent)\b', loc, maxsplit=1)[0]
            # Strip trailing words that aren't part of the location
            loc = re.sub(r"\s+(?:area|region|city|preferred|only)\s*$", "", loc)
            # Reject if it just turned into a language we already captured,
            # is too long, or looks like English grammar rather than a place.
            if (loc
                    and loc not in SPOKEN_LANGUAGES
                    and len(loc) <= 40
                    and _looks_like_location(loc)):
                crit.location = loc
                break

    # Special case: "Remote" treated as a location even though no preposition
    if crit.location is None and re.search(r"\bremote\b", q):
        crit.location = "remote"

    # Final fallback: scan for a known place name appearing as a whole word.
    # Catches short queries like "5 years and india" or "python developer
    # dubai" where no preposition pattern matches. Iterate longest first so
    # multi-word places ("abu dhabi") win over single-word substrings.
    if crit.location is None:
        for place in sorted(KNOWN_PLACES, key=len, reverse=True):
            if re.search(rf"\b{re.escape(place)}\b", q):
                crit.location = place
                break

    # Multi-location alternatives: scan for an "OR" list of places.
    # e.g. "Dubai or Abu Dhabi", "Mumbai/Bangalore", "in Pune, Hyderabad or Chennai".
    if crit.location is not None:
        crit.location_alternatives = _extract_location_alternatives(
            query, exclude=crit.location
        )

    # Required skills.
    crit.required_skills = _extract_required_skills(query)
    crit.skill_expression = _requirement_expression(_skill_chunks(query), _skill_term)

    return crit


def _extract_location_alternatives(query: str, exclude: str) -> list[str]:
    """Only explicit OR/slash lists expand the primary location."""
    places = list(_PLACE_RE.finditer(query))
    clusters: list[list[re.Match]] = []
    for place in places:
        gap = query[clusters[-1][-1].end():place.start()] if clusters else None
        if gap is not None and re.fullmatch(r'\s*(?:(?:,|/|or|and/or)\s*)*', gap, re.IGNORECASE):
            clusters[-1].append(place)
        else:
            clusters.append([place])
    alternatives: list[str] = []
    primary = _canonical_location(exclude)
    for cluster in clusters:
        gaps = [query[left.end():right.start()] for left, right in zip(cluster, cluster[1:])]
        if not any(re.search(r'\bor\b|/', gap, re.IGNORECASE) for gap in gaps):
            continue
        if not any(re.search(r'(?<!\w)' + re.escape(_canonical_location(place[0])) + r'(?!\w)', primary)
                   for place in cluster):
            continue
        for index, place in enumerate(cluster):
            value = _norm(place[0])
            canonical = _canonical_location(value)
            if canonical == primary or canonical in {_canonical_location(item) for item in alternatives}:
                continue
            # A city followed by its country is one place, not two choices.
            if index and canonical in _COUNTRY_CITIES and not re.search(r'\bor\b', gaps[index - 1], re.IGNORECASE):
                previous = _canonical_location(cluster[index - 1][0])
                if previous in _COUNTRY_CITIES[canonical]:
                    continue
            alternatives.append(value)
    return alternatives


def _language_term(raw):
    value = _norm(re.sub(r'^(?:either|both)\s+', '', raw.strip(), flags=re.IGNORECASE))
    return value if value in SPOKEN_LANGUAGES else None


def _skill_term(raw):
    value = _norm(re.sub(r'^(?:either|both)\s+', '', raw.strip(), flags=re.IGNORECASE))
    if (not value or (len(value)<2 and value not in {'c','r'}) or len(value)>30
            or value in SPOKEN_LANGUAGES or re.fullmatch(r'\d+\+?',value)
            or re.search(r'\b\d+\s*\+?\s*(?:years?|yrs?)\b',value)):
        return None
    if all(part in _SKILL_TOKEN_BLOCKLIST for part in re.findall(r'[a-z0-9.+#]+',value)):
        return None
    return value


def _skill_chunks(query):
    chunks=[]
    for pattern in _SKILL_PATTERNS:
        for match in re.finditer(pattern,query,re.IGNORECASE):
            chunks.append(re.split(r'\b(?:located|based|in\s+\w+|with\s+\d|who|that|years?|yrs?)\b',
                                   match[1],maxsplit=1,flags=re.IGNORECASE)[0])
    return chunks


def _requirement_expression(chunks, normalize):
    expressions=[];has_alternative=False
    for chunk in chunks:
        expression=requirements_logic.compile_clause(chunk,normalize)
        if expression is not None:
            has_alternative=True
        else:
            terms=[normalize(raw) for raw in re.split(r'[,;/&()]|\band\b|\bor\b|\bplus\b',chunk,flags=re.IGNORECASE)]
            items=[{'term':term} for term in terms if term]
            expression={'op':'all','items':items} if items else None
        if expression and expression not in expressions:
            expressions.append(expression)
    if not has_alternative or not expressions:
        return None
    return expressions[0] if len(expressions)==1 else {'op':'all','items':expressions}


def _extract_required_skills(query: str) -> list[str]:
    """Pull explicit hard-required skill tokens from must-have phrasings.
    Returns a deduplicated, lower-cased list. Conservative: skill chunks
    that look like English filler are dropped.
    """
    found: list[str] = []
    seen: set[str] = set()
    for chunk in _skill_chunks(query):
        for raw in re.split(r'[,;/&()]|\band\b|\bor\b|\bplus\b',chunk,flags=re.IGNORECASE):
            tok=_skill_term(raw)
            if tok and tok not in seen:
                seen.add(tok);found.append(tok)
    return found


# ---------- post-filtering --------------------------------------------------


def _parse_years_string(raw: str) -> Optional[float]:
    """Convert one free-text experience string to a float years value.

    Handles common Gemini output shapes:
      "5 Years"                         -> 5.0
      "3.7 Years"                       -> 3.7
      "9+ Years"                        -> 9.0  (conservative lower bound)
      "7 years 10 months"               -> 7.83
      "2-3 Years"                       -> 2.0  (lower bound, conservative)
      "0.5 Years (...) + 0.5 Years"     -> 1.0  (sum segments joined with '+')
      "less than 1 year relevant"       -> 0.5  (mid-point of [0, 1))
      "~2 years"                        -> 2.0
      "Entry-level (less than 1 year)"  -> 0.5
      "0 Years (Internship is not ...)" -> 0.0
    Returns None when no numeric content is present.
    """
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        return None
    text = str(raw).lower().strip()
    if not text or len(text)>4000 or uncertain_language(text):
        return None

    def valid(value):
        return value if math.isfinite(value) and 0 <= value <= 100 else None

    if re.fullmatch(r'(?:no|zero)\s+(?:professional\s+)?experience',text):
        return 0.0

    # A plus after a unit joins distinct segments; "5+ years" is a lower bound.
    parts=re.split(r'(?<=[a-z)])\s*\+\s*',text)
    if 1 < len(parts) <= 32:
        values=[_parse_years_string(part) for part in parts]
        if all(value is not None for value in values):
            return valid(sum(values))

    # Ranges precede single-value matching, preserving the conservative lower bound.
    rng=re.search(r'(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*(?:-|to|\u2013|\u2014)\s*(\d{1,3}(?:\.\d+)?)\s*(?:years?|yrs?)\b',text)
    if rng:
        low,high=float(rng[1]),float(rng[2])
        return valid(low) if low<=high and valid(high) is not None else None

    # "less than N year(s)" / "under N year(s)" / "<N year(s)" -> N - 0.5
    less_m = re.search(
        r"(?:less\s+than|under|fewer\s+than|<\s*)\s*(\d+(?:\.\d+)?)\s*(?:year|yr)",
        text,
    )
    if less_m:
        try:
            n = float(less_m.group(1))
            return valid(max(0.0, n - 0.5))
        except ValueError:
            pass

    # "X years Y months" -> X + Y/12
    ym = re.search(
        r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:and\s*)?(\d+(?:\.\d+)?)\s*(?:months?|mos?)\b",
        text,
    )
    if ym:
        try:
            yrs = float(ym.group(1))
            mos = float(ym.group(2))
            return valid(yrs + mos / 12.0)
        except ValueError:
            pass

    # Explicit units or an entirely numeric field; dates are not experience.
    m = re.search(r"(?<![\d.\-])(\d{1,3}(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b",text)
    if m:
        return valid(float(m[1]))
    months=re.search(r'(?<![\d.\-])(\d{1,3}(?:\.\d+)?)\s*(?:months?|mos?)\b',text)
    if months:
        return valid(float(months[1])/12)
    if re.fullmatch(r'\d{1,3}(?:\.\d+)?',text):
        return valid(float(text))
    return None


def _scorecard_data(analysis: Any) -> dict:
    if not isinstance(analysis, dict):
        return {}
    block = (analysis.get('hr_scorecard') or analysis.get('scorecard')
             or analysis.get('analysis_json') or analysis)
    return block if isinstance(block, dict) else {}


def _extract_candidate_years(analysis: dict) -> Optional[float]:
    """Pull experience years out of various scorecard shapes.

    Prefers the *largest* parsed value across all candidate fields so a
    candidate isn't unfairly penalised when one field reports relevant /
    partial years (e.g. "3+ Years (Frontend specific: 1.6+ years React)")
    and another reports the total.
    """
    if not analysis:
        return None
    raws: list[str] = []

    sc = _scorecard_data(analysis)

    if isinstance(sc, dict):
        co = sc.get("candidate_overview")
        co = co if isinstance(co, dict) else {}
        for key in ("experience_years", "total_experience",
                    "years_of_experience"):
            v = co.get(key)
            if isinstance(v, (str, int, float)) and not isinstance(v, bool):
                raws.append(str(v))
        efa = sc.get("experience_fit_analysis")
        efa = efa if isinstance(efa, dict) else {}
        for key in ("candidate_total_experience", "relevant_experience",
                    "total_years", "years"):
            v = efa.get(key)
            if isinstance(v, (str, int, float)) and not isinstance(v, bool):
                raws.append(str(v))

    parsed = [v for v in (_parse_years_string(r) for r in raws) if v is not None]
    if not parsed:
        return None
    return max(parsed)


def _extract_candidate_languages(analysis: dict) -> list[str]:
    sc = _scorecard_data(analysis)
    langs: list[str] = []
    if isinstance(sc, dict):
        da = sc.get("detailed_analysis")
        da = da if isinstance(da, dict) else {}
        raw = da.get("languages")
        if isinstance(raw, list):
            langs.extend(x for x in raw if isinstance(x, str))
        elif isinstance(raw, str):
            langs.extend(re.split(r"[,;/]| and ", raw))
    return [_norm(x) for x in langs if x and not uncertain_language(x)]


def _extract_candidate_location(analysis: dict) -> str:
    sc = _scorecard_data(analysis)
    if isinstance(sc, dict):
        co = sc.get("candidate_overview")
        co = co if isinstance(co, dict) else {}
        location = co.get('location')
        return _norm(location) if isinstance(location, str) else ''
    return ""


def _extract_candidate_skills(analysis: dict) -> list[str]:
    """Pull skill tokens out of various scorecard shapes for skill-match.

    Looks at every place Gemini might list a candidate's skills/tools:
      hr_scorecard.candidate_overview.skills / key_skills / primary_skills
      hr_scorecard.detailed_analysis.skills_matched / skills / technical_skills /
          matched_skills / tools / tools_technologies / tools_and_technologies /
          technologies / tech_stack / programming_languages / frameworks
      hr_scorecard.keyword_coverage.matched_keywords / keywords
      analysis_json.* equivalents
    Returns lower-cased deduplicated list.
    """
    if not analysis:
        return []
    sc = _scorecard_data(analysis)
    out: list[str] = []
    seen: set[str] = set()

    def _push(val: Any) -> None:
        if val is None:
            return
        items: list[str] = []
        if isinstance(val, list):
            items = [x for x in val if isinstance(x, str)]
        elif isinstance(val, str):
            items = re.split(r"[,;/]|\s+and\s+", val)
        for item in items:
            t = _norm(item)
            if t and t not in seen:
                seen.add(t)
                out.append(t)

    if isinstance(sc, dict):
        co = sc.get("candidate_overview")
        co = co if isinstance(co, dict) else {}
        for k in ("skills", "key_skills", "primary_skills",
                  "technical_skills", "core_skills"):
            _push(co.get(k))
        da = sc.get("detailed_analysis")
        da = da if isinstance(da, dict) else {}
        for k in ("skills_matched", "skills", "technical_skills",
                  "matched_skills", "tools",
                  # Newer Gemini scorecard shapes
                  "tools_technologies", "tools_and_technologies",
                  "technologies", "tech_stack",
                  "programming_languages", "frameworks",
                  "languages_frameworks", "core_competencies"):
            _push(da.get(k))
        # Keyword coverage block (HR scorecard hybrid scoring) often lists
        # the matched keyword tokens which double as candidate skills.
        kc = sc.get("keyword_coverage") or {}
        if isinstance(kc, dict):
            for k in ("matched_keywords", "keywords",
                      "matched", "present_keywords"):
                _push(kc.get(k))
    return out


def _location_primary(have: str) -> str:
    """Normalise a candidate location string for matching.

    Distinguishes between two kinds of parenthetical content:
      1. *Qualifier* parens describing market exposure, prior work, or
         willingness to relocate -- these are stripped because the
         candidate isn't actually there. Example:
           'Sharjah, UAE (with India market experience)' -> 'sharjah, uae'
      2. *Place-name* parens that clarify the actual location -- these are
         kept and folded into the primary so a country-level match still
         finds them. Example:
           'Kurla west, 400070 (Mumbai, India)' -> 'kurla west, 400070, mumbai, india'

    The decision is based on `_LOCATION_QUALIFIER_TOKENS`: if any qualifier
    token appears in the paren content, treat as qualifier; otherwise keep.
    """
    if not have:
        return have

    def _replace(match: re.Match) -> str:
        inner = match.group(1) or ""
        inner_toks = re.findall(r"[a-z]+", inner.lower())
        if any(t in _LOCATION_QUALIFIER_TOKENS for t in inner_toks):
            return " "
        # Keep place-name parens as additional location info.
        return ", " + inner

    cleaned = re.sub(r"\s*[\(\[]([^\)\]]*)[\)\]]\s*", _replace, have)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
    return cleaned


def _location_match(want: str, have: str) -> bool:
    """Match complete place aliases, with country-to-city inference only."""
    if not want:
        return True
    if not have:
        return False
    want = _canonical_location(want)
    have = _canonical_location(_location_primary(have))
    if want == have:
        return True
    want_toks = {t for t in re.findall(r"[a-z]+", want) if len(t) >= 2}
    have_toks = {t for t in re.findall(r"[a-z]+", have) if len(t) >= 2}
    if want_toks and want_toks.issubset(have_toks):
        return True
    if want not in _COUNTRY_CITIES:
        return False
    stated_countries = {country for country in _COUNTRY_CITIES
        if set(country.split()).issubset(have_toks)}
    if stated_countries and want not in stated_countries:
        return False
    return any(set(city.split()).issubset(have_toks) for city in _COUNTRY_CITIES[want])


def evaluate_criteria(analysis: dict, criteria: SearchCriteria) -> dict:
    """Return a criteria_match block describing matches and misses for one
    candidate. Does not mutate the input."""
    out: dict[str, Any] = {
        "evaluated": True,
        "criteria": criteria.to_dict(),
        "matches": [],
        "misses": [],
        "penalty_applied": 0,
    }
    if criteria.is_empty():
        out["evaluated"] = False
        return out

    if criteria.min_years is not None:
        cy = _extract_candidate_years(analysis)
        if cy is None:
            out["misses"].append({
                "criterion": "experience_years",
                "required": f">= {criteria.min_years}",
                "candidate": "unknown",
                "penalty": PENALTY_PER_MISS,
            })
        elif cy + 0.001 < criteria.min_years:
            gap = max(0.0, criteria.min_years - cy)
            yp = min(PENALTY_YEARS_MAX, int(round(gap * PENALTY_YEARS_PER_YEAR)))
            yp = max(yp, PENALTY_PER_MISS // 2)  # floor so 0.5y gap still stings
            out["misses"].append({
                "criterion": "experience_years",
                "required": f">= {criteria.min_years}",
                "candidate": f"{cy:g}",
                "penalty": yp,
            })
        else:
            out["matches"].append({
                "criterion": "experience_years",
                "required": f">= {criteria.min_years}",
                "candidate": f"{cy:g}",
            })

    if criteria.max_years is not None:
        cy = _extract_candidate_years(analysis)
        if cy is None:
            # Don't penalise twice for unknown years if min already did.
            already_noted = any(
                m.get("criterion") == "experience_years" for m in out["misses"]
            )
            if not already_noted:
                out["misses"].append({
                    "criterion": "experience_years",
                    "required": f"<= {criteria.max_years}",
                    "candidate": "unknown",
                    "penalty": PENALTY_PER_MISS,
                })
        elif cy - 0.001 > criteria.max_years:
            gap = cy - criteria.max_years
            yp = min(PENALTY_OVER_YEARS_MAX,
                     int(round(gap * PENALTY_OVER_YEARS_PER_YEAR)))
            yp = max(yp, PENALTY_PER_MISS)  # floor: over-experience is a hard mismatch
            miss = {
                "criterion": "experience_years",
                "required": f"<= {criteria.max_years}",
                "candidate": f"{cy:g}",
                "penalty": yp,
            }
            # Hard-fail flag for severely over-experienced candidates so the
            # caller can drop them from the result list (asking 2-5y and
            # getting an 11-year senior should not appear at all).
            if gap >= OVER_YEARS_HARD_FAIL_GAP:
                miss["hard_fail"] = True
                out["hard_fail"] = True
            out["misses"].append(miss)
        else:
            out["matches"].append({
                "criterion": "experience_years",
                "required": f"<= {criteria.max_years}",
                "candidate": f"{cy:g}",
            })

    if criteria.required_languages or criteria.language_expression is not None:
        have = set(_extract_candidate_languages(analysis))
        def has_language(value):
            return any(re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', h) for h in have)
        for lang in ([None] if criteria.language_expression is not None else criteria.required_languages):
            required = requirements_logic.label(criteria.language_expression) if lang is None else lang
            matched = requirements_logic.evaluate(criteria.language_expression,has_language) if lang is None else has_language(lang)
            if matched:
                out["matches"].append({
                    "criterion": "language",
                    "required": required,
                    "candidate": "found",
                })
            else:
                out["misses"].append({
                    "criterion": "language",
                    "required": required,
                    "candidate": "missing",
                    "penalty": PENALTY_PER_MISS,
                })

    if criteria.location:
        cl = _extract_candidate_location(analysis)
        # Multi-location: match the primary OR any alternative.
        wanted = criteria.all_locations()
        matched_against: Optional[str] = None
        for w in wanted:
            if _location_match(w, cl):
                matched_against = w
                break
        if matched_against is not None:
            out["matches"].append({
                "criterion": "location",
                "required": (criteria.location
                             if len(wanted) == 1
                             else " | ".join(wanted)),
                "candidate": cl or "match",
                "matched_against": matched_against,
            })
        else:
            miss = {
                "criterion": "location",
                "required": (criteria.location
                             if len(wanted) == 1
                             else " | ".join(wanted)),
                "candidate": cl or "unknown",
                "penalty": PENALTY_PER_MISS,
            }
            # Hard-fail when the candidate's location is known but does not
            # match: the user explicitly asked for this location, so a
            # candidate clearly elsewhere (e.g. India for a Dubai search)
            # should be dropped from the result list entirely. Candidates
            # whose location couldn't be extracted are merely penalised.
            if cl and cl.strip():
                miss["hard_fail"] = True
                out["hard_fail"] = True
            out["misses"].append(miss)

    if criteria.required_skills or criteria.skill_expression is not None:
        have_skills = _extract_candidate_skills(analysis)
        def has_skill(value):
            return any(re.search(_skill_pattern(value), item, re.IGNORECASE) for item in have_skills)
        for skill in ([None] if criteria.skill_expression is not None else criteria.required_skills):
            required = requirements_logic.label(criteria.skill_expression) if skill is None else skill
            matched = requirements_logic.evaluate(criteria.skill_expression,has_skill) if skill is None else has_skill(skill)
            if matched:
                out["matches"].append({
                    "criterion": "skill",
                    "required": required,
                    "candidate": "found",
                })
            else:
                out["misses"].append({
                    "criterion": "skill",
                    "required": required,
                    "candidate": "missing",
                    "penalty": PENALTY_PER_MISS,
                })

    out["penalty_applied"] = sum(int(m.get("penalty", PENALTY_PER_MISS)) for m in out["misses"])
    return out


def apply_criteria_to_result(result: dict, criteria: SearchCriteria) -> dict:
    """Mutate one result dict in place: attach criteria_match, and reduce
    match_score by the penalty. Returns the same dict for convenience.

    Idempotent: if `match_score_before_criteria` is already set, the original
    pre-criteria score is restored before re-applying so repeated calls do
    not compound penalties.
    """
    if criteria.is_empty():
        return result
    analysis = result.get("gemini_analysis") or {}
    # Idempotency: restore pre-criteria score if present so a re-apply is safe.
    if isinstance(analysis, dict) and "match_score_before_criteria" in analysis:
        try:
            analysis["match_score"] = float(analysis["match_score_before_criteria"])
        except (TypeError, ValueError):
            pass
        sc_prev = analysis.get("hr_scorecard") if isinstance(analysis, dict) else None
        if isinstance(sc_prev, dict):
            co_prev = sc_prev.get("candidate_overview") or {}
            if "overall_match_score_before_criteria" in co_prev:
                try:
                    co_prev["overall_match_score"] = float(
                        co_prev["overall_match_score_before_criteria"])
                except (TypeError, ValueError):
                    pass
    ev = evaluate_criteria(analysis, criteria)
    result["criteria_match"] = ev
    penalty = ev.get("penalty_applied", 0)
    if penalty and isinstance(analysis, dict):
        try:
            base = float(analysis.get("match_score") or 0)
        except (TypeError, ValueError):
            base = 0.0
        new_score = max(0.0, base - penalty)
        analysis["match_score_before_criteria"] = base
        analysis["match_score"] = new_score
        # Also adjust the scorecard nested score, where present.
        sc = analysis.get("hr_scorecard")
        if isinstance(sc, dict):
            co = sc.setdefault("candidate_overview", {})
            if not isinstance(co, dict):
                co = {}
                sc['candidate_overview'] = co
            try:
                co_base = float(co.get("overall_match_score") or base)
            except (TypeError, ValueError):
                co_base = base
            co["overall_match_score_before_criteria"] = co_base
            co["overall_match_score"] = max(0.0, co_base - penalty)
    return result


def _is_exact_criteria_match(result: dict) -> bool:
    """Return True only when every parsed criterion matched."""
    cm = result.get("criteria_match") or {}
    return bool(cm.get("evaluated")) and not cm.get("hard_fail") and not cm.get("misses")


def apply_criteria_to_results(
    results: list[dict],
    criteria: SearchCriteria,
    *,
    strict: bool = False,
    min_kept: int = 3,
) -> list[dict]:
    """Apply criteria to every result and re-sort by adjusted score (desc).

    Sort uses the *uncapped* base-minus-penalty differential so candidates
    whose displayed score clamps to 0 are still ordered relative to each
    other (a candidate missing 2 criteria ranks above one missing 4 even
    when both display 0). The displayed `match_score` itself is still
    floored at 0 by `apply_criteria_to_result`.
    """
    if criteria.is_empty() or not results:
        return results
    def _rank_key(r: dict) -> float:
        ga = r.get("gemini_analysis") or {}
        try:
            base = float(ga.get("match_score_before_criteria")
                         if ga.get("match_score_before_criteria") is not None
                         else ga.get("match_score") or 0)
        except (TypeError, ValueError):
            base = 0.0
        cm = r.get("criteria_match") or {}
        try:
            penalty = float(cm.get("penalty_applied") or 0)
        except (TypeError, ValueError):
            penalty = 0.0
        # Allow negative differential for stable ranking below 0.
        return base - penalty

    for r in results:
        apply_criteria_to_result(r, criteria)

    before_count = len(results)

    if strict:
        results[:] = [r for r in results if _is_exact_criteria_match(r)]
        dropped = before_count - len(results)
        if dropped:
            try:
                import logging
                logging.getLogger(__name__).info(
                    "search_criteria: strict exact filter dropped %d candidate(s)",
                    dropped,
                )
            except Exception:
                pass
        results.sort(key=_rank_key, reverse=True)
        return results

    # Drop hard-failed candidates (e.g. asking 2-5y and getting 11y, or
    # asking for Chennai and getting Dubai). Safety net: if filtering would
    # leave fewer than min_kept results, restore the best of the dropped ones
    # (still penalised) so non-strict ranking pages do not become empty.
    matched: list[dict] = []
    dropped_list: list[dict] = []
    for r in results:
        if (r.get("criteria_match") or {}).get("hard_fail"):
            dropped_list.append(r)
        else:
            matched.append(r)

    if len(matched) < min_kept and dropped_list:
        # Rank dropped candidates by their (already penalised) score so the
        # least-bad off-criteria candidates come back first.
        def _drop_rank(r: dict) -> float:
            ga = r.get("gemini_analysis") or {}
            try:
                return float(ga.get("match_score") or 0)
            except (TypeError, ValueError):
                return 0.0
        dropped_list.sort(key=_drop_rank, reverse=True)
        need = min_kept - len(matched)
        restored = dropped_list[:need]
        # Mark them so downstream UI / logs know these were soft-restored
        # despite failing the hard filter.
        for r in restored:
            cm = r.setdefault("criteria_match", {})
            cm["soft_restored"] = True
        matched.extend(restored)
        dropped_list = dropped_list[need:]

    results[:] = matched
    dropped = before_count - len(results)
    if dropped or any((r.get("criteria_match") or {}).get("soft_restored") for r in results):
        try:
            import logging
            soft = sum(1 for r in results if (r.get("criteria_match") or {}).get("soft_restored"))
            logging.getLogger(__name__).info(
                "search_criteria: dropped %d candidate(s), soft-restored %d to maintain min %d results",
                dropped, soft, min_kept,
            )
        except Exception:
            pass

    results.sort(key=_rank_key, reverse=True)
    return results
