"""
Stock analysis and financial metrics for West African markets (BRVM).

Computes:
- Daily / monthly returns
- Volatility
- Moving averages
- Basic valuation (P/E, growth, revenue trend when available)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from core.logger import get_logger

logger = get_logger("analyzer")


@dataclass
class AnalysisResult:
    """Stock analysis output."""

    ticker: str
    current_price: Decimal
    currency: str
    daily_return_pct: Optional[float] = None
    monthly_return_pct: Optional[float] = None
    volatility_annualized: Optional[float] = None
    ma_20: Optional[Decimal] = None
    ma_50: Optional[Decimal] = None
    pe_ratio: Optional[float] = None
    growth_trend: Optional[str] = None
    summary: str = ""
    computed_at: datetime = field(default_factory=datetime.utcnow)


def compute_daily_return(prices: List[Decimal]) -> Optional[float]:
    """Compute last daily return (today vs yesterday)."""
    if len(prices) < 2:
        return None
    prev, curr = float(prices[-2]), float(prices[-1])
    if prev == 0:
        return None
    return ((curr - prev) / prev) * 100


def compute_monthly_return(prices: List[Decimal], dates: Optional[List[datetime]] = None) -> Optional[float]:
    """Compute approx monthly return (last 30d vs 30d before)."""
    if len(prices) < 2:
        return None
    # Simple: last vs first of available data as proxy for 1 month
    n = len(prices)
    if n < 2:
        return None
    # Use last 20 vs previous 20 as monthly proxy if we have enough data
    mid = max(1, n // 2)
    old_avg = sum(float(p) for p in prices[:mid]) / mid
    new_avg = sum(float(p) for p in prices[mid:]) / (n - mid)
    if old_avg == 0:
        return None
    return ((new_avg - old_avg) / old_avg) * 100


def compute_volatility(returns: List[float]) -> Optional[float]:
    """Annualized volatility from daily returns (approx * sqrt(252))."""
    if not returns:
        return None
    n = len(returns)
    mean_ret = sum(returns) / n
    var = sum((r - mean_ret) ** 2 for r in returns) / max(1, n - 1)
    import math

    return math.sqrt(var) * (252 ** 0.5) * 100 if var >= 0 else None


def compute_moving_average(prices: List[Decimal], window: int) -> Optional[Decimal]:
    """Simple moving average."""
    if len(prices) < window:
        return None
    window_prices = prices[-window:]
    return sum(window_prices) / len(window_prices)


def compute_returns_from_prices(prices: List[Decimal]) -> List[float]:
    """Convert price series to daily returns (%)."""
    returns = []
    for i in range(1, len(prices)):
        prev, curr = float(prices[i - 1]), float(prices[i])
        if prev != 0:
            returns.append(((curr - prev) / prev) * 100)
    return returns


def analyze_stock(
    ticker: str,
    current_price: Decimal,
    historical_prices: Optional[List[tuple[datetime, Decimal]]] = None,
    pe_ratio: Optional[float] = None,
) -> AnalysisResult:
    """
    Perform full stock analysis.

    historical_prices: list of (date, price) tuples, sorted by date.
    """
    prices = [p for _, p in (historical_prices or [])]
    if (current_price or Decimal(0)) > 0:
        prices = prices + [current_price]

    daily_ret = None
    monthly_ret = None
    vol = None
    ma20 = None
    ma50 = None

    if prices:
        daily_ret = compute_daily_return(prices)
        monthly_ret = compute_monthly_return(prices)
        returns = compute_returns_from_prices(prices)
        vol = compute_volatility(returns)
        ma20 = compute_moving_average(prices, 20)
        ma50 = compute_moving_average(prices, 50)

    # Trend from MA
    growth_trend = None
    if ma20 and ma50 and current_price:
        if float(current_price) > float(ma20) > float(ma50):
            growth_trend = "bullish"
        elif float(current_price) < float(ma20) < float(ma50):
            growth_trend = "bearish"
        else:
            growth_trend = "neutral"

    summary = _build_summary(
        ticker=ticker,
        current_price=current_price,
        daily_ret=daily_ret,
        monthly_ret=monthly_ret,
        vol=vol,
        ma20=ma20,
        ma50=ma50,
        pe=pe_ratio,
        trend=growth_trend,
    )

    return AnalysisResult(
        ticker=ticker,
        current_price=current_price,
        currency="XOF",
        daily_return_pct=daily_ret,
        monthly_return_pct=monthly_ret,
        volatility_annualized=vol,
        ma_20=ma20,
        ma_50=ma50,
        pe_ratio=pe_ratio,
        growth_trend=growth_trend,
        summary=summary,
    )


def _build_summary(
    ticker: str,
    current_price: Decimal,
    daily_ret: Optional[float],
    monthly_ret: Optional[float],
    vol: Optional[float],
    ma20: Optional[Decimal],
    ma50: Optional[Decimal],
    pe: Optional[float],
    trend: Optional[str],
) -> str:
    """Build human-readable summary."""
    parts = [f"{ticker}: {current_price} XOF"]
    if daily_ret is not None:
        parts.append(f"1d: {daily_ret:+.2f}%")
    if monthly_ret is not None:
        parts.append(f"1m: {monthly_ret:+.2f}%")
    if vol is not None:
        parts.append(f"Vol: {vol:.1f}%")
    if ma20 is not None:
        parts.append(f"MA20: {ma20:.0f}")
    if ma50 is not None:
        parts.append(f"MA50: {ma50:.0f}")
    if pe is not None:
        parts.append(f"P/E: {pe:.1f}")
    if trend:
        parts.append(f"Trend: {trend}")
    return " | ".join(parts)


def detect_signal(
    current_price: Decimal,
    ma20: Optional[Decimal],
    ma50: Optional[Decimal],
) -> Optional[str]:
    """
    Simple buy/sell signal from moving average crossovers.

    Returns: "BUY" | "SELL" | None
    """
    if not ma20 or not ma50 or not current_price:
        return None
    cp = float(current_price)
    m20 = float(ma20)
    m50 = float(ma50)
    if m20 > m50 and cp > m20:
        return "BUY"
    if m20 < m50 and cp < m20:
        return "SELL"
    return None
