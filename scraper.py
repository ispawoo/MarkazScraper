"""
Markaz.app Product Scraper
==========================
Target: Self-Help Learning Books category
Tech: Playwright (async) — required because markaz.app is a React SPA
      that renders product cards via JavaScript. requests+BS4 would get
      an empty shell; Playwright drives a real Chromium browser.

Author: Senior Python Engineer
"""

import asyncio
import json
import csv
import logging
import argparse
import random
import re
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PWTimeout

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("markaz_scraper")

# ──────────────────────────────────────────────
# Constants / Config
# ──────────────────────────────────────────────
BASE_URL = (
    "https://www.markaz.app/shop/home-page/"
    "Books%20%26%20Stationery/Self-Help%20Learning%20Books"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
]

# CSS / XPath selectors — identified by inspecting the React DOM
# Product cards are rendered inside a grid; each card has these data points.
SELECTORS = {
    # The outer wrapper for each product card
    "product_card": "[class*='ProductCard'], [class*='product-card'], "
                    "[class*='ProductItem'], [class*='product_card'], "
                    "div[class*='Card']",
    # Fallback broad selector used after JS hydration
    "product_card_broad": "div[class*='card'], article",
    # Title inside a card
    "title": "[class*='title'], [class*='Title'], [class*='name'], [class*='Name'], h2, h3",
    # Price
    "price": "[class*='price'], [class*='Price'], [class*='amount'], [class*='Amount']",
    # Image
    "image": "img",
    # Description / short text
    "description": "[class*='desc'], [class*='Desc'], [class*='detail'], p",
}

SCROLL_PAUSE = 1.5          # seconds between scroll steps
RATE_LIMIT_MIN = 1.0        # min seconds between page actions
RATE_LIMIT_MAX = 2.5        # max seconds between page actions
MAX_RETRIES = 3
PAGE_TIMEOUT = 60_000       # ms


# ──────────────────────────────────────────────
# Data Helpers
# ──────────────────────────────────────────────
def clean_text(text: Optional[str]) -> str:
    """Strip whitespace/newlines and normalise unicode spaces."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def clean_price(raw: str) -> str:
    """
    Normalise price string.
    e.g. "Rs. 1,200" → "1200"  |  "PKR 850.00" → "850.00"
    Returns the numeric string; currency prefix stripped.
    """
    if not raw:
        return ""
    # Remove common currency labels
    cleaned = re.sub(r"(Rs\.?|PKR|₨)\s*", "", raw, flags=re.IGNORECASE)
    # Remove thousands comma  e.g. 1,200 → 1200
    cleaned = cleaned.replace(",", "").strip()
    return cleaned


# ──────────────────────────────────────────────
# Browser / Page Setup
# ──────────────────────────────────────────────
async def new_browser(playwright) -> Browser:
    """Launch a stealth-ish Chromium browser."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )
    return browser


async def new_page(browser: Browser) -> Page:
    """Create a page with a random user-agent and sensible viewport."""
    ua = random.choice(USER_AGENTS)
    context = await browser.new_context(
        user_agent=ua,
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="Asia/Karachi",
    )
    page = await context.new_page()
    # Mask navigator.webdriver to reduce bot-detection risk
    await page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return page


# ──────────────────────────────────────────────
# Scroll Helper (infinite scroll / lazy load)
# ──────────────────────────────────────────────
async def scroll_to_bottom(page: Page, max_scrolls: int = 30) -> None:
    """
    Scroll down incrementally until no new content loads or max_scrolls hit.
    Handles lazy-loaded images and infinite-scroll product grids.
    """
    prev_height = 0
    no_change_count = 0

    for i in range(max_scrolls):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 1.2)")
        await asyncio.sleep(SCROLL_PAUSE)

        cur_height = await page.evaluate("document.body.scrollHeight")
        if cur_height == prev_height:
            no_change_count += 1
            if no_change_count >= 3:
                log.info("Scroll: no new content after 3 tries — stopping.")
                break
        else:
            no_change_count = 0
        prev_height = cur_height
        log.debug("Scroll %d/%d — height %d", i + 1, max_scrolls, cur_height)

    # Scroll back to top so any sticky nav doesn't interfere
    await page.evaluate("window.scrollTo(0, 0)")


