"""
Agent tools - unified interface for web search, scraping, and analysis.

Used by the AI agent to perform financial intelligence tasks.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from core.analyzer import analyze_stock, detect_signal
from core.logger import get_logger
from integrations.scrapers import (
    scrape_brvm_prices,
    scrape_brvm_prices_async,
    scrape_stock_price,
    scrape_stock_price_async,
    scrape_company_news,
    scrape_company_news_async,
)
from integrations.web_search import search_financial_news, search_stock_info, tavily_search

logger = get_logger("tools")


class AgentTools:
    """Toolkit for the Financial Agent."""

    @staticmethod
    def web_search(query: str, max_results: int = 5) -> List[dict]:
        """Search the web for information."""
        return tavily_search(query, max_results=max_results)

    @staticmethod
    def get_current_stock_price(ticker: str) -> Optional[Dict[str, Any]]:
        """Get current price for a BRVM stock (sync)."""
        quote = scrape_stock_price(ticker)
        if not quote:
            return None
        return {
            "ticker": quote.ticker,
            "name": quote.name,
            "price": float(quote.price),
            "currency": quote.currency,
            "change_pct": quote.change_pct,
            "source": quote.source,
        }

    @staticmethod
    async def get_current_stock_price_async(ticker: str) -> Optional[Dict[str, Any]]:
        """Get current price for a BRVM stock (async, for use inside asyncio)."""
        quote = await scrape_stock_price_async(ticker)
        if not quote:
            return None
        return {
            "ticker": quote.ticker,
            "name": quote.name,
            "price": float(quote.price),
            "currency": quote.currency,
            "change_pct": quote.change_pct,
            "source": quote.source,
        }

    @staticmethod
    def get_all_brvm_prices() -> List[Dict[str, Any]]:
        """Get all BRVM stock prices."""
        quotes = scrape_brvm_prices()
        return [
            {
                "ticker": q.ticker,
                "name": q.name,
                "price": float(q.price),
                "currency": q.currency,
                "change_pct": q.change_pct,
            }
            for q in quotes
        ]

    @staticmethod
    def get_stock_news(ticker: str) -> List[Dict[str, Any]]:
        """Get news for a stock."""
        search_results = search_financial_news(ticker)
        scraped = scrape_company_news(ticker)
        combined: Dict[str, dict] = {}
        for r in search_results:
            title = r.get("title", "")
            if title and title not in combined:
                combined[title] = {"title": title, "url": r.get("url"), "content": r.get("content", "")[:300]}
        for n in scraped:
            if n.title not in combined:
                combined[n.title] = {"title": n.title, "url": n.url, "content": (n.summary or "")[:300]}
        return list(combined.values())

    @staticmethod
    def analyze_stock(
        ticker: str,
        current_price: Optional[Decimal] = None,
        historical_prices: Optional[List[tuple]] = None,
        use_db_cache: bool = True,
    ) -> Dict[str, Any]:
        """Analyze a stock with financial metrics. Uses DB cache for historical if available."""
        if current_price is None:
            quote = scrape_stock_price(ticker)
            if not quote:
                return {"error": f"No price data for {ticker}"}
            current_price = quote.price

        if historical_prices is None and use_db_cache:
            try:
                from database.connection import SessionLocal
                from database import crud
                db = SessionLocal()
                try:
                    prices = crud.get_stock_prices(db, ticker, days=90)
                    historical_prices = [(p.price_date, p.price) for p in prices] if prices else None
                finally:
                    db.close()
            except Exception:
                historical_prices = None

        result = analyze_stock(
            ticker=ticker,
            current_price=current_price,
            historical_prices=historical_prices,
        )

        signal = detect_signal(result.current_price, result.ma_20, result.ma_50)

        return {
            "ticker": result.ticker,
            "current_price": float(result.current_price),
            "currency": result.currency,
            "daily_return_pct": result.daily_return_pct,
            "monthly_return_pct": result.monthly_return_pct,
            "volatility_annualized": result.volatility_annualized,
            "ma_20": float(result.ma_20) if result.ma_20 else None,
            "ma_50": float(result.ma_50) if result.ma_50 else None,
            "pe_ratio": result.pe_ratio,
            "growth_trend": result.growth_trend,
            "signal": signal,
            "summary": result.summary,
        }

    @staticmethod
    async def analyze_stock_async(
        ticker: str,
        current_price: Optional[Decimal] = None,
        historical_prices: Optional[List[tuple]] = None,
        use_db_cache: bool = True,
    ) -> Dict[str, Any]:
        """Analyze a stock (async, for use inside asyncio)."""
        if current_price is None:
            quote = await scrape_stock_price_async(ticker)
            if not quote:
                return {"error": f"No price data for {ticker}"}
            current_price = quote.price

        if historical_prices is None and use_db_cache:
            try:
                from database.connection import SessionLocal
                from database import crud
                db = SessionLocal()
                try:
                    prices = crud.get_stock_prices(db, ticker, days=90)
                    historical_prices = [(p.price_date, p.price) for p in prices] if prices else None
                finally:
                    db.close()
            except Exception:
                historical_prices = None

        result = analyze_stock(
            ticker=ticker,
            current_price=current_price,
            historical_prices=historical_prices,
        )
        signal = detect_signal(result.current_price, result.ma_20, result.ma_50)
        return {
            "ticker": result.ticker,
            "current_price": float(result.current_price),
            "currency": result.currency,
            "daily_return_pct": result.daily_return_pct,
            "monthly_return_pct": result.monthly_return_pct,
            "volatility_annualized": result.volatility_annualized,
            "ma_20": float(result.ma_20) if result.ma_20 else None,
            "ma_50": float(result.ma_50) if result.ma_50 else None,
            "pe_ratio": result.pe_ratio,
            "growth_trend": result.growth_trend,
            "signal": signal,
            "summary": result.summary,
        }
