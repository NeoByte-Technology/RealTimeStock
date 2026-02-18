"""
Alert service - threshold checks, portfolio monitoring, notifications.

Uses APScheduler for background jobs.
"""

from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.logger import get_logger
from database import crud
from database.connection import SessionLocal
from integrations.scrapers import scrape_stock_price
from services.portfolio_service import get_portfolio_summary

logger = get_logger("alert_service")


def check_price_alerts(db: Session, telegram_notify: Callable[[str, int, str], None]) -> List[dict]:
    """
    Check all active price/loss/gain alert rules.
    Returns list of triggered alerts.
    """
    rules = crud.get_active_alert_rules(db)
    triggered = []

    for rule in rules:
        quote = scrape_stock_price(rule.ticker)
        if not quote:
            continue

        price = float(quote.price)
        ticker = quote.ticker

        if rule.rule_type == "price_above" and price >= rule.threshold_value:
            msg = f"Alert: {ticker} price {price} XOF >= {rule.threshold_value}"
            triggered.append({"rule_id": rule.id, "user_id": rule.user_id, "message": msg})
            crud.update_alert_last_triggered(db, rule.id)
            telegram_notify(msg, rule.user_id, "price_alert")

        elif rule.rule_type == "price_below" and price <= rule.threshold_value:
            msg = f"Alert: {ticker} price {price} XOF <= {rule.threshold_value}"
            triggered.append({"rule_id": rule.id, "user_id": rule.user_id, "message": msg})
            crud.update_alert_last_triggered(db, rule.id)
            telegram_notify(msg, rule.user_id, "price_alert")

        elif rule.rule_type == "loss_pct":
            # Need portfolio position to compute loss
            pos_list = [p for p in get_portfolio_summary(db, rule.user_id).positions if p.ticker == ticker]
            if pos_list:
                pos = pos_list[0]
                if pos.unrealized_profit_pct is not None and pos.unrealized_profit_pct <= -rule.threshold_value:
                    msg = f"Alert: {ticker} loss {pos.unrealized_profit_pct:.1f}% >= threshold {rule.threshold_value}%"
                    triggered.append({"rule_id": rule.id, "user_id": rule.user_id, "message": msg})
                    crud.update_alert_last_triggered(db, rule.id)
                    telegram_notify(msg, rule.user_id, "loss_alert")

        elif rule.rule_type == "gain_pct":
            pos_list = [p for p in get_portfolio_summary(db, rule.user_id).positions if p.ticker == ticker]
            if pos_list:
                pos = pos_list[0]
                if pos.unrealized_profit_pct is not None and pos.unrealized_profit_pct >= rule.threshold_value:
                    msg = f"Alert: {ticker} gain {pos.unrealized_profit_pct:.1f}% >= threshold {rule.threshold_value}%"
                    triggered.append({"rule_id": rule.id, "user_id": rule.user_id, "message": msg})
                    crud.update_alert_last_triggered(db, rule.id)
                    telegram_notify(msg, rule.user_id, "gain_alert")

    return triggered


def check_portfolio_daily(
    db: Session,
    telegram_notify: Callable[[str, int, str], None],
    loss_threshold: Optional[float] = None,
    gain_threshold: Optional[float] = None,
) -> List[dict]:
    """
    Daily portfolio check. Notify users when loss/gain exceeds thresholds.
    """
    loss_threshold = loss_threshold or settings.ALERT_LOSS_THRESHOLD_PCT
    gain_threshold = gain_threshold or settings.ALERT_GAIN_THRESHOLD_PCT

    # Get all users with transactions
    from database.models import User

    users = db.query(User).filter(User.is_active == True).all()
    triggered = []

    for user in users:
        try:
            summary = get_portfolio_summary(db, user.id)
            if summary.total_cost <= 0:
                continue

            total_return = summary.total_return_pct
            if total_return <= -loss_threshold:
                msg = f"Portfolio alert: total return {total_return:.1f}% (loss threshold {loss_threshold}%)"
                triggered.append({"user_id": user.id, "message": msg})
                telegram_notify(msg, user.id, "portfolio_loss")
            elif total_return >= gain_threshold:
                msg = f"Portfolio alert: total return +{total_return:.1f}% (gain threshold {gain_threshold}%)"
                triggered.append({"user_id": user.id, "message": msg})
                telegram_notify(msg, user.id, "portfolio_gain")

        except Exception as e:
            logger.exception("Portfolio check failed for user %s: %s", user.id, e)

    return triggered


def check_watchlist_prices(
    db: Session,
    telegram_notify: Callable[[str, int, str], None],
) -> None:
    """Check watchlist stock prices and notify on significant moves."""
    from database.models import Watchlist

    items = db.query(Watchlist).all()
    for w in items:
        quote = scrape_stock_price(w.ticker)
        if quote and quote.change_pct and abs(quote.change_pct) >= 5:
            msg = f"Watchlist: {w.ticker} {quote.change_pct:+.1f}% @ {quote.price} XOF"
            telegram_notify(msg, w.user_id, "watchlist")


def run_scheduled_jobs(telegram_notify: Callable[[str, int, str], None]) -> None:
    """Run all scheduled alert jobs."""
    db = SessionLocal()
    try:
        check_price_alerts(db, telegram_notify)
        check_portfolio_daily(db, telegram_notify)
    finally:
        db.close()
