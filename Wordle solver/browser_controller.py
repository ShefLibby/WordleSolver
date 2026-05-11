import time
import os
import sys
from typing import List, Tuple, Optional

from selenium.webdriver.chrome.webdriver import WebDriver as Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    JavascriptException,
)
from webdriver_manager.chrome import ChromeDriverManager

from logger import get_logger

log = get_logger(__name__)

WORDLE_URL = "https://wordleunlimited.org/"
TILE_FLIP_WAIT = 2.8
PAGE_LOAD_WAIT = 12
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# JavaScript helpers — all shadow-DOM traversal happens in the browser
# ---------------------------------------------------------------------------

# Read one completed row.
# game-app.shadowRoot → game-row[n] (has `letters` attr)
# game-row.shadowRoot → game-tile[i]
# game-tile.shadowRoot → div.tile[data-state]
_JS_READ_ROW = """
try {
    var rowIdx = arguments[0];
    var app = document.querySelector('game-app');
    if (!app || !app.shadowRoot) return {error: 'no game-app shadow root'};
    var rows = app.shadowRoot.querySelectorAll('game-row');
    if (!rows || rows.length <= rowIdx) return {error: 'row ' + rowIdx + ' not found (' + (rows ? rows.length : 0) + ' rows)'};
    var row = rows[rowIdx];
    var letters = (row.getAttribute('letters') || '').toLowerCase();
    if (!row.shadowRoot) return {error: 'game-row has no shadow root'};
    var tiles = row.shadowRoot.querySelectorAll('game-tile');
    if (!tiles || tiles.length !== 5) return {error: 'expected 5 tiles, got ' + (tiles ? tiles.length : 0)};
    var result = [];
    for (var i = 0; i < 5; i++) {
        var tile = tiles[i];
        if (!tile.shadowRoot) return {error: 'game-tile[' + i + '] has no shadow root'};
        var div = tile.shadowRoot.querySelector('.tile');
        if (!div) return {error: 'no .tile div in game-tile[' + i + ']'};
        var state = div.getAttribute('data-state') || '';
        var letter = letters.charAt(i) || '';
        result.push({letter: letter, state: state});
    }
    return {tiles: result};
} catch(e) { return {error: e.toString()}; }
"""

# Dismiss the help/instructions modal that opens on first visit.
# game-app.shadowRoot → game-modal[open] → shadow root → .close-icon
_JS_DISMISS_MODAL = """
try {
    var app = document.querySelector('game-app');
    if (!app || !app.shadowRoot) return 'no app shadow root';
    var modal = app.shadowRoot.querySelector('game-modal[open]');
    if (!modal) return 'no open modal';
    if (!modal.shadowRoot) return 'modal has no shadow root';
    var closeBtn = modal.shadowRoot.querySelector('.close-icon');
    if (!closeBtn) return 'no .close-icon in modal shadow root';
    closeBtn.click();
    return 'clicked';
} catch(e) { return 'error: ' + e.toString(); }
"""

_JS_ROW_COUNT = """
try {
    var app = document.querySelector('game-app');
    if (!app || !app.shadowRoot) return 0;
    return app.shadowRoot.querySelectorAll('game-row').length;
} catch(e) { return 0; }
"""

_JS_CHECK_TOAST = """
try {
    var app = document.querySelector('game-app');
    if (!app || !app.shadowRoot) return '';
    var toaster = app.shadowRoot.querySelector('#game-toaster, .toaster');
    return toaster ? (toaster.innerText || '').toLowerCase() : '';
} catch(e) { return ''; }
"""

# Recursively search all shadow roots for a button/link containing the given text.
_JS_CLICK_BY_TEXT = """
function findAndClick(root, text) {
    var els = root.querySelectorAll('button, a, [role=button]');
    for (var i = 0; i < els.length; i++) {
        if ((els[i].innerText || els[i].textContent || '').toLowerCase().includes(text)) {
            els[i].click();
            return 'clicked:' + (els[i].innerText || '').trim();
        }
    }
    var all = root.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
        if (all[i].shadowRoot) {
            var r = findAndClick(all[i].shadowRoot, text);
            if (r) return r;
        }
    }
    return null;
}
return findAndClick(document, arguments[0].toLowerCase());
"""

