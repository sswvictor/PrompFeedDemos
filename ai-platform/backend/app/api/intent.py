"""
Intent parser for natural language booking prompts.

Detects signals from a raw prompt string and returns an IntentResult
that tells the feed which providers to surface and which fields to emphasize
in the UI components.

Rule-based — no LLM call needed for this layer. Easy to swap for an LLM
call later if signal quality needs to improve.
"""
from dataclasses import dataclass, field
import re


# ── Signal keyword lists ──────────────────────────────────────────────────────

_PRICE_SENSITIVE = {
    "cheap", "budget", "affordable", "inexpensive", "low cost", "reasonable",
    "value", "good deal", "not too expensive", "cheap but",
    # Swedish / Norwegian
    "billig", "billigt", "prisvärd", "prisvärt", "prisgunstig", "rimlig",
    "rimligt", "förmånlig", "förmånligt", "billig men", "billigst",
}

_QUALITY_FOCUSED = {
    "great", "best", "top", "excellent", "amazing", "outstanding", "perfect",
    "highly rated", "top rated", "well reviewed", "popular", "experienced",
    "recommended", "good", "quality", "professional",
    # Swedish / Norwegian
    "bra", "bäst", "topp", "utmärkt", "professionell", "rekommenderad",
    "välrenommerad", "duktig", "skicklig",
}

_URGENCY = {
    "today", "asap", "now", "tonight", "this week", "immediately", "urgent",
    "right now", "today please", "same day",
    # Swedish / Norwegian
    "idag", "nu", "snabbt", "denna vecka", "direkt", "omgående",
}

# Neighborhoods / cities — extend as needed
_LOCATION_TOKENS = {
    # Stockholm
    "östermalm", "södermalm", "vasastan", "kungsholmen", "norrmalm",
    "djurgården", "gamla stan", "nacka", "solna", "sundbyberg", "lidingö",
    "danderyd", "täby", "bromma", "liljeholmen", "hammarby", "stockholm",
    # Gothenburg
    "göteborg", "haga", "linné", "majorna",
    # Malmö
    "malmö", "värnhem", "möllevången",
    # Oslo
    "oslo", "frogner", "majorstuen", "grünerløkka", "sentrum", "aker brygge",
    "st. hanshaugen",
    # Generic
    "near me", "nearby", "close by", "in my area",
}

# Service type keyword → canonical category slug
_SERVICE_MAP: dict[str, str] = {
    # Hair
    "hair": "hair", "haircut": "hair", "hairstyle": "hair",
    "hairstylist": "hair", "stylist": "hair", "blowout": "hair",
    "balayage": "hair", "highlights": "hair", "color": "hair", "trim": "hair",
    "cut": "hair", "klippning": "hair", "frisör": "hair", "frisörska": "hair",
    "hår": "hair", "frisyr": "hair", "färgning": "hair",
    # Barber
    "barber": "barber", "beard": "barber", "shave": "barber",
    "herrklippning": "barber", "skägg": "barber", "rakning": "barber",
    # Nails
    "nail": "nails", "nails": "nails", "manicure": "nails",
    "pedicure": "nails", "gel nails": "nails", "acrylics": "nails",
    "naglar": "nails", "nagel": "nails", "manikyr": "nails",
    "pedikyr": "nails",
    # Lashes / brows
    "lash": "lashes", "lashes": "lashes", "brows": "lashes",
    "eyebrows": "lashes", "extensions": "lashes", "fransar": "lashes",
    "ögonbryn": "lashes",
    # Makeup
    "makeup": "makeup", "make-up": "makeup", "makeover": "makeup",
    "smink": "makeup",
    # Skincare
    "facial": "skincare", "skincare": "skincare", "skin": "skincare",
    "peel": "skincare", "ansiktsbehandling": "skincare", "hud": "skincare",
    # Massage
    "massage": "massage", "massör": "massage", "massös": "massage",
    "therapeutic": "massage", "relaxing massage": "massage",
    # Spa
    "spa": "spa", "wellness": "spa", "sauna": "spa",
}

