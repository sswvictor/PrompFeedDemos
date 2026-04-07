"""
Quick end-to-end test for the website scan + intelligence pipeline.

Usage (from backend/):
    python -m scripts.test_scan_pipeline https://yoursalon.com

No server, no DB, no auth needed — just OpenAI key in .env.
Prints the full extracted JSON so you can verify before committing.
"""

import json
import re
import sys
import os

from pathlib import Path
# Load .env from backend root
env_path = Path(__file__).parent.parent.parent / ".env"  # repo root
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

import httpx
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

# ── Step 1: Scrape ────────────────────────────────────────────────────────────

def scrape_url(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9,sv;q=0.8",
    }
    try:
        resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", resp.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{3,}", "\n", text)
        return text[:12000]
    except Exception as e:
        print(f"  ✗ Scrape failed: {e}")
        return ""


# ── Step 2: AI extraction ────────────────────────────────────────────────────

def ai_extract(url: str, page_text: str) -> dict:
    system_prompt = (
        "You are an AI data-extraction assistant for a beauty & wellness discovery platform. "
        "Analyze the given website page text and extract a comprehensive structured profile "
        "to power our AI discovery engine. Return ONLY valid JSON (no markdown fences).\n\n"
        "Required fields (omit if not found):\n"
        "- name (string): business or provider name\n"
        "- city (string): city where they operate\n"
        "- bio (string): compelling description in their voice, 150–300 chars\n"
        "- services (array): [{name, duration_minutes, price, description}] — all services/treatments\n"
        "- working_hours (object): {Mon,Tue,Wed,Thu,Fri,Sat,Sun: {open:bool, start:'HH:MM', end:'HH:MM'}}\n"
        "- amenity_keys (array of strings): e.g. ['wifi','parking','card_payment','private_room']\n"
        "- booking_policy (string): booking/deposit policy, max 200 chars\n"
        "- cancellation_policy (string): cancellation policy, max 200 chars\n\n"
        "Enhanced AI-profile fields:\n"
        "- specialties (array of 3–6 strings): unique skills or signature services\n"
        "- price_tier (string): one of 'budget' | 'mid-range' | 'premium' | 'luxury'\n"
        "- target_audience (string): who they primarily serve, max 100 chars\n"
        "- unique_value (string): what makes them stand out from competitors, max 200 chars\n"
        "- social_proof (array of up to 3 strings): verbatim testimonial or review quotes found on page\n\n"
        "Vibe & aesthetic analysis:\n"
        "- vibe_tags (array of objects): [{tag, score, dimension}] — pick 3-6 tags from these dimensions:\n"
        "  aesthetic: minimalist, maximalist, editorial, boho, classic, avant-garde, natural, glamorous, industrial, vintage\n"
        "  energy: calm, energetic, luxurious, cozy, edgy, playful, sophisticated, zen, bold, intimate\n"
        "  style_era: modern, retro, timeless, trendsetting, traditional\n"
        "  brand_personality: artistic, clinical, boutique, eco-conscious, tech-forward, family-friendly, exclusive, community-driven\n"
        "  Each tag object: {\"tag\": \"minimalist\", \"score\": 0.85, \"dimension\": \"aesthetic\"}\n"
        "- vibe_summary (string): 1-2 sentences describing their overall vibe, max 150 chars\n"
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"URL: {url}\n\nPage content:\n{page_text}"},
        ],
        temperature=0.1,
        max_tokens=2500,
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Parse args:  test_scan_pipeline.py [URL] [--file path/to/page.txt]
    args = sys.argv[1:]
    file_path = None
    url = "https://www.salonglyktan.se"

    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            file_path = args[i + 1]; i += 2
        else:
            url = args[i]; i += 1

    print(f"\n{'='*60}")
    print(f"  FIXMEAPP SCAN PIPELINE TEST")
    print(f"{'='*60}")
    print(f"  URL: {url}\n")

    if file_path:
        print(f"  [1/2] Loading pre-fetched content from {file_path}...")
        try:
            page_text = Path(file_path).read_text(encoding="utf-8")
            print(f"  OK Got {len(page_text):,} chars\n")
        except Exception as e:
            print(f"  FAIL Could not read file: {e}")
            sys.exit(1)
    else:
        print("  [1/2] Scraping page...")
        page_text = scrape_url(url)
        if not page_text:
            print("  FAIL Nothing scraped. URL might be JS-heavy or blocked.")
            sys.exit(1)
        chars = len(page_text)
        print(f"  OK Got {chars:,} chars of page text\n")

    print("  [2/2] Running AI extraction (gpt-4o-mini)...")
    try:
        result = ai_extract(url, page_text)
    except Exception as e:
        print(f"  FAIL AI extraction failed: {e}")
        sys.exit(1)
    print(f"  OK Extraction complete\n")

    print(f"{'='*60}")
    print("  RESULTS")
    print(f"{'='*60}\n")

    # Summary view
    print(f"  Name:          {result.get('name', '—')}")
    print(f"  City:          {result.get('city', '—')}")
    print(f"  Price tier:    {result.get('price_tier', '—')}")
    print(f"  Target:        {result.get('target_audience', '—')}")
    print(f"  Services:      {len(result.get('services', []))} found")
    print(f"  Specialties:   {result.get('specialties', [])}")
    print(f"  Vibe tags:     {[t['tag'] for t in result.get('vibe_tags', [])]}")
    print(f"  Vibe summary:  {result.get('vibe_summary', '—')}")
    print(f"  Unique value:  {result.get('unique_value', '—')}")
    social = result.get('social_proof', [])
    print(f"  Social proof:  {len(social)} quotes")
    print()

    print("  FULL JSON:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()

if __name__ == "__main__":
    main()