# Wait until all board tiles are empty again (new game loaded).
_JS_BOARD_RESET = """
try {
    var app = document.querySelector('game-app');
    if (!app || !app.shadowRoot) return false;
    var rows = app.shadowRoot.querySelectorAll('game-row');
    if (!rows || rows.length === 0) return false;
    var firstRow = rows[0];
    if (!firstRow.shadowRoot) return false;
    var tiles = firstRow.shadowRoot.querySelectorAll('game-tile');
    if (!tiles || tiles.length === 0) return false;
    var tile = tiles[0];
    if (!tile.shadowRoot) return false;
    var div = tile.shadowRoot.querySelector('.tile');
    if (!div) return false;
    return div.getAttribute('data-state') === 'empty';
} catch(e) { return false; }
"""


class BrowserController:
    def __init__(self):
        self.driver: Optional[Chrome] = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def open_wordle(self) -> None:
        log.info("Launching Chrome…")
        options = Options()
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = Chrome(service=service, options=options)
            log.info("Chrome launched successfully")
        except WebDriverException as e:
            log.exception("Failed to launch Chrome: %s", e)
            raise

        log.info("Navigating to %s", WORDLE_URL)
        self.driver.get(WORDLE_URL)

        self._wait_for_game_app()
        self._dismiss_modal()
        log.info("Wordle board is ready")

    def _wait_for_game_app(self) -> None:
        log.debug("Waiting for game-app shadow root and rows…")
        deadline = time.time() + PAGE_LOAD_WAIT
        while time.time() < deadline:
            count = self.driver.execute_script(_JS_ROW_COUNT)
            if count and count > 0:
                log.debug("game-app ready (%d rows)", count)
                return
            time.sleep(0.5)
        log.warning("game-app did not appear within %ds — proceeding anyway", PAGE_LOAD_WAIT)

    def _dismiss_modal(self) -> None:
        """Close the help/instructions modal that appears on first load."""
        log.debug("Attempting to dismiss intro modal…")
        time.sleep(1.5)   # let JS fully initialise

        for attempt in range(1, 5):
            result = self.driver.execute_script(_JS_DISMISS_MODAL)
            log.debug("Modal dismiss attempt %d: %s", attempt, result)
            if result == "clicked":
                log.info("Intro modal dismissed")
                time.sleep(0.6)
                return
            if result == "no open modal":
                log.info("No open modal found — board already visible")
                return
            time.sleep(0.8)

        log.warning("Could not dismiss modal via shadow DOM — trying body click fallback")
        try:
            self.driver.find_element(By.TAG_NAME, "body").click()
        except WebDriverException:
            pass
        time.sleep(0.5)

    # ------------------------------------------------------------------
    # Typing
    # ------------------------------------------------------------------

    def type_guess(self, word: str) -> None:
        log.info("Typing guess: '%s'", word)
        body = self.driver.find_element(By.TAG_NAME, "body")
        for char in word:
            body.send_keys(char)
            time.sleep(0.08)
        body.send_keys(Keys.RETURN)
        log.debug("Sent ENTER — waiting %.1fs for flip animation", TILE_FLIP_WAIT)
        time.sleep(TILE_FLIP_WAIT)

    # ------------------------------------------------------------------
    # Reading the board
    # ------------------------------------------------------------------

    def read_row(self, row_index: int) -> List[Tuple[str, str]]:
        """Return list of (letter, state) for the given row (0-indexed).
        States: 'correct', 'present', 'absent'
        """
        log.debug("Reading board row %d…", row_index)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                data = self.driver.execute_script(_JS_READ_ROW, row_index)
                log.debug("Row %d raw result: %s", row_index, data)

                if isinstance(data, dict) and "error" in data:
                    log.warning(
                        "Row %d attempt %d/%d JS error: %s",
                        row_index, attempt, MAX_RETRIES, data["error"]
                    )
                    self._save_screenshot(f"row{row_index}_attempt{attempt}")
                    time.sleep(1.2)
                    continue

                if isinstance(data, dict) and "tiles" in data:
                    tiles = data["tiles"]
                    # Validate all tiles have a real evaluated state
                    valid_states = {"correct", "present", "absent"}
                    if all(t.get("state") in valid_states for t in tiles):
                        result = [(t["letter"], t["state"]) for t in tiles]
                        log.info(
                            "Row %d: %s",
                            row_index,
                            "  ".join(f"{l.upper()}:{s}" for l, s in result)
                        )
                        return result
                    else:
                        states = [t.get("state") for t in tiles]
                        log.warning(
                            "Row %d attempt %d/%d: tiles not fully evaluated yet: %s",
                            row_index, attempt, MAX_RETRIES, states
                        )
                        time.sleep(1.2)
                        continue

            except (JavascriptException, WebDriverException) as e:
                log.error(
                    "Row %d attempt %d/%d exception: %s",
                    row_index, attempt, MAX_RETRIES, e, exc_info=True
                )
                self._save_screenshot(f"row{row_index}_attempt{attempt}_exc")
                time.sleep(1.2)

        raise RuntimeError(f"Failed to read board row {row_index} after {MAX_RETRIES} attempts")

    # ------------------------------------------------------------------
    # Game state helpers
    # ------------------------------------------------------------------

    def check_win(self) -> bool:
        try:
            toast = self.driver.execute_script(_JS_CHECK_TOAST)
            win_words = ("genius", "magnificent", "splendid", "great", "phew", "amazing")
            if any(w in toast for w in win_words):
                return True
            # Also check body text as fallback
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            return any(w in body_text for w in win_words)
        except WebDriverException:
            return False

    def check_loss(self) -> bool:
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            return "the answer was" in body_text or "better luck" in body_text
        except WebDriverException:
            return False

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _save_screenshot(self, name: str) -> None:
        try:
            if getattr(sys, "frozen", False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "logs", f"{name}.png")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.driver.save_screenshot(path)
            log.debug("Screenshot saved: %s", path)
        except Exception as e:
            log.warning("Could not save screenshot: %s", e)

    def save_debug_screenshot(self, label: str = "debug") -> None:
        self._save_screenshot(label)

    # ------------------------------------------------------------------
    # Play Again
    # ------------------------------------------------------------------

    def click_play_again(self) -> bool:
        """Find and click any 'Play Again' / 'New Game' button. Returns True on success."""
        log.info("Looking for Play Again button…")
        time.sleep(2.0)   # let result modal fully animate in

        for phrase in ("play again", "new game", "play more", "next"):
            try:
                result = self.driver.execute_script(_JS_CLICK_BY_TEXT, phrase)
                if result:
                    log.info("Play Again: found and clicked via text '%s' → %s", phrase, result)
                    time.sleep(1.0)
                    return True
            except (JavascriptException, WebDriverException) as e:
                log.debug("click_play_again JS error for '%s': %s", phrase, e)

        log.warning("Play Again button not found — reloading page as fallback")
        try:
            self.driver.get(WORDLE_URL)
            self._wait_for_game_app()
            self._dismiss_modal()
            return True
        except WebDriverException as e:
            log.error("Page reload failed: %s", e)
            return False

    def wait_for_board_reset(self, timeout: float = 8.0) -> bool:
        """Poll until the first tile is empty again (new game board loaded)."""
        log.debug("Waiting for board to reset…")
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.driver.execute_script(_JS_BOARD_RESET):
                    log.info("Board reset confirmed — new game ready")
                    return True
            except (JavascriptException, WebDriverException):
                pass
            time.sleep(0.4)
        log.warning("Board did not reset within %.1fs — proceeding anyway", timeout)
        return False

    def quit(self) -> None:
        if self.driver:
            log.info("Closing browser")
            try:
                self.driver.quit()
            except WebDriverException as e:
                log.warning("Error closing browser: %s", e)
            self.driver = None
