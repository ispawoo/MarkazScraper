# Markaz Self-Help Books Scraper

> Scrapes product data from markaz.app — Self-Help Learning Books category.
> Available in both **Desktop GUI** and **CLI** modes.

---

```
╔══════════════════════════════════════════════════════════╗
║               MARKAZ SCRAPER  v2.0                       ║
╠══════════════════════════════════════════════════════════╣
║  Developer  :  Yasir Ispawoo                             ║
║  GitHub     :  https://github.com/ispawoo               ║
║  Telegram   :  https://t.me/the_ispawoo                  ║
╚══════════════════════════════════════════════════════════╝
```

---

## Target

```
https://www.markaz.app/shop/home-page/Books%20%26%20Stationery/Self-Help%20Learning%20Books
```

---

## Why Playwright?

markaz.app is a React SPA — the product grid is rendered entirely by JavaScript.
A plain `requests` call returns an empty HTML shell with no product data.
Playwright drives a real Chromium browser, waits for JS hydration, and handles:

- Lazy-loaded images (`data-src` attributes)
- Infinite scroll / load-more triggers
- Dynamic pagination

---

## Installation

### Step 1 — Install Python

Download from **https://python.org/downloads** (version 3.10 or higher).

> **Windows users:** On the installer's first screen, tick **"Add Python.exe to PATH"** before clicking Install Now.

### Step 2 — Open Terminal / Command Prompt

- **Windows:** Press `Win + R`, type `cmd`, press Enter
- **Mac:** Press `Cmd + Space`, type Terminal, press Enter
- **Linux:** Press `Ctrl + Alt + T`

### Step 3 — Navigate to the project folder

```bash
cd Desktop\myScraper        # Windows
cd ~/Desktop/myScraper      # Mac / Linux
```

### Step 4 — Install dependencies

```bash
pip install playwright
```

### Step 5 — Download Chromium browser (one-time, ~130 MB)

```bash
playwright install chromium
```

If `playwright` is not recognized, try:

```bash
python -m playwright install chromium
```

### Step 6 — Run

**Desktop GUI (recommended):**
```bash
python scraper_gui.py
```

**Command Line:**
```bash
python scraper.py
```

---

## Quick start (copy-paste all at once)

```bash
pip install playwright
playwright install chromium
python scraper_gui.py
```

---

## Desktop GUI Guide

| Element | Description |
|---------|-------------|
| Max Pages | Number of pages to scrape (default: 5) |
| Output JSON / CSV | File paths where results will be saved |
| ▶ START SCRAPING | Begins scraping in background — UI stays responsive |
| ■ STOP | Gracefully stops after current page finishes |
| ⬇ SAVE JSON | Saves results to JSON file |
| ⬇ SAVE CSV | Saves results to CSV file |
| ✕ CLEAR RESULTS | Wipes current results from view |
| RESULTS tab | Table view of all scraped products |
| LOG tab | Real-time colour-coded log output |

---

## CLI Usage

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
|---------|----------------|
| JS rendering | Playwright Chromium (headless) |
| Lazy load / infinite scroll | Incremental scroll until page height stops growing |
| Pagination | Detects Next button/link via 7 selector patterns |
| Retry logic | 3 attempts with exponential backoff |
| User-agent rotation | Random choice from 4 real browser UAs |
| Rate limiting | 1–2.5s random sleep between page loads |
| Data cleaning | Whitespace normalised; currency prefix stripped |
| Logging | Colour-coded real-time output in GUI + file logging in CLI |
| Graceful error handling | try/except around every network and parse operation |
| Background threading | GUI never freezes during scraping |

---

## Project Structure

```
myScraper/
├── scraper_gui.py    # Desktop GUI application (tkinter + Playwright)
├── scraper.py        # CLI script (Playwright async)
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `pip` is not recognized | Reinstall Python and tick "Add Python to PATH" |
| `playwright` is not recognized | Use `python -m playwright install chromium` |
| Chromium executable not found | Run `playwright install chromium` |
| 0 products scraped | Check internet connection; site may be temporarily down |
| tkinter not found (Linux) | Run `sudo apt-get install python3-tk` |

---

## Notes

- Run in a stable network environment; markaz.app may be geo-restricted.
- Respect the site's `robots.txt` and Terms of Service.
- For questions or issues, reach out via the contact details above.

---

*Built with Python · Playwright · tkinter*
