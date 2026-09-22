# Task: MapTap.gg auto-solver

Build a Python program that plays the daily puzzle on https://maptap.gg automatically. For each of the 5 rounds it should read the prompted location, find its coordinates, point the globe at that spot, and tap it to score as close to 1000 as possible.

## Stack
- Python, managed with **uv** (`uv init`, `uv add`, `uv run`). No pip or requirements.txt.
- Browser automation library is your choice; Playwright is the natural fit.
- The architecture is up to you.

## Code style
- Clean, concise, readable code. Small files, small functions.
- No defensive fallbacks, compatibility shims, or speculative abstraction. Remove any line that doesn't earn its place.
- Do reconnaissance first and build against what you actually find, not against guesses.

## What's known about MapTap.gg

### Game mechanics (corroborated by multiple sources)
- There are 5 locations per day, the same for everyone and seeded by date. Places are tied to "this day in history": usually cities, sometimes battle or event sites.
- Each round scores 0–100 based on distance. Round multipliers are ×1, ×1, ×2, ×3, ×3, for a maximum of 1000.
- The distance→score curve comes from community reverse-engineering, not official docs. It is approximately `score = 100 / (1 + (km/3867)^1.05)`. Being within about 20 km scores 100, 100 km ≈ 98, 500 km ≈ 90, 1000 km ≈ 81. City-level accuracy is enough; metre precision is not needed.
- A single tap on the globe places the guess, with no confirm button by default. An optional "confirm tap" setting adds a confirmation step. Settings also exist for ignoring taps briefly after a drag or pinch-zoom.
- The daily game is untimed. Other modes (Versus, Gauntlet, Frontier) are timed and out of scope.
- The globe can be dragged to rotate and scrolled or pinched to zoom.

### Tech stack
- **The globe is globe.gl** (three-globe / three.js, WebGL on a `<canvas>`). This is verified: the creator (GitHub "mostlyrand0m", John Donham) posted his init code in globe.gl issue #213 (Aug 2024):
```js
  const myGlobe = Globe()(globeContainer)
    .globeImageUrl('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
    .labelTypeFace('helvetiker_bold')
    .pointOfView({ lat: 0, lng: 0, altitude: 2 });
```
  That code is from 2024. Re-verify the variable name and whether the instance is reachable from `window`; a `const` declaration is not global by default.
- The frontend appears to be mostly static HTML with vanilla JS, not an obvious SPA framework. Pages include `/`, `/home`, `/history.html`, `/faq.html`, `/versus`, and `/profile`.
- The backend is Firebase (auth + Firestore), plus Google Analytics.
- Useful globe.gl APIs:
  - `pointOfView({lat, lng, altitude}, ms)` rotates the camera so that lat/lng sits at the center of the canvas.
  - `getScreenCoords(lat, lng, alt)` returns canvas pixel coordinates.
  - `pointsData()` and `labelsData()` return the data the globe is drawing.

### Unverified: confirm during recon
- **Whether the answer coordinates are client-side before guessing.** This is likely, because the distance appears instantly after a tap. Check whether they arrive via a Firestore request (`firestore.googleapis.com`), a JSON/JS asset, or a JS global. If the coordinates are exposed, read them directly and skip geocoding.
- The exact endpoint and payload schema for the daily puzzle.
- DOM selectors for the place-name prompt, the date, the round indicator, and any "next" controls.
- Whether the globe instance is reachable. If it isn't, one option is to hook globe.gl's `Globe` factory before the page boots so the instance gets captured.

### If coordinates aren't exposed
Read the place name from the DOM rather than using OCR, then geocode it. Use the historical date as context to disambiguate names like "Springfield" or "Battle of X"; an LLM call or Wikipedia lookup works well for this. Because anything within 20 km scores a perfect 100, city-centroid geocoding is sufficient.

## Constraints
- MapTap's Terms of Service prohibit cheating and manipulating leaderboards. Run the solver only on a throwaway account that stays off leaderboards, or against a local clone. Clones on GitHub such as `mitchliss/mtap` and `prestonthomas-cmd/mapTapClone` are good for development.
- There are no known existing MapTap solvers. `JackBurla/maptap-bot` only tracks scores.

## Deliverable
A uv project runnable with a single command (e.g. `uv run maptap`). It should play all 5 rounds and print each round's place, the coordinates used, and the resulting score. Include a short README covering what you found during recon: the data source, the globe access method, and the selectors.