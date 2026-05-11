import sys
import time

from logger import get_logger
from solver import load_words, filter_words, best_guess
from browser_controller import BrowserController

log = get_logger(__name__)

MAX_GUESSES = 6
STATE_SYMBOLS = {
    "correct": "\U0001f7e9",
    "present": "\U0001f7e8",
    "absent":  "⬛",
}


def _print_result(guess: str, result: list) -> None:
    tiles = "".join(STATE_SYMBOLS.get(s, "?") for _, s in result)
    letters = "  ".join(f"{l.upper()}:{s[0].upper()}" for l, s in result)
    log.info("%s  %s  |  %s", tiles, guess.upper(), letters)


def solve_one(browser: BrowserController, all_words: list, game_num: int) -> bool:
    """Run one full solve attempt. Returns True if solved."""
    log.info("=" * 60)
    log.info("Game #%d starting", game_num)
    log.info("=" * 60)

    candidates = list(all_words)
    previous_guesses: list = []
    history: list = []
    solved = False

    for attempt in range(1, MAX_GUESSES + 1):
        log.info("--- Attempt %d / %d  (%d candidates) ---", attempt, MAX_GUESSES, len(candidates))

        guess = best_guess(candidates, all_words, attempt, previous_guesses, history)
        previous_guesses.append(guess)
        log.info("Guessing: '%s'", guess.upper())

        browser.type_guess(guess)
        result = browser.read_row(attempt - 1)
        _print_result(guess, result)

        states = [s for _, s in result]
        history.append((guess, states))

        if all(s == "correct" for s in states):
            log.info("Game #%d SOLVED in %d attempt(s)!", game_num, attempt)
            solved = True
            break

        if browser.check_win():
            log.info("Win overlay detected — game #%d solved!", game_num)
            solved = True
            break

        candidates = filter_words(candidates, guess, states)

        if not candidates:
            log.warning(
                "Game #%d: no candidates left after attempt %d — "
                "answer is probably not in our word list. "
                "Continuing to exhaust remaining guesses…",
                game_num, attempt,
            )

        if browser.check_loss():
            log.warning("Loss overlay detected — game #%d failed", game_num)
            break

    if not solved:
        log.warning(
            "Game #%d FAILED: could not find answer within %d guesses. "
            "Consider expanding the word list if this happens often.",
            game_num, MAX_GUESSES,
        )
        browser.save_debug_screenshot(f"game{game_num}_failed")

    return solved


def run() -> None:
    log.info("Wordle Solver — starting (press Ctrl+C to stop)")
    all_words = load_words()

    browser = BrowserController()
    try:
        browser.open_wordle()

        game_num = 1
        wins = 0
        session_start = time.time()

        while True:
            game_start = time.time()
            solved = solve_one(browser, all_words, game_num)
            elapsed = time.time() - game_start

            if solved:
                wins += 1

            log.info(
                "Game #%d finished in %.1fs  |  session score: %d/%d",
                game_num, elapsed, wins, game_num,
            )

            time.sleep(3.0)

            if not browser.click_play_again():
                log.error("Could not start next game — exiting loop")
                break

            browser.wait_for_board_reset()
            game_num += 1

    except KeyboardInterrupt:
        elapsed = time.time() - session_start if "session_start" in dir() else 0
        log.info("Stopped by user after %d game(s), %d win(s), %.0fs", game_num - 1, wins, elapsed)
    except Exception as e:
        log.exception("Unexpected error: %s", e)
        try:
            browser.save_debug_screenshot("crash")
        except Exception:
            pass
        raise
    finally:
        input("\nPress ENTER to close the browser and exit…")
        browser.quit()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log.info("Interrupted")
        sys.exit(0)
    except Exception:
        log.exception("Fatal error")
        input("\nFATAL ERROR — check logs. Press ENTER to exit…")
        sys.exit(1)
