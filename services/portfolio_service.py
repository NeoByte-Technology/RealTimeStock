"""
Portfolio management service.

Computes positions, performance, gain/loss, and watchlist.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from core.analyzer import detect_signal
from core.logger import get_logger
from database import crud
from database.models import Transaction
from integrations.scrapers import scrape_stock_price, scrape_stock_price_async

logger = get_logger("portfolio_service")


@dataclass
class Position:
    """Portfolio position for a ticker."""

    user_id: int
    ticker: str
    stock_name: str
    total_quantity: Decimal
    average_buy_price: Decimal
    total_cost: Decimal
    current_price: Optional[Decimal]
    market_value: Optional[Decimal]
    realized_profit: Decimal
    unrealized_profit: Optional[Decimal]
    unrealized_profit_pct: Optional[float]


@dataclass
class PortfolioSummary:
    """Portfolio summary."""

    user_id: int
    total_cost: Decimal
    total_market_value: Decimal
    total_realized_profit: Decimal
    total_unrealized_profit: Decimal
    total_return_pct: float
    positions: List[Position]


def get_current_price(ticker: str, price_fetcher: Optional[Callable[[str], Optional[Decimal]]] = None) -> Optional[Decimal]:
    """Get current price for ticker. Uses scraper by default."""
    if price_fetcher:
        quote = price_fetcher(ticker)
        return Decimal(str(quote.price)) if quote else None
    quote = scrape_stock_price(ticker)
    return Decimal(str(quote.price)) if quote else None


def compute_positions(db: Session, user_id: int) -> List[dict]:
    """
    Compute portfolio positions from transactions.

    FIFO not required for MVP; we use average cost.
    """
    trans = crud.get_user_transactions(db, user_id)
    by_ticker: dict[str, dict] = {}

    for t in trans:
        ticker = t.ticker
        qty = Decimal(str(t.quantity))
        price = Decimal(str(t.price))
        fees = Decimal(str(t.fees or 0))
        cost = qty * price + fees

        if ticker not in by_ticker:
            by_ticker[ticker] = {
                "ticker": ticker,
                "stock_name": t.stock_name,
                "quantity": Decimal("0"),
                "cost_basis": Decimal("0"),
                "realized_profit": Decimal("0"),
            }

        if t.transaction_type == "BUY":
            by_ticker[ticker]["quantity"] += qty
            by_ticker[ticker]["cost_basis"] += cost
        else:  # SELL
            by_ticker[ticker]["quantity"] -= qty
            avg_cost = by_ticker[ticker]["cost_basis"] / by_ticker[ticker]["quantity"] if by_ticker[ticker]["quantity"] != 0 else Decimal("0")
            by_ticker[ticker]["cost_basis"] -= qty * (by_ticker[ticker]["cost_basis"] / (by_ticker[ticker]["quantity"] + qty) if (by_ticker[ticker]["quantity"] + qty) != 0 else Decimal("0"))
            # Simplified: realized = sell proceeds - cost of shares sold
            proceeds = qty * price - fees
            cost_sold = qty * (by_ticker[ticker]["cost_basis"] / (by_ticker[ticker]["quantity"] + qty)) if (by_ticker[ticker]["quantity"] + qty) != 0 else Decimal("0")
            by_ticker[ticker]["realized_profit"] += proceeds - cost_sold

    # Clean up: only positions with quantity > 0
    positions = []
    for ticker, data in by_ticker.items():
        if data["quantity"] > 0:
            positions.append(data)
    return positions


def compute_positions_simple(db: Session, user_id: int) -> List[dict]:
    """
    Simpler position computation: average cost, no complex FIFO.
    """
    trans = crud.get_user_transactions(db, user_id)
    by_ticker: dict[str, dict] = {}

    for t in trans:
        ticker = t.ticker
        qty = Decimal(str(t.quantity))
        price = Decimal(str(t.price))
        fees = Decimal(str(t.fees or 0))

        if ticker not in by_ticker:
            by_ticker[ticker] = {
                "ticker": ticker,
                "stock_name": t.stock_name,
                "quantity": Decimal("0"),
                "total_cost": Decimal("0"),
                "realized_profit": Decimal("0"),
            }

        if t.transaction_type == "BUY":
            by_ticker[ticker]["quantity"] += qty
            by_ticker[ticker]["total_cost"] += qty * price + fees
        else:
            old_qty = by_ticker[ticker]["quantity"]
            if old_qty > 0:
                avg = by_ticker[ticker]["total_cost"] / old_qty
                sell_qty = min(qty, old_qty)
                cost_sold = sell_qty * avg
                by_ticker[ticker]["total_cost"] -= cost_sold
                proceeds = sell_qty * price - (fees * sell_qty / qty if qty else Decimal("0"))
                by_ticker[ticker]["realized_profit"] += proceeds - cost_sold
            by_ticker[ticker]["quantity"] -= qty

    positions = [v for v in by_ticker.values() if v["quantity"] > 0]
    return positions


def get_portfolio_summary(
    db: Session,
    user_id: int,
    price_fetcher: Optional[Callable[[str], Optional[Decimal]]] = None,
) -> PortfolioSummary:
    """Get full portfolio summary with current prices."""
    positions_data = compute_positions_simple(db, user_id)
    positions: List[Position] = []
    total_cost = Decimal("0")
    total_mv = Decimal("0")
    total_realized = Decimal("0")
    total_unrealized = Decimal("0")

    for p in positions_data:
        qty = p["quantity"]
        cost = p["total_cost"]
        realized = p["realized_profit"]
        current = get_current_price(p["ticker"], price_fetcher)
        mv = current * qty if current else None
        unrealized = (mv - cost) if mv is not None else None
        unrealized_pct = (float(unrealized / cost) * 100) if unrealized is not None and cost and cost != 0 else None

        total_cost += cost
        if mv is not None:
            total_mv += mv
            total_unrealized += unrealized or Decimal("0")
        total_realized += realized

        positions.append(
            Position(
                user_id=user_id,
                ticker=p["ticker"],
                stock_name=p["stock_name"],
                total_quantity=qty,
                average_buy_price=cost / qty if qty else Decimal("0"),
                total_cost=cost,
                current_price=current,
                market_value=mv,
                realized_profit=realized,
                unrealized_profit=unrealized,
                unrealized_profit_pct=unrealized_pct,
            )
        )

    total_return_pct = 0.0
    if total_cost and total_cost > 0 and total_mv > 0:
        total_return_pct = float((total_mv + total_realized - total_cost) / total_cost * 100)

    return PortfolioSummary(
        user_id=user_id,
        total_cost=total_cost,
        total_market_value=total_mv,
        total_realized_profit=total_realized,
        total_unrealized_profit=total_unrealized,
        total_return_pct=total_return_pct,
        positions=positions,
    )


async def get_portfolio_summary_async(db: Session, user_id: int) -> PortfolioSummary:
    """Get portfolio summary using async scrapers (for use inside asyncio e.g. Telegram)."""
    positions_data = compute_positions_simple(db, user_id)
    positions: List[Position] = []
    total_cost = Decimal("0")
    total_mv = Decimal("0")
    total_realized = Decimal("0")
    total_unrealized = Decimal("0")

    for p in positions_data:
        qty = p["quantity"]
        cost = p["total_cost"]
        realized = p["realized_profit"]
        quote = await scrape_stock_price_async(p["ticker"])
        current = Decimal(str(quote.price)) if quote else None
        mv = current * qty if current else None
        unrealized = (mv - cost) if mv is not None else None
        unrealized_pct = (float(unrealized / cost) * 100) if unrealized is not None and cost and cost != 0 else None

        total_cost += cost
        if mv is not None:
            total_mv += mv
            total_unrealized += unrealized or Decimal("0")
        total_realized += realized

        positions.append(
            Position(
                user_id=user_id,
                ticker=p["ticker"],
                stock_name=p["stock_name"],
                total_quantity=qty,
                average_buy_price=cost / qty if qty else Decimal("0"),
                total_cost=cost,
                current_price=current,
                market_value=mv,
                realized_profit=realized,
                unrealized_profit=unrealized,
                unrealized_profit_pct=unrealized_pct,
            )
        )

    total_return_pct = 0.0
    if total_cost and total_cost > 0 and total_mv > 0:
        total_return_pct = float((total_mv + total_realized - total_cost) / total_cost * 100)

    return PortfolioSummary(
        user_id=user_id,
        total_cost=total_cost,
        total_market_value=total_mv,
        total_realized_profit=total_realized,
        total_unrealized_profit=total_unrealized,
        total_return_pct=total_return_pct,
        positions=positions,
    )


def parse_transaction_text(text: str) -> Optional[dict]:
    """
    Parse transaction from text like:
    BUY SNTS 100 @ 5000
    SELL ETIT 50 @ 12000
    BUY BICC 200 4500 XOF
    """
    import re

    text = text.strip().upper()
    # BUY/SELL TICKER QTY @ PRICE
    m = re.match(r"(BUY|SELL)\s+(\w+)\s+([\d.]+)\s+(?:@\s*)?([\d.]+)(?:\s+(\w+))?", text)
    if m:
        return {
            "type": m.group(1),
            "ticker": m.group(2),
            "quantity": Decimal(m.group(3)),
            "price": Decimal(m.group(4)),
            "currency": m.group(5) or "XOF",
        }
    return None


def parse_transaction_csv(lines: List[str]) -> List[dict]:
    """
    Parse CSV with columns: type,ticker,quantity,price,date[,fees,notes]
    """
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO("\n".join(lines)))
    out = []
    for row in reader:
        t = row.get("type", row.get("transaction_type", "")).upper()
        if t not in ("BUY", "SELL"):
            continue
        try:
            from datetime import datetime

            date_str = row.get("date", row.get("transaction_date", ""))
            dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d") if date_str else datetime.utcnow()
            out.append({
                "type": t,
                "ticker": row.get("ticker", "").strip().upper(),
                "quantity": Decimal(str(row.get("quantity", 0))),
                "price": Decimal(str(row.get("price", 0))),
                "date": dt,
                "fees": Decimal(str(row.get("fees", 0))),
                "notes": row.get("notes", ""),
                "stock_name": row.get("stock_name", row.get("ticker", "")),
            })
        except (ValueError, KeyError) as e:
            logger.warning("Skip CSV row: %s", e)
    return out
