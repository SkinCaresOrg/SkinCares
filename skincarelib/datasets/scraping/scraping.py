from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# CONFIGURATION ~~~~~~~~~~~~~~~~~~~~~~~~~
DEFAULT_INPUT  = "../data/products_dataset_raw.csv"
DEFAULT_OUTPUT = "../data/prices_raw.csv"

MAX_WORKERS      = 12
REQUEST_TIMEOUT  = 12
CHECKPOINT_EVERY = 100

AMAZON_MIN_DELAY = 1.5
AMAZON_MAX_DELAY = 3.5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept-Language":           "en-US,en;q=0.9",
    "Accept-Encoding":           "gzip, deflate, br",
    "Connection":                "keep-alive",
    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control":             "max-age=0",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# UTILITIES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.4,
        status_forcelist={429, 500, 502, 503, 504},
        allowed_methods={"GET"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=MAX_WORKERS + 4,
        pool_maxsize=(MAX_WORKERS + 4) * 3,
    )
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    return session

_SESSION = _build_session()

@dataclass
class PriceResult:
    price:  Optional[float] = None
    source: Optional[str]   = None
    error:  Optional[str]   = None

    @property
    def found(self) -> bool:
        return self.price is not None


_PRICE_RE = re.compile(r"\$?\s*(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")


def _extract_price(text: str) -> Optional[float]:
    if not text:
        return None
    for m in _PRICE_RE.finditer(str(text)):
        try:
            val = float(m.group(1).replace(",", ""))
            if 0.50 <= val <= 2_000:
                return val
        except ValueError:
            continue
    return None


def _random_headers(extra: Optional[dict] = None) -> dict:
    h = {**BASE_HEADERS, "User-Agent": random.choice(USER_AGENTS)}
    if extra:
        h.update(extra)
    return h


