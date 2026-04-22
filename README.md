# Markaz Self-Help Books Scraper

Scrapes product data (title, price, image URL, description) from:
https://www.markaz.app/shop/home-page/Books%20%26%20Stationery/Self-Help%20Learning%20Books

---

## Why Playwright?

markaz.app is a **React SPA** — the product grid is rendered entirely by JavaScript.
A plain `requests` call returns an HTML shell with no product data.
Playwright drives a real Chromium browser, waits for JS hydration, and handles:
- Lazy-loaded images (`data-src` attributes)
- Infinite scroll / load-more triggers
- Dynamic pagination

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install the Playwright browser binary (one-time)

```bash
playwright install chromium
```

---

## Usage

### Basic (5 pages, default output files)

```bash
python scraper.py
```

### Custom pages and output paths

```bash
python scraper.py --pages 3 --output data.json --csv data.csv
```

### CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `--pages` | `5` | Max pages to scrape |
| `--output` | `products.json` | JSON output path |
| `--csv` | `products.csv` | CSV output path |

---

## Output Format

### JSON (`products.json`)

```json
[
  {
    "title": "Atomic Habits",
    "price": "1200",
    "image_url": "https://cdn.markaz.app/...",
    "description": "An easy and proven way to build good habits"
  }
]
```

### CSV (`products.csv`)

```
title,price,image_url,description
Atomic Habits,1200,https://...,An easy and proven way...
```

---

## Features

| Feature | Implementation |
|---------|---------------|
| JS rendering | Playwright Chromium (headless) |
| Lazy load / infinite scroll | `scroll_to_bottom()` — scrolls until no new height change |
| Pagination | Detects Next button/link via multiple selectors |
| Retry logic | 3 attempts with exponential backoff |
| User-agent rotation | Random choice from 4 real browser UAs |
| Rate limiting | 1–2.5s random sleep between page loads |
| Data cleaning | Whitespace normalised; currency prefix stripped from price |
| Logging | `INFO`/`ERROR` via Python `logging` module |
| Graceful error handling | `try/except` around every network + parse operation |

---

## Project Structure

```
markaz_scraper/
├── scraper.py        # Main script (modular functions + async orchestration)
├── requirements.txt  # Python deps
└── README.md         # This file
```

---

## Notes

- Run in a stable network environment; markaz.app may be geo-restricted.
- First run downloads the Chromium binary (~130 MB) via `playwright install chromium`.
- Respect the site's `robots.txt` and Terms of Service.
