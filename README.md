# MapTap bot

Python + Playwright solver for MapTap's five daily rounds, managed with uv.

```sh
uv run maptap
```

Chromium installs automatically on first use. Internet access is required to load
MapTap's current frontend, daily puzzle, and globe textures. On Linux, if Chromium
reports missing system libraries, install them with `uv run playwright install-deps chromium`.

```sh
uv run maptap --headed                  # watch it play (requires a desktop)
uv run maptap --runs 3                  # three independent, fresh sessions
uv run maptap --day September20         # another date in the local mirror
uv run maptap --output artifacts/demo   # choose the evidence directory
```

Each run prints the place, target latitude/longitude, base score, multiplier,
weighted score, and the game's distance in kilometres. It saves `result.json`
and `final.png` under `<output>/run-N/`. The JSON includes actual guessed
coordinates, prompts, per-round scores, blocked requests, and JavaScript errors.
Failures produce `failure.png` and `failure.txt` and exit with an error.
Output files with the same names are replaced on subsequent invocations.

## Isolation

Following `PROMPT.md`, this runs a local mirror of the actual game at
`http://127.0.0.1:8765`, served inside Playwright through request interception;
there is no HTTP server to start. It retrieves static assets using Python and
executes the original game code locally. Each run has a new browser context with
empty cookies and storage, including the complete New York City tutorial.

Only static GET requests to MapTap, its tile host, and Google's Firebase script
CDN are permitted. All writes, Firebase services, analytics, other hosts,
WebSockets, and service workers are blocked. Redirects are not followed.
No account is used and scores cannot reach the live leaderboards. `devmode=1` is
also set, but network isolation does not depend on the game's developer mode.
Blocked services can trigger the site's "Something didn't load" banner; this
does not affect local scoring.

## Reconnaissance (September 21, 2026)

- **Daily data:** `https://maptap.gg/data/this_day_in_history/<Month><Day>.js`,
  loaded by `js/data-loader.js`. These scripts assign `cities`, including names
  and exact `lat`/`lng` answers before guessing. The selected current target is
  `runtime.activeRoundCity`. Geocoding is unnecessary. `scoreLat`/`scoreLng`
  position score labels; they are not the answers.
- **Globe:** the site now uses **TileGlobe**, replacing globe.gl.
  `window.myGlobe` is explicitly exposed by the page. The solver calls
  `pointOfView({lat, lng, altitude: 2.45}, 0)` and uses the page's
  `latLngToScreenCoords()` helper, which projects via `GlobeCoordinates` and the
  real camera. Canvas bounding-box offsets convert those coordinates to a
  Playwright mouse click. It does not call scoring handlers or modify scores.
- **State:** the classic scripts' lexical globals `runtime` and `gameState` are
  accessible through `page.evaluate` even though they are not window properties.
  The solver waits for each round's scoring lock to clear, then reads the game's
  own `gameState.roundData` after clicking. It checks the five weighted scores
  against both `finalScore` and the rendered total.
- **Progress:** rounds advance automatically after the original reveal animation
  (roughly eight seconds). No Next button is needed. Fresh sessions use the
  default single-tap mode; the bot waits for the game's tap guard.

| Element | Selector |
| --- | --- |
| Tutorial welcome | `.tutorial-prompt` |
| Tutorial completion | `.tutorial-go-button` |
| Location prompt | `#instruction` |
| Difficulty / multiplier | `#info_header` |
| Puzzle number | `#topbar_center` |
| Date | `#topbar_right` |
| Globe | `#globeViz canvas` |
| Total score | `#ui_score` |
| Completed-game control | `#share-button` |

The date's initial `#bar_right_text` span is replaced during initialization;
read its stable parent `#topbar_right` instead.

`--day` selects the upstream month/day file using the game's localhost date
option. Those files are mutable and are not a year-specific historical archive.
The default uses the browser's local date. This targets the observed daily game;
upstream changes to globals or DOM selectors may require an update.

## Checks

Browser validation on September 21, 2026:

| Puzzle | Fresh sessions | Results |
| --- | --- | --- |
| September 21 | 3 | 1000/1000 each |
| September 20 | 1 | 1000/1000 |

All 20 scoring taps earned 100/100 with game-reported distance 0 km, and all
four sessions had no JavaScript errors. Reports and screenshots are in
`artifacts/validation-today/` and `artifacts/validation-september20/` locally
(generated artifacts are excluded from Git). This verifies these puzzles,
not every historical or future daily file.

```sh
uv run python -m unittest discover -s tests -v
```

These tests verify the static mirror's cache and network isolation, including
blocked writes, backend requests, hostname spoofing, and redirects.
