"""Read daily targets, aim the real camera, and submit browser mouse clicks."""

import math
from playwright.async_api import Page


async def tap(page: Page, target: dict) -> None:
    lat, lng = target["lat"], target["lng"]
    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError(f"Invalid target coordinates: {target}")
    await page.evaluate(
        "p => { window.myGlobe.pointOfView({...p, altitude: 2.45}, 0); }",
        {"lat": lat, "lng": lng},
    )
    await page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    await page.locator(".tutorial-prompt").wait_for(state="hidden")
    await page.wait_for_function("() => !window.TapGuard.shouldBlockTap({})")
    point = await page.evaluate(
        """p => {
            const xy = latLngToScreenCoords(p.lat, p.lng);
            if (!xy) throw new Error('Target is not visible on the globe');
            const canvas = window.myGlobe.renderer().domElement;
            const rect = canvas.getBoundingClientRect();
            return {x: rect.left + xy.x, y: rect.top + xy.y};
        }""",
        {"lat": lat, "lng": lng},
    )
    await page.mouse.click(point["x"], point["y"])


async def play(page: Page) -> dict:
    # A genuinely fresh context shows onboarding. Complete it through the UI.
    await page.locator(".tutorial-prompt").wait_for(state="visible")
    print("  Tutorial: New York City", flush=True)
    await tap(page, await page.evaluate("tutorialCity"))
    await page.locator(".tutorial-go-button").click()
    date = await page.locator("#topbar_right").inner_text()
    print(f"  {date}", flush=True)
    rounds = []
    for number in range(1, 6):
        await page.wait_for_function(
            """n => gameState.round === n && runtime.activeRoundCity !== null
                && runtime.currentlyScoring === 0 && PARAMS.tutorial == 0""",
            arg=number,
        )
        prompt = (await page.locator("#instruction").inner_text()).strip()
        target = await page.evaluate(
            """() => ({name: runtime.activeRoundCity.name,
                lat: runtime.activeRoundCity.lat, lng: runtime.activeRoundCity.lng,
                multiplier: getRoundScoreMultiplier()})"""
        )
        await tap(page, target)
        await page.wait_for_function("n => gameState.roundData.length === n", arg=number)
        result = await page.evaluate("gameState.roundData.at(-1)")
        if result["round"] != number or result["cityName"] != target["name"]:
            raise RuntimeError("Scored round does not match the displayed target")
        rounds.append({"prompt": prompt, "target": target, "result": result})
        points = result["score"] * target["multiplier"]
        print(
            f"  {number}/5 {target['name']} | ({target['lat']:.6f}, {target['lng']:.6f})"
            f" | {result['score']}/100 ×{target['multiplier']} = {points}"
            f" | {result['distance']:.3f} km",
            flush=True,
        )
    await page.locator("#share-button").wait_for(state="visible")
    # The end screen resets its score counter to zero and animates back up.
    await page.wait_for_function("UI.displayedScore === gameState.finalScore")
    state = await page.evaluate("gameState")
    displayed = await page.locator("#ui_score").inner_text()
    total = sum(r["result"]["score"] * r["target"]["multiplier"] for r in rounds)
    if state["totalScore"] != total or state["finalScore"] != total or int(displayed) != total:
        raise RuntimeError("Round scores, final state, and displayed score disagree")
    print(f"  Total: {total}/1000", flush=True)
    return {"date": date, "rounds": rounds, "total": total}
