"""
AI Agent for West Africa Financial Intelligence.

Uses LLM to summarize, interpret metrics, and provide natural language analysis.
"""

import json
from typing import Any, Dict, List, Optional

from core.analyzer import AnalysisResult, analyze_stock
from core.logger import get_logger
from core.tools import AgentTools
from integrations.scrapers import scrape_stock_price
from integrations.web_search import tavily_search

logger = get_logger("agent")


SYSTEM_PROMPT = """You are the West Africa Financial Intelligence Agent, an expert in BRVM (Bourse Régionale des Valeurs Mobilières) and West African stock markets.

Your role:
- Analyze stocks listed on BRVM (Senegal, Côte d'Ivoire, Burkina Faso, etc.)
- Interpret financial metrics: P/E, volatility, moving averages, returns
- Provide risk analysis and investment insights
- Summarize company performance in clear, actionable language
- Explain portfolio performance in natural language

Guidelines:
- Be concise but thorough
- Use XOF (West African CFA Franc) as the default currency
- When data is unavailable, say so clearly
- Focus on practical insights for West African investors
- Avoid excessive jargon; explain technical terms when needed
"""


def get_llm_client():
    """Get configured LLM client (Ollama, OpenAI, or Anthropic)."""
    from core.config import settings

    if settings.LLM_PROVIDER == "ollama":
        return "ollama"
    if settings.LLM_PROVIDER == "anthropic":
        try:
            from anthropic import Anthropic
            return Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except ImportError:
            logger.warning("anthropic package not installed")
            return None
    if settings.LLM_PROVIDER == "openai":
        try:
            from openai import OpenAI
            return OpenAI(api_key=settings.OPENAI_API_KEY)
        except ImportError:
            logger.warning("openai package not installed")
            return None
    return None


def call_llm(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
) -> Optional[str]:
    """Call LLM and return response text."""
    from core.config import settings

    client = get_llm_client()
    if not client:
        return None

    model = model or settings.LLM_MODEL

    try:
        if settings.LLM_PROVIDER == "ollama":
            from ollama import Client
            client = Client(host=settings.OLLAMA_HOST)
            ollama_msgs = [{"role": m.get("role", "user"), "content": m["content"]} for m in messages]
            response = client.chat(
                model=model,
                messages=ollama_msgs,
                options={"num_predict": 1024},
            )
            return response.message.content if response.message else None

        if settings.LLM_PROVIDER == "anthropic":
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            )
            return response.content[0].text if response.content else None

        # OpenAI
        response = client.chat.completions.create(model=model, messages=messages, max_tokens=1024)
        return response.choices[0].message.content if response.choices else None
    except Exception as e:
        logger.exception("LLM call failed: %s", e)
        return None


class FinancialAgent:
    """AI-powered financial analysis agent."""

    def __init__(self):
        self.tools = AgentTools()

    def summarize_stock_analysis(self, analysis_data: Dict[str, Any]) -> str:
        """Use LLM to summarize stock analysis."""
        prompt = f"""Summarize this BRVM stock analysis for an investor. Be concise (2-4 sentences). Focus on key metrics and any buy/sell signal.

Analysis data:
{json.dumps(analysis_data, indent=2)}
"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages)
        return result or _fallback_summary(analysis_data)

    def interpret_metrics(self, ticker: str, metrics: Dict[str, Any]) -> str:
        """Interpret financial metrics in natural language."""
        prompt = f"""Interpret these financial metrics for {ticker} (BRVM). Explain what they mean for an investor in 2-3 sentences.

Metrics:
{json.dumps(metrics, indent=2)}
"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages)
        return result or "Unable to interpret metrics. Review the raw data above."

    def risk_analysis(self, ticker: str, analysis_data: Dict[str, Any]) -> str:
        """Provide risk analysis."""
        prompt = f"""Provide a brief risk analysis for {ticker} (BRVM stock) based on this data. Consider volatility, trend, and market context. 2-3 sentences.

Data:
{json.dumps(analysis_data, indent=2)}
"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages)
        return result or "Risk assessment requires more data. Monitor volatility and market conditions."

    def explain_portfolio(self, portfolio_summary: Dict[str, Any]) -> str:
        """Explain portfolio performance in natural language."""
        prompt = f"""Explain this portfolio performance to the investor in 2-4 sentences. Be encouraging but realistic.

Portfolio:
{json.dumps(portfolio_summary, indent=2)}
"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        result = call_llm(messages)
        return result or _fallback_portfolio_summary(portfolio_summary)

    def analyze_with_ai(self, ticker: str) -> Dict[str, Any]:
        """Full analysis: fetch data, compute metrics, LLM summary (sync)."""
        analysis = self.tools.analyze_stock(ticker)
        if "error" in analysis:
            return analysis

        summary = self.summarize_stock_analysis(analysis)
        risk = self.risk_analysis(ticker, analysis)
        analysis["ai_summary"] = summary
        analysis["ai_risk_analysis"] = risk
        return analysis

    async def analyze_with_ai_async(self, ticker: str) -> Dict[str, Any]:
        """Full analysis (async, for use inside asyncio e.g. Telegram)."""
        analysis = await self.tools.analyze_stock_async(ticker)
        if "error" in analysis:
            return analysis

        summary = self.summarize_stock_analysis(analysis)
        risk = self.risk_analysis(ticker, analysis)
        analysis["ai_summary"] = summary
        analysis["ai_risk_analysis"] = risk
        return analysis


def _fallback_summary(data: Dict[str, Any]) -> str:
    """Fallback when LLM unavailable."""
    parts = [f"{data.get('ticker', '')}: {data.get('current_price', 0)} XOF"]
    if data.get("daily_return_pct") is not None:
        parts.append(f"1d {data['daily_return_pct']:+.1f}%")
    if data.get("signal"):
        parts.append(f"Signal: {data['signal']}")
    return ". ".join(parts)


def _fallback_portfolio_summary(data: Dict[str, Any]) -> str:
    """Fallback portfolio summary."""
    total_return = data.get("total_return_pct", 0)
    return f"Portfolio return: {total_return:+.1f}%. Review positions for details."
