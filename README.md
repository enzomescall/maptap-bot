# MapTap bot

Python + Playwright solver for MapTap daily and Frontier modes, managed with uv.

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
uv run maptap --mode frontier --rounds 20
```

Daily runs print the place, target coordinates, score, and distance. Frontier
runs print the location, score, remaining seconds, fuel, and response time.
Frontier defaults to 12 rounds; `--rounds` sets a different limit. Each run
saves `result.json` and `final.png` under `<output>/run-N/`, including per-round
scores, blocked requests, and JavaScript errors.
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
Daily mode sets `devmode=1`, but isolation does not depend on it. Frontier
receives a synthetic local test user because the page requires login; its auth
observer is intercepted before it can contact Firebase. The URL includes
`unlimited=1` so local daily-run limits cannot block repeat tests. No scores
can reach the live leaderboards.
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
- **Frontier:** `/frontier?from=practice` uses a client-side pool of about 6,900
  locations. The displayed name can be matched to its coordinates in that pool.
  Its round timer starts at 30 seconds, drops four seconds every three rounds,
  and bottoms out at eight seconds. Overtime burns 25 fuel per second; inaccurate
  taps also cost fuel. The bot submits through the page's `_frTap` test hook,
  which follows the actual score, fuel, and round-advance code. It stops at the
  configured limit before an endless perfect run can affect a leaderboard.

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

Browser validation:

| Mode | Fresh sessions | Results |
| --- | --- | --- |
| Daily, September 21 | 3 | 1000/1000 each |
| Daily, September 20 | 1 | 1000/1000 |
| Frontier, 20 rounds | 1 | 20 × 100 points, 250 fuel left |

Frontier taps took under 165 ms, including at the eight-second clock floor.
There were no JavaScript errors. Reports and screenshots are under `artifacts/`
locally; generated artifacts are excluded from Git.

```sh
uv run python -m unittest discover -s tests -v
```

These tests verify the static mirror's cache and network isolation, including
blocked writes, backend requests, hostname spoofing, and redirects.
