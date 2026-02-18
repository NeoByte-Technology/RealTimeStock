"""
Web scrapers for BRVM and West African financial data.

Uses Tavily API (Extract + Search) instead of Playwright.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from core.logger import get_logger
from core.config import settings
from integrations.web_search import tavily_extract, tavily_search

logger = get_logger("scrapers")


@dataclass
class StockQuote:
    """Normalized stock quote."""

    ticker: str
    name: str
    price: Decimal
    currency: str
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[Decimal] = None
    source: str = ""
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CompanyNewsItem:
    """Normalized company news item."""

    title: str
    summary: Optional[str] = None
    url: Optional[str] = None
    source: str = ""
    published_at: Optional[datetime] = None
    ticker: Optional[str] = None


def _safe_decimal(s: str) -> Optional[Decimal]:
    """Parse string to Decimal. Handles '1 650', '20,100', 'CFA 27,995'."""
    if not s or not s.strip():
        return None
    s = s.strip()
    # Remove "CFA" prefix
    s = re.sub(r"CFA\s*", "", s, flags=re.I)
    # Remove spaces (thousand sep) and commas (thousand sep)
    s = s.replace(" ", "").replace(",", "")
    # If dot used as decimal, keep; if no dot, we're good
    if not re.search(r"\d", s):
        return None
    if s.count(".") > 1:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def _parse_brvm_from_content(raw_content: str) -> List[StockQuote]:
    """
    Parse BRVM stock data from extracted content (markdown or text).
    Handles markdown tables and line-based patterns like "SNTS ... 5000".
    """
    results: List[StockQuote] = []
    seen_tickers: set[str] = set()

    # Pattern: ticker (2-6 upper) then optional name then price (number with optional , or .)
    # e.g. "SNTS  Sonatel  5 000" or "| SNTS | Sonatel | 5000 |"
    ticker_price_re = re.compile(
        r'\b([A-Z]{2,6})\b[\s|]*'  # ticker
        r'(?:[^\d|]*?[\s|]+)?'     # optional name
        r'([\d\s.,]+)'             # price
        r'(?:[\s|%+-]*([-\d.,]+)\s*%?)?',  # optional change pct
        re.IGNORECASE
    )

    lines = raw_content.replace('\r\n', '\n').split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # Try markdown table rows
        # Richbourse: | ticker | name | variation% | vol | val | cours_actuel | ... |
        # Daba: | ticker mcap | CFA price | today% |
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                ticker_raw = parts[0]
                ticker_match = re.match(r'^([A-Z]{2,6})\b', ticker_raw, re.I) or re.search(r'\b([A-Z]{2,6})\b', ticker_raw, re.I)
                ticker = ticker_match.group(1).upper() if ticker_match else ticker_raw[:6].upper()
                if not (2 <= len(ticker) <= 6 and ticker.isalpha()) or ticker in seen_tickers:
                    continue

                name = parts[1] if len(parts) > 1 else ticker
                price = None
                change_pct = None
                if len(parts) >= 6:
                    price = _safe_decimal(parts[5])
                    if len(parts) > 2 and '%' in parts[2]:
                        cp = re.search(r'([-\d.]+)', parts[2])
                        if cp:
                            try:
                                change_pct = float(cp.group(1).replace(',', '.'))
                            except ValueError:
                                pass
                else:
                    price = _safe_decimal(parts[1] if len(parts) > 1 else parts[0])

                if price and price > 0:
                    results.append(StockQuote(
                        ticker=ticker,
                        name=name[:80] if name else ticker,
                        price=price,
                        currency="XOF",
                        change_pct=change_pct,
                        source="brvm",
                    ))
                    seen_tickers.add(ticker)
            continue

        # Try regex for inline patterns
        for m in ticker_price_re.finditer(line):
            ticker = m.group(1).upper()
            if ticker in seen_tickers or len(ticker) < 2:
                continue
            try:
                price_str = m.group(2)
                price_match = re.search(r'[\d.]+', price_str)
                if not price_match:
                    continue
                price = _safe_decimal(price_match.group())
                if price and price > 0 and price < 10000000:  # sanity
                    change_pct = None
                    if m.lastindex >= 3 and m.group(3):
                        try:
                            change_pct = float(m.group(3).replace(',', '.'))
                        except (ValueError, TypeError):
                            pass
                    results.append(StockQuote(
                        ticker=ticker,
                        name=ticker,
                        price=price,
                        currency="XOF",
                        change_pct=change_pct,
                        source="brvm",
                    ))
                    seen_tickers.add(ticker)
                    break
            except (ValueError, AttributeError, TypeError):
                pass

    return results


def _fetch_brvm_content() -> str:
    """Fetch BRVM stock data from Richbourse and Daba Finance via Tavily Extract."""
    urls = list(settings.BRVM_STOCKS_URLS)
    if not urls:
        return ""
    results = tavily_extract(
        urls,
        extract_depth="advanced",
        format="markdown",
    )
    # Merge content from all sources
    parts = []
    for r in results:
        raw = r.get("raw_content", "")
        if raw:
            parts.append(raw)
    return "\n\n".join(parts) if parts else ""


def scrape_brvm_prices() -> List[StockQuote]:
    """Scrape current BRVM stock prices via Tavily Extract (sync)."""
    try:
        content = _fetch_brvm_content()
        if not content:
            # Fallback: search for BRVM prices and parse from results
            search_results = tavily_search(
                "BRVM cours actions bourse",
                max_results=5,
                search_depth="advanced",
                include_domains=["richbourse.com", "dabafinance.com", "brvm.org"],
            )
            content = " ".join(r.get("content", "") for r in search_results)
            if not content:
                logger.warning("No BRVM content from Tavily")
                return []

        quotes = _parse_brvm_from_content(content)
        logger.info("Parsed %d BRVM quotes from Tavily", len(quotes))
        return quotes
    except Exception as e:
        logger.exception("BRVM fetch failed: %s", e)
        return []


async def scrape_brvm_prices_async() -> List[StockQuote]:
    """Scrape current BRVM stock prices (async - runs Tavily in thread)."""
    return await asyncio.to_thread(scrape_brvm_prices)


def scrape_stock_price(ticker: str) -> Optional[StockQuote]:
    """Get price for a single ticker (sync)."""
    quotes = scrape_brvm_prices()
    ticker_upper = ticker.upper()
    for q in quotes:
        if q.ticker.upper() == ticker_upper:
            return q

    # Fallback: search for specific ticker
    search_results = tavily_search(
        f"{ticker} BRVM prix cours",
        max_results=3,
        search_depth="advanced",
        include_domains=["richbourse.com", "dabafinance.com", "brvm.org"],
    )
    for r in search_results:
        content = r.get("content", "")
        quotes = _parse_brvm_from_content(content)
        for q in quotes:
            if q.ticker.upper() == ticker_upper:
                return q
    return None


async def scrape_stock_price_async(ticker: str) -> Optional[StockQuote]:
    """Get price for a single ticker (async)."""
    return await asyncio.to_thread(scrape_stock_price, ticker)


def scrape_company_news(ticker: str, sources: Optional[List[str]] = None) -> List[CompanyNewsItem]:
    """Scrape news for a company via Tavily Search (sync)."""
    results = tavily_search(
        f"{ticker} BRVM actualités news",
        max_results=10,
        search_depth="basic",
        include_domains=["richbourse.com", "dabafinance.com", "brvm.org", "reuters.com"],
    )
    items: List[CompanyNewsItem] = []
    for r in results:
        title = r.get("title", "")
        if not title or len(title) < 5:
            continue
        items.append(CompanyNewsItem(
            title=title,
            summary=r.get("content", "")[:500] if r.get("content") else None,
            url=r.get("url"),
            source=r.get("url", ""),
            ticker=ticker,
        ))
    return items


async def scrape_company_news_async(ticker: str, sources: Optional[List[str]] = None) -> List[CompanyNewsItem]:
    """Scrape news for a company (async)."""
    return await asyncio.to_thread(scrape_company_news, ticker, sources)


def normalize_ticker(ticker: str) -> str:
    """Normalize ticker symbol for BRVM."""
    return ticker.upper().strip()
