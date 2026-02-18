"""
APScheduler jobs for West Africa Financial Intelligence Agent.

- Daily portfolio check
- Stock price monitoring (watchlist + alerts)
- News monitoring
"""

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.logger import get_logger
from database.connection import SessionLocal
from services.alert_service import check_price_alerts, check_portfolio_daily, run_scheduled_jobs

logger = get_logger("scheduler")

_scheduler = None


def _telegram_notify(message: str, user_id: int, alert_type: str) -> None:
    """Send Telegram notification. Used by alert service."""
    try:
        from integrations.telegram_bot import send_telegram_message

        send_telegram_message(user_id, f"[{alert_type}] {message}")
    except Exception as e:
        logger.exception("Notify failed for user %s: %s", user_id, e)


def _run_alerts():
    """Run all alert checks."""
    try:
        run_scheduled_jobs(_telegram_notify)
        logger.info("Scheduled alerts completed at %s", datetime.utcnow())
    except Exception as e:
        logger.exception("Alert job failed: %s", e)


def _run_portfolio_check():
    """Daily portfolio summary check."""
    try:
        db = SessionLocal()
        try:
            check_portfolio_daily(db, _telegram_notify)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Portfolio check job failed: %s", e)


def _run_price_monitoring():
    """Periodic price monitoring for alerts."""
    try:
        db = SessionLocal()
        try:
            check_price_alerts(db, _telegram_notify)
        finally:
            db.close()
    except Exception as e:
        logger.exception("Price monitoring job failed: %s", e)


def _run_price_cache():
    """Cache BRVM prices to DB for historical analysis."""
    try:
        from datetime import datetime
        from integrations.scrapers import scrape_brvm_prices
        from database import crud
        from database.connection import SessionLocal

        quotes = scrape_brvm_prices()
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            for q in quotes:
                crud.upsert_stock_price(db, q.ticker, q.price, now, "XOF", q.source)
            db.commit()
            logger.info("Cached %d stock prices", len(quotes))
        finally:
            db.close()
    except Exception as e:
        logger.exception("Price cache job failed: %s", e)


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler with all jobs."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()

    # Daily portfolio check
    _scheduler.add_job(
        _run_portfolio_check,
        CronTrigger(hour=settings.ALERT_PORTFOLIO_CHECK_HOUR, minute=0),
        id="portfolio_daily",
    )

    # Price alert monitoring - every N minutes
    _scheduler.add_job(
        _run_price_monitoring,
        IntervalTrigger(minutes=settings.ALERT_PRICE_CHECK_INTERVAL_MIN),
        id="price_alerts",
    )

    # Cache BRVM prices - daily
    _scheduler.add_job(
        _run_price_cache,
        CronTrigger(hour=18, minute=0),  # End of BRVM trading
        id="price_cache",
    )

    # Full alert run (includes portfolio) - daily
    _scheduler.add_job(
        _run_alerts,
        CronTrigger(hour=settings.ALERT_PORTFOLIO_CHECK_HOUR, minute=15),
        id="alerts_daily",
    )

    _scheduler.start()
    logger.info("Scheduler started with jobs: portfolio_daily, price_alerts, alerts_daily")
    return _scheduler


def stop_scheduler() -> None:
    """Stop the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
