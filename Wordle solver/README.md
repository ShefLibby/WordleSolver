# Wordle Solver

Automatically plays [wordleunlimited.org](https://wordleunlimited.org/) using Google Chrome. It opens the site, guesses words using an information-theory (entropy) algorithm, reads the green/yellow/gray tile feedback, and keeps solving games back-to-back via the Play Again button — no human input needed.

---

## Quick Start — Run the exe (no Python required)

**Prerequisites:** Google Chrome must be installed.

1. Copy `dist\WordleSolver.exe` to any folder you like.
2. Double-click `WordleSolver.exe`.
3. Chrome will open automatically and start solving.
4. Press **Ctrl+C** in the console window to stop, then press **ENTER** to close the browser.

A `logs\` folder is created automatically next to the exe. Each run produces a timestamped log file with full debug output.

> **Note:** Do not click inside or interact with the Chrome window while the solver is running.

---

## Running from Source (developers)

**Prerequisites:** Python 3.10+, Google Chrome.

```bat
pip install -r requirements.txt
python main.py
```

ChromeDriver is downloaded automatically by `webdriver-manager` — no manual setup needed.

---

## Rebuilding the exe

Run the included batch file (handles all dependencies and packaging):

```bat
build.bat
```

Output: `dist\WordleSolver.exe`

---

## Updating the Word List

The word list is sourced directly from wordleunlimited.org. To refresh it:

```bat
python fetch_words.py
```

Then rebuild the exe with `build.bat` so the new list gets bundled in.

---

## Logs

| Location | Content |
|---|---|
| `logs\wordle_YYYY-MM-DD_HH-MM-SS.log` | Full DEBUG output — every guess, tile read, and filter step |
| Console window | INFO level — guess choices and game outcomes |

Log files are created next to the exe (or next to `main.py` when running from source).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Chrome doesn't open | Make sure Google Chrome is installed |
| "ChromeDriver" error | Check your internet connection — ChromeDriver is downloaded on first run |
| Solver gets stuck / no progress | Press Ctrl+C, check the latest log file in `logs\` for the error |
| "Failed" result on a game | The answer wasn't in the word list — run `fetch_words.py` and rebuild |
| Window closes instantly | Run from a terminal (`cmd` or PowerShell) so you can see the error message |
