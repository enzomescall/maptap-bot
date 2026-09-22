"""MapTap daily solver for an isolated local mirror."""

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlencode

import httpx
from playwright.async_api import Browser, async_playwright

from .mirror import Mirror, ORIGIN
from .solver import play, play_frontier


def day(value: str) -> str:
    try:
        parsed = datetime.strptime(value + "2000", "%B%d%Y")
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use a month and day, e.g. September21") from error
    return parsed.strftime("%B") + str(parsed.day)


async def session(browser: Browser, mirror: Mirror, args: argparse.Namespace, index: int) -> int:
    print(f"Run {index}/{args.runs}: fresh local mirror (backend writes blocked)", flush=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900}, locale="en-US", service_workers="block",
    )
    mirror.blocked.clear()
    await mirror.install(context)
    page = await context.new_page()
    page.set_default_timeout(60000)
    output = args.output / f"run-{index}"
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    options = {"from": "practice", "unlimited": "1"} if args.mode == "frontier" else {"devmode": "1"}
    if args.mode == "daily" and args.day:
        options["overrideday"] = args.day
    try:
        path = "/frontier" if args.mode == "frontier" else "/"
        await page.goto(ORIGIN + path + "?" + urlencode(options), wait_until="domcontentloaded")
        report = (await play_frontier(page, args.rounds) if args.mode == "frontier"
                  else await play(page))
        report["blocked_requests"] = sorted(mirror.blocked)
        report["page_errors"] = errors
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        await page.screenshot(path=output / "final.png")
        return report["total"] if args.mode == "daily" else report["score"]
    except Exception as error:
        await page.screenshot(path=output / "failure.png")
        (output / "failure.txt").write_text(
            str(error) + "\n" + await page.locator("body").inner_text() + "\n"
            + "\n".join(errors + sorted(mirror.blocked)) + "\n"
            + json.dumps(mirror.failed_assets, indent=2)
        )
        raise
    finally:
        await context.close()


async def run(args: argparse.Namespace) -> None:
    async with async_playwright() as p:
        if not Path(p.chromium.executable_path).exists():
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        async with httpx.AsyncClient(timeout=60) as client:
            mirror = Mirror(client)
            browser = await p.chromium.launch(
                headless=not args.headed, args=["--enable-unsafe-swiftshader"],
            )
            try:
                totals = [await session(browser, mirror, args, i) for i in range(1, args.runs + 1)]
                if args.mode == "daily":
                    print(f"Completed {len(totals)} games; perfect scores: {totals.count(1000)}/{len(totals)}.")
                else:
                    print(f"Frontier practice complete; best run score: {max(totals)}.")
            finally:
                await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headed", action="store_true", help="Show Chromium (requires a desktop)")
    parser.add_argument("--runs", type=int, default=1, help="Repeat using fresh browser contexts")
    parser.add_argument("--mode", choices=("daily", "frontier"), default="daily")
    parser.add_argument("--rounds", type=int, default=12, help="Frontier rounds before the local run ends")
    parser.add_argument("--day", type=day, help="Daily puzzle date, e.g. September21")
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")
    asyncio.run(run(args))
