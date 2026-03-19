"""
Pydoll Scraper HTTP Service (POC)

POST /scrape
  Body: {
    "url": "https://...",
    "wait_after_load": 2,
    "timeout": 30000
  }
  Returns: {"html": "...", "status": 200, "url": "..."}

GET /health
  Returns: {"status": "ok"}
"""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path

from aiohttp import web
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pydoll-scraper")


def build_options() -> ChromiumOptions:
    seed_persona_files()

    options = ChromiumOptions()
    options.binary_location = os.environ.get("BROWSER_BINARY", "/usr/bin/google-chrome")
    options.headless = True
    options.start_timeout = int(os.environ.get("BROWSER_START_TIMEOUT", "30"))
    options.add_argument(f"--user-data-dir={os.environ.get('CHROME_USER_DATA_DIR', '/var/lib/chrome-persona')}")
    options.add_argument(f"--profile-directory={os.environ.get('CHROME_PROFILE_DIR', 'Default')}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.set_accept_languages("en-US,en")

    # Optional extra preferences merged on top of the seeded persona.
    prefs_path = os.environ.get("PERSONA_PREFS_JSON", "")
    if prefs_path:
        try:
            with open(prefs_path, "r", encoding="utf-8") as fh:
                options.browser_preferences = json.load(fh)
        except Exception as exc:
            logger.warning("Could not load PERSONA_PREFS_JSON (%s): %s", prefs_path, exc)

    return options


def seed_persona_files() -> None:
    """Seed a persistent Chrome user-data dir from mounted persona files (one-time).

    Expected seed files in PERSONA_SEED_DIR:
      - Local State
      - Preferences
      - Secure Preferences

    They are copied into:
      CHROME_USER_DATA_DIR/
      CHROME_USER_DATA_DIR/<CHROME_PROFILE_DIR>/
    """

    seed_dir = Path(os.environ.get("PERSONA_SEED_DIR", "/persona-seed"))
    user_data_dir = Path(os.environ.get("CHROME_USER_DATA_DIR", "/var/lib/chrome-persona"))
    profile_dir_name = os.environ.get("CHROME_PROFILE_DIR", "Default")
    profile_dir = user_data_dir / profile_dir_name
    marker = user_data_dir / ".persona_seeded"

    user_data_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    if marker.exists():
        return

    if not seed_dir.exists():
        logger.info("No persona seed directory found at %s", seed_dir)
        marker.write_text("not-seeded", encoding="utf-8")
        return

    copied = 0
    local_state = seed_dir / "Local State"
    preferences = seed_dir / "Preferences"
    secure_preferences = seed_dir / "Secure Preferences"

    if local_state.exists():
        shutil.copy2(local_state, user_data_dir / "Local State")
        copied += 1

    if preferences.exists():
        shutil.copy2(preferences, profile_dir / "Preferences")
        copied += 1

    if secure_preferences.exists():
        shutil.copy2(secure_preferences, profile_dir / "Secure Preferences")
        copied += 1

    logger.info("Persona seeding complete: %d files copied from %s", copied, seed_dir)
    marker.write_text("seeded", encoding="utf-8")


async def handle_scrape(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    url = body.get("url")
    if not url:
        return web.json_response({"error": "Missing 'url' field"}, status=400)

    wait_after_load = float(body.get("wait_after_load", 2))
    timeout_ms = int(body.get("timeout", 30000))

    logger.info("Scraping with Pydoll: %s", url)

    browser = None
    try:
        options = build_options()
        browser = Chrome(options=options)
        page = await browser.start()

        await page.go_to(url, timeout=max(10, timeout_ms // 1000))
        if wait_after_load > 0:
            await asyncio.sleep(wait_after_load)

        html = await page.page_source
        final_url = await page.current_url

        logger.info("Pydoll scraped %s (%d bytes)", final_url, len(html))
        return web.json_response({"html": html, "status": 200, "url": final_url})

    except Exception as exc:
        logger.exception("Error scraping %s", url)
        return web.json_response({"error": str(exc)}, status=500)
    finally:
        if browser is not None:
            try:
                await browser.stop()
            except Exception:
                pass


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/scrape", handle_scrape)
    app.router.add_get("/health", handle_health)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app = create_app()
    logger.info("Starting Pydoll Scraper on port %d", port)
    web.run_app(app, host="0.0.0.0", port=port)
