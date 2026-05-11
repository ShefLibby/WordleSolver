"""
Fetches the word list directly from wordleunlimited.org's main.js
and writes all unique 5-letter words to words.txt.
Run this once to get the full game word list.
"""
import re
import os
import sys
import urllib.request

MAIN_JS_URL = "https://wordleunlimited.org/main.js"
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.txt")


def fetch_words():
    print(f"Fetching {MAIN_JS_URL} ...")
    req = urllib.request.Request(
        MAIN_JS_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        js = resp.read().decode("utf-8", errors="ignore")
    print(f"Downloaded {len(js):,} bytes")

    # Extract every quoted 5-letter lowercase string
    raw = re.findall(r'"([a-z]{5})"', js)
    words = sorted(set(raw))
    print(f"Found {len(words)} unique 5-letter words")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(words) + "\n")
    print(f"Saved to {OUT_PATH}")
    return words


if __name__ == "__main__":
    try:
        words = fetch_words()
        print("\nSample words:", words[:20])
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
