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

from aiohttp import web
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pydoll-scraper")


def build_options() -> ChromiumOptions:
    options = ChromiumOptions()
    options.binary_location = os.environ.get("BROWSER_BINARY", "/usr/bin/google-chrome")
    options.headless = True
    options.start_timeout = int(os.environ.get("BROWSER_START_TIMEOUT", "30"))
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.set_accept_languages("en-US,en")
    return options


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
        await browser.start()
        page = await browser.get_page()

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
