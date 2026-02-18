"""
Web search integration - Tavily API (search + extract).
"""

import os
from typing import List, Optional, Union

from core.logger import get_logger

logger = get_logger("web_search")


def _get_tavily_client():
    """Get Tavily client. Returns None if API key missing."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set")
        return None
    try:
        from tavily import TavilyClient
        return TavilyClient(api_key=api_key)
    except ImportError:
        logger.warning("tavily package not installed. pip install tavily-python")
        return None


def tavily_extract(
    urls: Union[str, List[str]],
    extract_depth: str = "advanced",
    format: str = "markdown",
) -> List[dict]:
    """
    Extract content from URLs using Tavily Extract API.
    Returns list of dicts with keys: url, raw_content.
    """
    client = _get_tavily_client()
    if not client:
        return []

    try:
        url_list = [urls] if isinstance(urls, str) else urls
        response = client.extract(
            url_list,
            extract_depth=extract_depth,
            format=format,
        )
        results = response.get("results", [])
        failed = response.get("failed_results", [])
        if failed:
            for f in failed:
                logger.warning("Tavily extract failed for %s: %s", f.get("url"), f.get("error"))
        return results
    except Exception as e:
        logger.exception("Tavily extract failed: %s", e)
        return []


def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[List[str]] = None,
) -> List[dict]:
    """
    Search the web using Tavily API.

    Returns list of dicts with keys: title, url, content, score.
    """
    client = _get_tavily_client()
    if not client:
        return []

    try:
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_domains=include_domains or [
                "richbourse.com",
                "dabafinance.com",
                "brvm.org",
                "reuters.com",
                "investing.com",
            ],
        )
        return response.get("results", [])
    except Exception as e:
        logger.exception("Tavily search failed: %s", e)
        return []


def search_financial_news(ticker: str, company_name: str = "") -> List[dict]:
    """Search for financial news about a stock."""
    query = f"{ticker} {company_name} BRVM stock news".strip()
    return tavily_search(query, max_results=8, search_depth="basic")


def search_stock_info(ticker: str) -> List[dict]:
    """Search for general stock/company info."""
    query = f"{ticker} BRVM West Africa stock"
    return tavily_search(query, max_results=5)
