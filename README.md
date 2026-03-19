# pydoll-scraper

Small HTTP service that renders pages with Pydoll (Chromium CDP) and returns HTML.

It is designed as a simple browser-rendering backend for SearXNG custom engines or crawler workers.

## API

- `GET /health`
- `POST /scrape`

Request body:

```json
{
  "url": "https://example.com",
  "wait_after_load": 2,
  "timeout": 30000
}
```

Response:

```json
{
  "html": "...",
  "status": 200,
  "url": "https://example.com"
}
```

## Run

```bash
docker build -t pydoll-scraper .
docker run --rm -p 8080:8080 pydoll-scraper
```

## Intended usage

- Internal cluster service (e.g. `pydoll-svc.searxng:8080`)
- Called from search/crawl pipelines via `POST /scrape`
- Returns rendered HTML for downstream parsing and extraction

## Environment

- `PORT` (default `8080`)
- `BROWSER_BINARY` (default `/usr/bin/google-chrome`)
- `BROWSER_START_TIMEOUT` (default `30`)