# Vibe keyword → taxonomy tag mapping (all 4 dimensions + common synonyms)
# Used for both feed search and platform search vibe scoring.
_VIBE_KEYWORDS: dict[str, str] = {
    # aesthetic
    "minimalist": "minimalist", "minimal": "minimalist", "clean lines": "minimalist",
    "maximalist": "maximalist", "lush": "maximalist", "ornate": "maximalist",
    "editorial": "editorial", "high fashion": "editorial", "fashion forward": "editorial",
    "boho": "boho", "bohemian": "boho", "earthy": "boho",
    "classic": "classic",
    "avant-garde": "avant-garde", "experimental": "avant-garde",
    "natural": "natural", "organic": "natural",
    "glamorous": "glamorous", "glam": "glamorous", "glitzy": "glamorous",
    "industrial": "industrial", "raw": "industrial",
    "vintage": "vintage",
    # energy
    "calm": "calm", "relaxing": "calm", "peaceful": "calm", "chill": "calm",
    "energetic": "energetic", "vibrant": "energetic", "lively": "energetic",
    "luxurious": "luxurious", "luxury": "luxurious",
    "cozy": "cozy", "warm": "cozy", "hygge": "cozy",
    "edgy": "edgy", "rock": "edgy", "punk": "edgy", "alternative": "edgy",
    "playful": "playful", "fun": "playful", "quirky": "playful",
    "sophisticated": "sophisticated", "refined": "sophisticated", "elegant": "sophisticated",
    "zen": "zen", "mindful": "zen", "meditative": "zen",
    "bold": "bold", "statement": "bold", "striking": "bold",
    "intimate": "intimate", "personal": "intimate",
    # style era
    "modern": "modern", "contemporary": "modern",
    "retro": "retro", "old school": "retro",
    "timeless": "timeless",
    "trendsetting": "trendsetting", "trendy": "trendsetting",
    "traditional": "traditional",
    # brand personality
    "artistic": "artistic", "art": "artistic",
    "clinical": "clinical", "medical grade": "clinical", "precise": "clinical",
    "boutique": "boutique", "independent": "boutique",
    "eco-conscious": "eco-conscious", "eco": "eco-conscious",
    "sustainable": "eco-conscious", "green": "eco-conscious",
    "tech-forward": "tech-forward", "tech": "tech-forward",
    "family-friendly": "family-friendly", "family": "family-friendly", "kids": "family-friendly",
    "exclusive": "exclusive", "vip": "exclusive",
    "community-driven": "community-driven", "community": "community-driven",
}

# Emphasis field mapping: signal → ordered list of provider fields to highlight
_SIGNAL_EMPHASIS: dict[str, list[str]] = {
    "price_sensitive":  ["price_level", "starting_from", "price_range"],
    "quality_focused":  ["rating", "revisit_rate", "review_count"],
    "urgency":          ["next_available", "available_today"],
    "location":         ["city", "location_salon"],
    "service_specific": ["matched_services"],
    "vibe":             ["vibe_tags", "vibe_summary"],
}

# Price level labels
PRICE_LEVEL_LABELS = {
    1: "Budget-friendly",
    2: "Standard",
    3: "Premium",
    4: "Luxury",
}


@dataclass
class IntentResult:
    raw_prompt: str
    signals: list[str] = field(default_factory=list)
    emphasis: list[str] = field(default_factory=list)
    location: str | None = None
    service_category: str | None = None
    service_keywords: list[str] = field(default_factory=list)
    vibe_tags: list[str] = field(default_factory=list)   # detected vibe tags
    sort_strategy: str = "rating"  # "price_asc", "value_score", "rating", "availability"
    subtitle: str = ""  # Human-readable summary line for SearchSummaryCard

    def to_dict(self) -> dict:
        return {
            "raw_prompt": self.raw_prompt,
            "signals": self.signals,
            "emphasis": self.emphasis,
            "location": self.location,
            "service_category": self.service_category,
            "service_keywords": self.service_keywords,
            "vibe_tags": self.vibe_tags,
            "sort_strategy": self.sort_strategy,
            "subtitle": self.subtitle,
        }


