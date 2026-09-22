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
from playwright.async_api import async_playwright

from .mirror import Mirror, ORIGIN
from .solver import play


def day(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%B%d")
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use a month and day, e.g. September21") from error
    return parsed.strftime("%B") + str(parsed.day)


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
                for index in range(1, args.runs + 1):
                    print(f"Run {index}/{args.runs}: fresh local mirror (backend writes blocked)", flush=True)
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 900},
                        locale="en-US", service_workers="block",
                    )
                    await mirror.install(context)
                    page = await context.new_page()
                    page.set_default_timeout(60000)
                    output = args.output / f"run-{index}"
                    output.mkdir(parents=True, exist_ok=True)
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    options = {"devmode": "1"}
                    if args.day:
                        options["overrideday"] = args.day
                    try:
                        await page.goto(ORIGIN + "/?" + urlencode(options), wait_until="domcontentloaded")
                        report = await play(page)
                        report["blocked_requests"] = sorted(mirror.blocked)
                        report["page_errors"] = errors
                        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
                        await page.screenshot(path=output / "final.png")
                    except Exception:
                        await page.screenshot(path=output / "failure.png")
                        (output / "failure.txt").write_text(
                            await page.locator("body").inner_text() + "\n" + "\n".join(errors)
                        )
                        raise
                    finally:
                        await context.close()
            finally:
                await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headed", action="store_true", help="Show Chromium (requires a desktop)")
    parser.add_argument("--runs", type=int, default=1, help="Repeat using fresh browser contexts")
    parser.add_argument("--day", type=day, help="Local mirror's puzzle date, e.g. September21")
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    asyncio.run(run(args))
