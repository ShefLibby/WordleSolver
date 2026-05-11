import os
import random
import sys
from collections import Counter
from math import log2
from typing import List, Optional, Tuple

from logger import get_logger

log = get_logger(__name__)

# Openers: all 5 unique letters, chosen for high letter-frequency coverage
OPENER_POOL = [
    "crane", "slate", "trace", "crate", "snare",
    "stare", "arise", "irate", "least", "stale",
    "tried", "alter", "later", "trice", "clout",
]


def _words_path() -> str:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "words.txt")


def load_words() -> List[str]:
    path = _words_path()
    log.debug("Loading word list from: %s", path)
    seen: set = set()
    words: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if len(w) == 5 and w.isalpha() and w not in seen:
                seen.add(w)
                words.append(w)
    log.info("Loaded %d unique words", len(words))
    return words


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def _get_pattern(guess: str, answer: str) -> Tuple[str, ...]:
    result = ["absent"] * 5
    answer_pool = list(answer)

    for i in range(5):
        if guess[i] == answer[i]:
            result[i] = "correct"
            answer_pool[i] = None  # type: ignore[call-overload]

    for i in range(5):
        if result[i] != "correct" and guess[i] in answer_pool:
            result[i] = "present"
            answer_pool[answer_pool.index(guess[i])] = None  # type: ignore[call-overload]

    return tuple(result)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_words(
    candidates: List[str],
    guess: str,
    result: List[str],
) -> List[str]:
    """Return subset of candidates consistent with the feedback from one guess."""
    pattern = tuple(result)
    kept = [w for w in candidates if _get_pattern(guess, w) == pattern]
    log.debug(
        "filter_words('%s', %s): %d → %d",
        guess, result, len(candidates), len(kept),
    )
    return kept


def _apply_all_constraints(
    words: List[str],
    history: List[Tuple[str, List[str]]],
) -> List[str]:
    """Apply every (guess, result) pair in history to narrow down words."""
    result = words
    for guess, feedback in history:
        result = filter_words(result, guess, feedback)
    return result


def _words_respecting_constraints(
    words: List[str],
    history: List[Tuple[str, List[str]]],
) -> List[str]:
    """
    Looser filter used for info-gathering when the answer is not in our list.
    Keeps words that:
      - place known-correct letters at their correct positions
      - do not place known-present letters at their known-wrong positions
      - do not use letters known to be absent (accounting for duplicates)
    """
    correct: dict = {}       # pos -> letter
    wrong_pos: dict = {}     # letter -> set of positions where it cannot be
    min_count: dict = {}     # letter -> minimum required occurrences
    exact_count: dict = {}   # letter -> exact required occurrences (if capped by absent)

    for guess, feedback in history:
        letter_feedback: dict = {}  # letter -> list of states at each occurrence
        for i, (letter, state) in enumerate(zip(guess, feedback)):
            letter_feedback.setdefault(letter, []).append((i, state))

        for letter, occurrences in letter_feedback.items():
            greens   = [(i, s) for i, s in occurrences if s == "correct"]
            yellows  = [(i, s) for i, s in occurrences if s == "present"]
            grays    = [(i, s) for i, s in occurrences if s == "absent"]

            confirmed = len(greens) + len(yellows)
            if confirmed > 0:
                min_count[letter] = max(min_count.get(letter, 0), confirmed)

            if grays:
                # At least one gray: the word contains exactly `confirmed` of this letter
                exact_count[letter] = min(
                    exact_count.get(letter, confirmed), confirmed
                )

            for i, _ in greens:
                correct[i] = letter

            for i, _ in yellows:
                wrong_pos.setdefault(letter, set()).add(i)

    def valid(word: str) -> bool:
        for pos, letter in correct.items():
            if word[pos] != letter:
                return False
        for letter, positions in wrong_pos.items():
            for pos in positions:
                if word[pos] == letter:
                    return False
        for letter, count in min_count.items():
            if word.count(letter) < count:
                return False
        for letter, count in exact_count.items():
            if word.count(letter) != count:
                return False
        return True

    kept = [w for w in words if valid(w)]
    log.debug("_words_respecting_constraints: %d → %d", len(words), len(kept))
    return kept


# ---------------------------------------------------------------------------
# Entropy scoring
# ---------------------------------------------------------------------------

def _entropy(guess: str, candidates: List[str]) -> float:
    counts: Counter = Counter()
    for answer in candidates:
        counts[_get_pattern(guess, answer)] += 1
    total = len(candidates)
    return sum(-(c / total) * log2(c / total) for c in counts.values() if c > 0)


# ---------------------------------------------------------------------------
# Main solver entry point
# ---------------------------------------------------------------------------

def best_guess(
    candidates: List[str],
    all_words: List[str],
    attempt: int,
    previous_guesses: Optional[List[str]] = None,
    history: Optional[List[Tuple[str, List[str]]]] = None,
) -> str:
    previous_guesses = previous_guesses or []
    history = history or []

    # --- Attempt 1: random opener (all unique letters) ---
    if attempt == 1:
        opener = random.choice(OPENER_POOL)
        log.info("Attempt 1 — random opener: '%s'", opener)
        return opener

    # --- Normal mode: candidates exist ---
    if candidates:
        if len(candidates) <= 2:
            log.info("%d candidate(s) left — guessing '%s'", len(candidates), candidates[0])
            return candidates[0]

        log.debug("Scoring %d candidates…", len(candidates))
        best_word = max(candidates, key=lambda w: _entropy(w, candidates))
        score = _entropy(best_word, candidates)
        log.info("Best guess: '%s'  (entropy=%.3f bits, %d candidates)", best_word, score, len(candidates))
        return best_word

    # --- Info-gathering mode: 0 candidates (answer not in word list) ---
    log.warning("0 candidates — info-gathering mode (constraints still respected)")

    # Step 1: try the strict filter (pattern-exact, will fail if answer not in list)
    constrained_strict = _apply_all_constraints(all_words, history)
    untried_strict = [w for w in constrained_strict if w not in previous_guesses]

    # Step 2: fall back to loose constraint check
    if not untried_strict:
        constrained_loose = _words_respecting_constraints(all_words, history)
        untried_loose = [w for w in constrained_loose if w not in previous_guesses]
        pool = untried_loose
        log.debug("Info-gathering loose pool: %d words", len(pool))
    else:
        pool = untried_strict
        log.debug("Info-gathering strict pool: %d words", len(pool))

    # Step 3: absolute fallback — anything not yet tried
    if not pool:
        pool = [w for w in all_words if w not in previous_guesses]
        log.warning("Info-gathering: no constrained words left, using unconstrained pool (%d)", len(pool))

    if not pool:
        pool = all_words

    # Score against pool (cap for speed)
    score_pool = pool[:400] if len(pool) > 400 else pool
    best = max(score_pool, key=lambda w: _entropy(w, score_pool))
    log.info("Info-gathering guess: '%s'  (pool size=%d)", best, len(pool))
    return best
