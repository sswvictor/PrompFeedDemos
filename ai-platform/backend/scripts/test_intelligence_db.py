"""
End-to-end DB test for the intelligence pipeline.

Tests:
  1. analyze_provider()  — stores specialties, price_tier, vibe tags, summary in DB
  2. confirm_vibes()     — updates confirmed_vibe_tags + status = 'confirmed'
  3. get_intelligence()  — reads back the full record
  4. Verifies all JSON fields parse correctly

No server needed — calls pipeline functions directly with a real DB connection.
Uses an existing provider from the DB (non-destructive: only writes to
provider_intelligence table, which can be re-run safely).

Usage (from backend/):
    python -m scripts.test_intelligence_db
"""

import json
import os
import sys
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent.parent / ".env"  # repo root
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# ── Bootstrap app (needed for settings + DB) ─────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models.provider import Provider
from app.models.provider_intelligence import ProviderIntelligence, VIBE_DIMENSIONS
from app.services.intelligence_pipeline import analyze_provider, confirm_vibes, get_intelligence

# ── Mock scan data (mirrors what /setup/scan-website returns) ─────────────────
MOCK_SCAN_DATA = {
    "source_url": "https://www.salonglyktan.se",
    "name": "Hår & Skönhetssalong Lyktan",
    "city": "Stockholm",
    "bio": "Vi är en liten, personlig hårsalong på Södermalm. Vi tror på tidlös stil, hög kvalitet och en avkopplande upplevelse för varje kund.",
    "services": [
        {"name": "Damklippning", "duration_minutes": 60, "price": 750, "description": "Tvätt, klipp, blow-dry"},
        {"name": "Balayage / babylights", "duration_minutes": 150, "price": 2200, "description": ""},
        {"name": "Herrklippning", "duration_minutes": 45, "price": 495, "description": ""},
        {"name": "Olaplex behandling", "duration_minutes": 30, "price": 450, "description": ""},
        {"name": "Keratin-smoothing treatment", "duration_minutes": 120, "price": 1800, "description": ""},
    ],
    "specialties": ["skandinavisk balayage", "naturliga toner", "precision cuts"],
    "price_tier": "mid-range",
    "target_audience": "Kunder som söker högkvalitativ hårvård i en lugn atmosfär",
    "unique_value": "Enbart ekologiska och cruelty-free produkter (Davines, Olaplex) i en stressfri Södermalm-salong",
    "social_proof": [
        "Bästa salongen i Stockholm! Maja förstår exakt vad man vill ha.",
        "Fantastisk balayage, håller i månader. Värt varenda krona.",
        "Lugn atmosfär, kompetent personal och riktigt gott kaffe.",
    ],
    "ai_vibe_tags": [
        {"tag": "minimalist", "score": 0.8, "dimension": "aesthetic"},
        {"tag": "calm",       "score": 0.9, "dimension": "energy"},
        {"tag": "timeless",   "score": 0.85, "dimension": "style_era"},
        {"tag": "boutique",   "score": 0.75, "dimension": "brand_personality"},
    ],
    "vibe_summary": "A calm, minimalist Södermalm salon focused on timeless beauty and ethical products.",
}

MOCK_CONFIRMED_TAGS = ["minimalist", "calm", "timeless", "boutique", "eco-conscious"]

SEP = "=" * 62


def fmt_json(raw: str | None) -> str:
    if not raw:
        return "  (empty)"
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, indent=4, ensure_ascii=False)
    except Exception:
        return f"  INVALID JSON: {raw[:100]}"