def parse_intent(prompt: str) -> IntentResult:
    """Parse a raw user prompt and return detected intent signals.

    Examples:
        >>> parse_intent("cheap but great hairstylists in östermalm")
        IntentResult(signals=['price_sensitive', 'quality_focused', 'location', 'service_specific'], ...)

        >>> parse_intent("nail salon today asap")
        IntentResult(signals=['urgency', 'service_specific'], sort_strategy='availability', ...)
    """
    lower = prompt.lower().strip()
    tokens = set(re.findall(r"[a-zåäöæøü]+(?:'[a-z]+)?", lower))

    signals: list[str] = []

    # ── Price sensitivity ─────────────────────────────────────────────────────
    if tokens & _PRICE_SENSITIVE or any(kw in lower for kw in _PRICE_SENSITIVE if " " in kw):
        signals.append("price_sensitive")

    # ── Quality focus ─────────────────────────────────────────────────────────
    if tokens & _QUALITY_FOCUSED or any(kw in lower for kw in _QUALITY_FOCUSED if " " in kw):
        signals.append("quality_focused")

    # ── Urgency ───────────────────────────────────────────────────────────────
    if tokens & _URGENCY or any(kw in lower for kw in _URGENCY if " " in kw):
        signals.append("urgency")

    # ── Location ─────────────────────────────────────────────────────────────
    detected_location: str | None = None
    for loc in _LOCATION_TOKENS:
        if loc in lower:
            detected_location = loc.title()
            break
    if detected_location:
        signals.append("location")

    # ── Service type ─────────────────────────────────────────────────────────
    detected_category: str | None = None
    matched_service_keywords: list[str] = []

    # Check multi-word keys first (longer matches win)
    for kw in sorted(_SERVICE_MAP.keys(), key=len, reverse=True):
        if kw in lower:
            cat = _SERVICE_MAP[kw]
            if not detected_category:
                detected_category = cat
            if kw not in matched_service_keywords:
                matched_service_keywords.append(kw)

    if detected_category:
        signals.append("service_specific")

    # ── Vibe / aesthetic ─────────────────────────────────────────────────────
    detected_vibe_tags: list[str] = []
    # Check multi-word keys first so "clean lines" wins over "clean"
    for kw in sorted(_VIBE_KEYWORDS.keys(), key=len, reverse=True):
        if kw in lower:
            tag = _VIBE_KEYWORDS[kw]
            if tag not in detected_vibe_tags:
                detected_vibe_tags.append(tag)

    if detected_vibe_tags:
        signals.append("vibe")

    # ── Compute emphasis ─────────────────────────────────────────────────────
    emphasis: list[str] = []
    for sig in signals:
        for field_name in _SIGNAL_EMPHASIS.get(sig, []):
            if field_name not in emphasis:
                emphasis.append(field_name)

    # Ensure some baseline emphasis is always present
    for baseline in ["rating", "services"]:
        if baseline not in emphasis:
            emphasis.append(baseline)

    # ── Sort strategy ─────────────────────────────────────────────────────────
    if "urgency" in signals:
        sort_strategy = "availability"
    elif "price_sensitive" in signals and "quality_focused" in signals:
        sort_strategy = "value_score"        # rating / price_level
    elif "price_sensitive" in signals:
        sort_strategy = "price_asc"
    elif "quality_focused" in signals:
        sort_strategy = "rating"
    else:
        sort_strategy = "rating"

    # ── Subtitle ─────────────────────────────────────────────────────────────
    subtitle = _build_subtitle(
        signals, detected_category, detected_location, sort_strategy, detected_vibe_tags
    )

    return IntentResult(
        raw_prompt=prompt,
        signals=signals,
        emphasis=emphasis,
        location=detected_location,
        service_category=detected_category,
        service_keywords=matched_service_keywords,
        vibe_tags=detected_vibe_tags,
        sort_strategy=sort_strategy,
        subtitle=subtitle,
    )


def _build_subtitle(
    signals: list[str],
    category: str | None,
    location: str | None,
    sort_strategy: str,
    vibe_tags: list[str] | None = None,
) -> str:
    parts: list[str] = []

    service_label = category.replace("_", " ").title() if category else "providers"

    if location:
        parts.append(f"{service_label} in {location}")
    else:
        parts.append(service_label.capitalize())

    if vibe_tags:
        parts.append(f"{', '.join(vibe_tags[:2])} vibe")

    if sort_strategy == "value_score":
        parts.append("sorted by best value")
    elif sort_strategy == "price_asc":
        parts.append("sorted by lowest price")
    elif sort_strategy == "availability":
        parts.append("showing earliest availability")
    elif sort_strategy == "rating":
        parts.append("sorted by top rated")

    return ", ".join(parts)