def _fetch(url: str, extra_headers: Optional[dict] = None, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
    try:
        r = _SESSION.get(url, headers=_random_headers(extra_headers), timeout=timeout)
        if r.status_code == 200:
            return r.text
        log.debug("HTTP %s -> %s", r.status_code, url[:80])
    except requests.RequestException as exc:
        log.debug("fetch error: %s", exc)
    return None


def _build_queries(brand: str, product_name: str) -> list[str]:
    brand = brand.strip()
    name  = product_name.strip().split(",")[0].strip()
    if name.lower().startswith(brand.lower()):
        name = name[len(brand):].strip()

    words   = name.split()
    full    = f"{brand} {name}".strip()
    short   = f"{brand} {' '.join(words[:4])}".strip() if len(words) > 4 else full
    minimal = f"{brand} {words[0]}".strip() if words else brand

    seen, out = set(), []
    for q in (full, short, minimal):
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out

# SCRAPERS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 1
def _parse_amazon_price(soup: BeautifulSoup) -> Optional[float]:
    """
        Option 1: look for price split into whole and fraction parts (common on Amazon)
        Option 2: look for itemprop="price" tags
        Option 3: look for Product data in ld+json scripts
        Return first valid price found, or None if no price could be extracted.
    """
    # options 1
    whole = soup.select_one("span.a-price-whole")
    frac  = soup.select_one("span.a-price-fraction")
    if whole:
        fv = frac.text.strip().lstrip(".") if frac else "00"
        try:
            return float(f"{whole.text.replace(',', '').rstrip('.')}.{fv}")
        except ValueError:
            pass
    # option 2
    tag = soup.select_one("[itemprop='price']")
    if tag:
        p = _extract_price(tag.get("content") or tag.get_text())
        if p:
            return p
        
    # option 3
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data  = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Product":
                    p = _extract_price(str(item.get("offers", {}).get("price", "")))
                    if p:
                        return p
        except Exception:
            pass

    return None


def _amazon_is_bot_page(text: str, soup: BeautifulSoup) -> bool:
    """ making sure we are not blocked"""
    return bool(
        soup.select_one("form[action*='validateCaptcha']")
        or "robot check"                        in text
        or "enter the characters you see below" in text
        or "sorry, we just need to make sure"   in text
        or "automated access"                   in text
        or "captcha"                            in text
    )


def _scrape_amazon(query: str) -> PriceResult:
    """To avoid being blocked, it:
       - adds a random delay before requests
       - randomizes the User-Agent and sets realistic headers
       - uses a session with retries and connection pooling
       - checks responses for Amazon bot-detection pages

       Scraping logic:
        1. Try to fetch pricw from results page
        2. If not found, look for first product link and visit product page to extract price
        """

    time.sleep(random.uniform(AMAZON_MIN_DELAY, AMAZON_MAX_DELAY))

    #1 - search page
    html = _fetch(
        f"https://www.amazon.com/s?k={quote_plus(query)}&ref=nb_sb_noss",
        extra_headers={"Referer": "https://www.amazon.com/"},
    )
    if not html:
        return PriceResult(error="amazon_fetch_failed")

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text().lower()

    # bot check
    if _amazon_is_bot_page(text, soup):
        return PriceResult(error="amazon_bot_check")

    # 1.2 - try to get price from search results
    price = _parse_amazon_price(soup)
    if price:
        return PriceResult(price=price, source="amazon_search")

    # 2 - try to get price from product page
    anchor = soup.select_one("a.a-link-normal.s-no-outline[href]")
    if anchor and anchor.get("href"):
        time.sleep(random.uniform(0.5, 1.2))
        product_html = _fetch(
            "https://www.amazon.com" + anchor["href"].split("?")[0],
            extra_headers={"Referer": "https://www.amazon.com/s"},
        )
        if product_html:
            psoup = BeautifulSoup(product_html, "html.parser")
            if not _amazon_is_bot_page(product_html.lower(), psoup):
                price = _parse_amazon_price(psoup)
                if price:
                    return PriceResult(price=price, source="amazon_product")

    return PriceResult(error="amazon_not_found")


#2
def _scrape_walmart(query: str) -> PriceResult:
    """
    scrpaing logic:
    1. Try to extract price from search results page 
    2. If not found, look for price data in ld+json scripts 
    3. recursively walk through all JSON objects in the script to find any price-related fields to return
    4. If not found, look for price tags in the HTML as a last resort
    """
    # 1 
    html = _fetch(
        f"https://www.walmart.com/search?q={quote_plus(query)}&sort=best_match",
        extra_headers={"Accept": "text/html", "Referer": "https://www.walmart.com/"},
    )
    if not html:
        return PriceResult(error="walmart_fetch_failed")

    soup = BeautifulSoup(html, "html.parser")

    # 2 
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if script and script.string:
        try:
            # 3
            def _walk(obj: object, depth: int = 0) -> Optional[float]:
                if depth > 14 or not isinstance(obj, (dict, list)):
                    return None
                if isinstance(obj, list):
                    for item in obj[:20]:
                        p = _walk(item, depth + 1)
                        if p:
                            return p
                else:
                    for k in ("price", "currentPrice", "priceInfo", "salePrice",
                              "minPrice", "displayPrice"):
                        v = obj.get(k)
                        if isinstance(v, (int, float)):
                            p = _extract_price(str(v))
                            if p:
                                return p
                        elif isinstance(v, str):
                            p = _extract_price(v)
                            if p:
                                return p
                        elif isinstance(v, dict):
                            p = _walk(v, depth + 1)
                            if p:
                                return p
                    for v in obj.values():
                        if isinstance(v, (dict, list)):
                            p = _walk(v, depth + 1)
                            if p:
                                return p
                return None
            price = _walk(json.loads(script.string))
            if price:
                return PriceResult(price=price, source="walmart")
        except Exception as exc:
            log.debug("Walmart JSON: %s", exc)

    # 4 (plan z)
    for sel in (
        "[itemprop='price']",
        "span[class*='price-characteristic']",
        "span[class*='Price']",
        "div[class*='price']",
    ):
        tag = soup.select_one(sel)
        if tag:
            p = _extract_price(tag.get("content") or tag.get_text())
            if p:
                return PriceResult(price=p, source="walmart")

    return PriceResult(error="walmart_not_found")

#PRICE LOOKUP
def get_best_price(brand: str, product_name: str) -> PriceResult:
    """
    For each query:
        1. Try to scrape Amazon for the product price. If found, return immediately.
        2. If not found on Amazon, try to scrape Walmart for the product price. If found, return immediately.
        3. return not found if neither source had a price for any of the queries.
    """
    for query in _build_queries(brand, product_name):
        result = _scrape_amazon(query)
        if result.found:
            return result

        result = _scrape_walmart(query)
        if result.found:
            return result

    return PriceResult(error="not_found_anywhere")


def _process_row(args: tuple) -> tuple[int, PriceResult]:
    idx, brand, product_name = args
    return idx, get_best_price(brand, product_name)


#CHECKPOINT
def _checkpoint_path(output_path: str) -> Path:
    return Path(output_path).with_suffix(".checkpoint.csv")


def _load_checkpoint(output_path: str) -> dict[int, PriceResult]:
    """IMPORTANT for interruptions
    If a checkpoint file exists, it loads the already scraped prices into a dict and returns it
    """
    cp = _checkpoint_path(output_path)
    if not cp.exists():
        return {}
    try:
        done = pd.read_csv(cp)
        if not {"_idx", "price_source"}.issubset(done.columns):
            log.warning("Checkpoint missing columns -- starting fresh")
            return {}
        out: dict[int, PriceResult] = {}
        for _, row in done.iterrows():
            price  = float(row["price"])      if pd.notna(row.get("price"))        else None
            source = str(row["price_source"]) if pd.notna(row.get("price_source")) else None
            out[int(row["_idx"])] = PriceResult(price=price, source=source)
        log.info("Resumed: %d rows already done from checkpoint", len(out))
        return out
    except Exception as exc:
        log.warning("Could not read checkpoint (%s) -- starting fresh", exc)
        return {}


def _save_checkpoint(
    output_path: str,
    results: dict[int, PriceResult],
    df: pd.DataFrame,
) -> None:
    rows = [
        {
            "_idx":         idx,
            "brand":        df.at[idx, "brand"],
            "product_name": df.at[idx, "product_name"],
            "price":        r.price,
            "price_source": r.source,
        }
        for idx, r in results.items()
    ]
    pd.DataFrame(rows).to_csv(_checkpoint_path(output_path), index=False)


# ----------------------------------------------
def load_dataset(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = {"brand", "product_name"} - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV missing columns: {missing}")
    return df


def run(input_path: str, output_path: str, workers: int = MAX_WORKERS) -> pd.DataFrame:
    """ 
    Main entry point for the scraping process. It:
        1. Loads the input dataset
        2. Resumes from checkpoint if available
        3. Scrapes prices in parallel with multiple workers
        4. Periodically saves checkpoints
        5. Saves final output CSV and cleans up last checkpoint
    """

    df    = load_dataset(input_path)
    total = len(df)
    log.info("Loaded %d products from %s", total, input_path)

    results: dict[int, PriceResult] = _load_checkpoint(output_path)
    pending = [
        (i, row["brand"], row["product_name"])
        for i, row in df.iterrows()
        if i not in results
    ]
    log.info(
        "Scraping %d products | %d workers | Amazon -> Walmart",
        len(pending), workers,
    )

    done_count       = len(results)
    since_checkpoint = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_row, task): task for task in pending}

        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result
            done_count  += 1
            since_checkpoint += 1

            status = f"${result.price:.2f} via {result.source}" if result.found else f"x {result.error}"
            brand  = df.at[idx, "brand"]
            name   = df.at[idx, "product_name"].split(",")[0]
            log.info("[%d/%d] %-46s -> %s", done_count, total, f"{brand} {name}"[:46], status)

            if since_checkpoint >= CHECKPOINT_EVERY:
                _save_checkpoint(output_path, results, df)
                log.info("  checkpoint saved (%d/%d)", done_count, total)
                since_checkpoint = 0

    # final save and cleanup
    if since_checkpoint:
        _save_checkpoint(output_path, results, df)

    # format output dataframe
    output_df = pd.DataFrame({
        "brand":        df["brand"].values,
        "product_name": df["product_name"].values,
        "price":        [results[i].price  for i in df.index],
        "price_source": [results[i].source for i in df.index],
    })

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(out, index=False)

    cp = _checkpoint_path(output_path)
    if cp.exists():
        cp.unlink()

    found = output_df["price"].notna().sum()
    log.info(
        "Done. %d/%d prices found (%.1f%%) -> %s",
        found, total, 100 * found / total, out,
    )
    return output_df

# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Beauty product price scraper -- Amazon + Walmart",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input",   default=DEFAULT_INPUT)
    parser.add_argument("--output",  default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS,
                        help="Number of parallel worker threads")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(args.input, args.output, args.workers)