def main():
    print(f"\n{SEP}")
    print("  FIXMEAPP INTELLIGENCE PIPELINE — DB TEST")
    print(SEP)

    db = SessionLocal()
    try:
        # ── Pick a test provider ───────────────────────────────────────────────
        provider = db.query(Provider).first()
        if not provider:
            print("\n  FAIL No providers in DB. Run migrations and create at least one provider first.")
            return

        pid = str(provider.provider_id)
        name = getattr(provider, "name", None) or "(unnamed)"
        print(f"\n  Using provider: {name} ({pid[:8]}...)")

        # ── Step 1: analyze_provider ───────────────────────────────────────────
        print(f"\n{SEP}")
        print("  STEP 1 — analyze_provider() [calls GPT-4o-mini for vibe extraction]")
        print(SEP)

        intel = analyze_provider(db=db, provider_id=pid, scan_data=MOCK_SCAN_DATA)

        print(f"\n  status:           {intel.status}")
        print(f"  source_url:       {intel.source_url}")
        print(f"  price_tier:       {intel.price_tier}")
        print(f"  target_audience:  {intel.target_audience}")
        print(f"  unique_value:     {intel.unique_value}")
        print(f"  ig_posts_analyzed:{intel.ig_posts_analyzed}")
        print(f"  analyzed_at:      {intel.analyzed_at}")

        print(f"\n  specialties (JSON):")
        print(fmt_json(intel.specialties))

        print(f"\n  social_proof (JSON):")
        print(fmt_json(intel.social_proof))

        print(f"\n  ai_vibe_tags (JSON):")
        print(fmt_json(intel.ai_vibe_tags))

        print(f"\n  vibe_scores (JSON):")
        print(fmt_json(intel.vibe_scores))

        print(f"\n  vibe_summary:")
        print(f"    {intel.vibe_summary}")

        print(f"\n  data_sources (JSON):")
        print(fmt_json(intel.data_sources))

        # Validate tags are in taxonomy
        tags = json.loads(intel.ai_vibe_tags or "[]")
        all_valid = set(t for dim in VIBE_DIMENSIONS.values() for t in dim)
        invalid = [t for t in tags if t not in all_valid]
        if invalid:
            print(f"\n  WARN  Invalid tags (not in taxonomy): {invalid}")
        else:
            print(f"\n  OK   All {len(tags)} vibe tag(s) are valid taxonomy members")

        # ── Step 2: confirm_vibes ──────────────────────────────────────────────
        print(f"\n{SEP}")
        print("  STEP 2 — confirm_vibes() [provider confirms their tags]")
        print(SEP)
        print(f"\n  Confirming tags: {MOCK_CONFIRMED_TAGS}")

        confirmed = confirm_vibes(db=db, provider_id=pid, confirmed_tags=MOCK_CONFIRMED_TAGS)

        print(f"\n  status after confirm:  {confirmed.status}")
        print(f"  confirmed_at:          {confirmed.confirmed_at}")
        print(f"\n  confirmed_vibe_tags (JSON):")
        print(fmt_json(confirmed.confirmed_vibe_tags))

        # Validate confirmed tags (eco-conscious might be filtered if not in taxonomy)
        stored = json.loads(confirmed.confirmed_vibe_tags or "[]")
        invalid_confirmed = [t for t in stored if t not in all_valid]
        if invalid_confirmed:
            print(f"\n  WARN  Filtered out invalid tags: {[t for t in MOCK_CONFIRMED_TAGS if t not in all_valid]}")
        else:
            print(f"\n  OK   {len(stored)}/{len(MOCK_CONFIRMED_TAGS)} confirmed tags stored (invalid ones filtered)")

        # ── Step 3: get_intelligence (read-back) ───────────────────────────────
        print(f"\n{SEP}")
        print("  STEP 3 — get_intelligence() [fresh DB read-back]")
        print(SEP)

        readback = get_intelligence(db, pid)
        if not readback:
            print("\n  FAIL Record not found on read-back!")
            return

        # Verify key fields match
        checks = [
            ("status",       readback.status,     "confirmed"),
            ("price_tier",   readback.price_tier,  "mid-range"),
            ("source_url",   readback.source_url,  MOCK_SCAN_DATA["source_url"]),
        ]
        all_ok = True
        for field, actual, expected in checks:
            ok = actual == expected
            all_ok = all_ok and ok
            mark = "OK  " if ok else "FAIL"
            print(f"\n  {mark} {field}: {actual!r}  (expected {expected!r})")

        print(f"\n{SEP}")
        if all_ok:
            print("  ALL CHECKS PASSED — intelligence pipeline is working correctly")
        else:
            print("  SOME CHECKS FAILED — see above")
        print(SEP)
        print()

    except Exception as exc:
        import traceback
        print(f"\n  EXCEPTION: {exc}")
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