# ──────────────────────────────────────────────
# Product Extraction
# ──────────────────────────────────────────────
async def extract_products_from_page(page: Page) -> list[dict]:
    """
    Wait for product cards to render, then parse each card's data.
    Returns a list of product dicts.
    """
    products: list[dict] = []

    # Wait for *something* to appear that looks like a product grid
    try:
        await page.wait_for_selector(
            "img, [class*='product'], [class*='Product']",
            timeout=PAGE_TIMEOUT,
        )
    except PWTimeout:
        log.warning("Timed out waiting for product selector — page may be empty.")
        return products

    # Scroll to trigger lazy loading
    await scroll_to_bottom(page)

    # ── Try to locate product cards via JS evaluation ──────────────────
    # We query all candidate card elements and extract structured data
    # directly in the browser context for reliability.
    raw_data = await page.evaluate(
        """() => {
        const results = [];

        // Helper: get first matching text inside an element
        function getText(el, selectors) {
            for (const sel of selectors) {
                try {
                    const found = el.querySelector(sel);
                    if (found && found.innerText && found.innerText.trim()) {
                        return found.innerText.trim();
                    }
                } catch(e) {}
            }
            return '';
        }

        // Helper: get image src (handles lazy-load data-src / srcset)
        function getImg(el) {
            const img = el.querySelector('img');
            if (!img) return '';
            return img.getAttribute('src') ||
                   img.getAttribute('data-src') ||
                   img.getAttribute('data-lazy-src') ||
                   (img.srcset ? img.srcset.split(' ')[0] : '') || '';
        }

        // Candidate card selectors (broad → narrow fallback)
        const cardSelectors = [
            '[class*="ProductCard"]',
            '[class*="product-card"]',
            '[class*="ProductItem"]',
            '[class*="product_item"]',
            '[class*="ItemCard"]',
            '[class*="item-card"]',
            'li[class*="product"]',
            'div[class*="grid"] > div',
            'div[class*="list"] > div',
        ];

        let cards = [];
        for (const sel of cardSelectors) {
            const found = document.querySelectorAll(sel);
            if (found.length > 2) {
                cards = Array.from(found);
                break;
            }
        }

        // Last-resort: any element containing a price-looking text near an img
        if (cards.length === 0) {
            document.querySelectorAll('div, li, article').forEach(el => {
                const txt = el.innerText || '';
                const hasPrice = /Rs\\.?|PKR|₨|\\d+/.test(txt);
                const hasImg = !!el.querySelector('img');
                const hasTitle = txt.length > 5 && txt.length < 300;
                if (hasPrice && hasImg && hasTitle && el.children.length >= 1) {
                    cards.push(el);
                }
            });
            // Deduplicate nested elements — keep smallest containing valid card
            cards = cards.filter(c => !cards.some(p => p !== c && p.contains(c)));
            cards = cards.slice(0, 200); // safety cap
        }

        const titleSels = [
            '[class*="title"]','[class*="Title"]',
            '[class*="name"]','[class*="Name"]',
            'h1','h2','h3','h4','strong',
        ];
        const priceSels = [
            '[class*="price"]','[class*="Price"]',
            '[class*="amount"]','[class*="Amount"]',
            '[class*="cost"]','[class*="Cost"]',
            'span[class*="rs"]','b',
        ];
        const descSels = [
            '[class*="desc"]','[class*="Desc"]',
            '[class*="detail"]','[class*="Detail"]',
            '[class*="info"]','[class*="subtitle"]',
            'p',
        ];

        cards.forEach(card => {
            const title   = getText(card, titleSels);
            const price   = getText(card, priceSels);
            const imgUrl  = getImg(card);
            const desc    = getText(card, descSels);
            if (title || price || imgUrl) {   // must have at least one field
                results.push({ title, price, image_url: imgUrl, description: desc });
            }
        });

        return results;
    }"""
    )

    # Post-process / clean
    seen_titles: set[str] = set()
    for item in raw_data:
        title = clean_text(item.get("title", ""))
        price = clean_price(clean_text(item.get("price", "")))
        image_url = (item.get("image_url") or "").strip()
        description = clean_text(item.get("description", ""))

        # Deduplicate by title
        key = title.lower()
        if key in seen_titles:
            continue
        if key:
            seen_titles.add(key)

        # Skip cards that look like UI chrome rather than products
        if not title and not price and not image_url:
            continue

        products.append(
            {
                "title": title,
                "price": price,
                "image_url": image_url,
                "description": description,
            }
        )

    log.info("Extracted %d products from current page view.", len(products))
    return products


