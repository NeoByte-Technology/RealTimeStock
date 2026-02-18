"""
CRUD operations for West Africa Financial Intelligence Agent.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from database.models import (
    AlertRule,
    CompanyNews,
    StockPrice,
    Transaction,
    User,
    Watchlist,
)


# --- Users ---


def get_user_by_telegram_id(db: Session, telegram_id: str) -> Optional[User]:
    """Get user by Telegram ID."""
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


def get_or_create_user(db: Session, telegram_id: str, name: str = "", username: str = "") -> User:
    """Get or create user by Telegram ID."""
    user = get_user_by_telegram_id(db, telegram_id)
    if user:
        if name:
            user.name = name
        if username:
            user.username = username
        db.commit()
        db.refresh(user)
        return user
    user = User(telegram_id=str(telegram_id), name=name or None, username=username or None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- Transactions ---


def create_transaction(
    db: Session,
    user_id: int,
    stock_name: str,
    ticker: str,
    transaction_type: str,
    quantity: Decimal,
    price: Decimal,
    transaction_date: datetime,
    fees: Decimal = Decimal("0"),
    currency: str = "XOF",
    notes: str = "",
) -> Transaction:
    """Create a transaction record."""
    t = Transaction(
        user_id=user_id,
        stock_name=stock_name,
        ticker=ticker.upper(),
        transaction_type=transaction_type.upper(),
        quantity=quantity,
        price=price,
        fees=fees,
        currency=currency,
        transaction_date=transaction_date,
        notes=notes or None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def get_user_transactions(
    db: Session,
    user_id: int,
    ticker: Optional[str] = None,
    limit: int = 100,
) -> List[Transaction]:
    """Get transactions for a user, optionally filtered by ticker."""
    q = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(desc(Transaction.transaction_date))
    if ticker:
        q = q.filter(Transaction.ticker == ticker.upper())
    return q.limit(limit).all()


def get_transactions_by_ticker(db: Session, user_id: int, ticker: str) -> List[Transaction]:
    """Get all transactions for a user for a specific ticker."""
    return get_user_transactions(db, user_id, ticker=ticker, limit=1000)


# --- Watchlist ---


def add_to_watchlist(db: Session, user_id: int, ticker: str, stock_name: str = "") -> Watchlist:
    """Add stock to user watchlist."""
    existing = db.query(Watchlist).filter(Watchlist.user_id == user_id, Watchlist.ticker == ticker.upper()).first()
    if existing:
        return existing
    w = Watchlist(user_id=user_id, ticker=ticker.upper(), stock_name=stock_name or None)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def remove_from_watchlist(db: Session, user_id: int, ticker: str) -> bool:
    """Remove stock from watchlist. Returns True if removed."""
    w = db.query(Watchlist).filter(Watchlist.user_id == user_id, Watchlist.ticker == ticker.upper()).first()
    if w:
        db.delete(w)
        db.commit()
        return True
    return False


def get_watchlist(db: Session, user_id: int) -> List[Watchlist]:
    """Get user watchlist."""
    return db.query(Watchlist).filter(Watchlist.user_id == user_id).all()


# --- Alert Rules ---


def create_alert_rule(
    db: Session,
    user_id: int,
    ticker: str,
    rule_type: str,
    threshold_value: float,
) -> AlertRule:
    """Create alert rule."""
    r = AlertRule(user_id=user_id, ticker=ticker.upper(), rule_type=rule_type, threshold_value=threshold_value)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def get_active_alert_rules(db: Session, ticker: Optional[str] = None) -> List[AlertRule]:
    """Get active alert rules, optionally for a ticker."""
    q = db.query(AlertRule).filter(AlertRule.is_active == True)
    if ticker:
        q = q.filter(AlertRule.ticker == ticker.upper())
    return q.all()


def get_user_alert_rules(db: Session, user_id: int) -> List[AlertRule]:
    """Get alert rules for a user."""
    return db.query(AlertRule).filter(AlertRule.user_id == user_id, AlertRule.is_active == True).all()


def deactivate_alert_rule(db: Session, rule_id: int, user_id: int) -> bool:
    """Deactivate an alert rule."""
    r = db.query(AlertRule).filter(AlertRule.id == rule_id, AlertRule.user_id == user_id).first()
    if r:
        r.is_active = False
        db.commit()
        return True
    return False


def update_alert_last_triggered(db: Session, rule_id: int) -> None:
    """Update last triggered timestamp."""
    r = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if r:
        r.last_triggered_at = datetime.utcnow()
        db.commit()


# --- Stock Prices (cache) ---


def upsert_stock_price(
    db: Session,
    ticker: str,
    price: Decimal,
    price_date: datetime,
    currency: str = "XOF",
    source: str = "",
) -> StockPrice:
    """Insert or update stock price for a date."""
    existing = (
        db.query(StockPrice)
        .filter(StockPrice.ticker == ticker.upper(), func.date(StockPrice.price_date) == price_date.date())
        .first()
    )
    if existing:
        existing.price = price
        existing.source = source or existing.source
        db.commit()
        db.refresh(existing)
        return existing
    sp = StockPrice(ticker=ticker.upper(), price=price, currency=currency, price_date=price_date, source=source)
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp


def get_stock_prices(db: Session, ticker: str, days: int = 90) -> List[StockPrice]:
    """Get historical stock prices for a ticker."""
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(StockPrice)
        .filter(StockPrice.ticker == ticker.upper(), StockPrice.price_date >= since)
        .order_by(StockPrice.price_date)
        .all()
    )


def get_latest_stock_price(db: Session, ticker: str) -> Optional[StockPrice]:
    """Get most recent cached price."""
    return (
        db.query(StockPrice)
        .filter(StockPrice.ticker == ticker.upper())
        .order_by(desc(StockPrice.price_date))
        .first()
    )


# --- Company News ---


def upsert_company_news(
    db: Session,
    ticker: str,
    title: str,
    summary: str = "",
    url: str = "",
    source: str = "",
    published_at: Optional[datetime] = None,
) -> CompanyNews:
    """Insert company news (avoid exact duplicate titles)."""
    existing = db.query(CompanyNews).filter(CompanyNews.ticker == ticker.upper(), CompanyNews.title == title).first()
    if existing:
        return existing
    n = CompanyNews(
        ticker=ticker.upper(),
        title=title,
        summary=summary,
        url=url,
        source=source,
        published_at=published_at,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def get_recent_news(db: Session, ticker: str, limit: int = 10) -> List[CompanyNews]:
    """Get recent news for a ticker."""
    return (
        db.query(CompanyNews)
        .filter(CompanyNews.ticker == ticker.upper())
        .order_by(desc(CompanyNews.published_at or CompanyNews.created_at))
        .limit(limit)
        .all()
    )