# ──────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────
async def get_next_page_url(page: Page) -> Optional[str]:
    """
    Check for a 'Next' pagination button or link.
    Returns the href or None if on the last page.
    """
    next_selectors = [
        "a[aria-label*='next' i]",
        "a[class*='next' i]",
        "button[aria-label*='next' i]",
        "[class*='pagination'] a:last-child",
        "a:has-text('Next')",
        "a:has-text('›')",
        "a:has-text('»')",
    ]
    for sel in next_selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                href = await el.get_attribute("href")
                if href and href not in ("#", "javascript:void(0)", ""):
                    if href.startswith("http"):
                        return href
                    return f"https://www.markaz.app{href}"
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────
# Retry Wrapper
# ──────────────────────────────────────────────
async def fetch_page_with_retry(page: Page, url: str, retries: int = MAX_RETRIES) -> bool:
    """Navigate to *url* with exponential-backoff retries."""
    for attempt in range(1, retries + 1):
        try:
            log.info("Loading URL (attempt %d/%d): %s", attempt, retries, url)
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            # Extra wait for React hydration
            await asyncio.sleep(3)
            return True
        except PWTimeout:
            log.warning("Timeout on attempt %d for %s", attempt, url)
        except Exception as exc:
            log.error("Navigation error attempt %d: %s", attempt, exc)

        backoff = 2 ** attempt + random.uniform(0, 1)
        log.info("Retrying in %.1fs …", backoff)
        await asyncio.sleep(backoff)

    log.error("All %d attempts failed for %s", retries, url)
    return False


# ──────────────────────────────────────────────
# Main Scraper Orchestration
# ──────────────────────────────────────────────
async def scrape(max_pages: int = 5, output_file: str = "products.json") -> list[dict]:
    """
    Orchestrate the full scrape across up to *max_pages* pages.
    Returns the aggregated list of product dicts.
    """
    all_products: list[dict] = []

    async with async_playwright() as pw:
        browser = await new_browser(pw)
        page = await new_page(browser)

        current_url: Optional[str] = BASE_URL
        page_num = 0

        while current_url and page_num < max_pages:
            page_num += 1
            log.info("━━━ Page %d / %d ━━━", page_num, max_pages)

            success = await fetch_page_with_retry(page, current_url)
            if not success:
                log.error("Skipping page %d due to repeated failures.", page_num)
                break

            # Rate-limit
            await asyncio.sleep(random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX))

            products = await extract_products_from_page(page)
            all_products.extend(products)

            # Check for next page
            next_url = await get_next_page_url(page)
            if next_url and next_url != current_url:
                current_url = next_url
            else:
                log.info("No further pagination found — stopping after page %d.", page_num)
                break

        await browser.close()

    log.info("Total products scraped: %d", len(all_products))
    return all_products


# ──────────────────────────────────────────────
# Output Writers
# ──────────────────────────────────────────────
def save_json(products: list[dict], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    log.info("JSON saved → %s (%d records)", out, len(products))


def save_csv(products: list[dict], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["title", "price", "image_url", "description"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(products)
    log.info("CSV saved → %s (%d records)", out, len(products))


# ──────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Self-Help Learning Books from markaz.app"
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=5,
        help="Maximum number of pages to scrape (default: 5)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="products.json",
        help="Output JSON file path (default: products.json)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="products.csv",
        help="Output CSV file path (default: products.csv)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    log.info("Starting Markaz scraper — pages=%d, output=%s", args.pages, args.output)
    t0 = time.perf_counter()

    products = await scrape(max_pages=args.pages, output_file=args.output)

    if products:
        save_json(products, args.output)
        save_csv(products, args.csv)
    else:
        log.warning("No products found. Check selectors or site availability.")

    elapsed = time.perf_counter() - t0
    log.info("Done in %.1fs — %d products saved.", elapsed, len(products))


if __name__ == "__main__":
    asyncio.run(main())
