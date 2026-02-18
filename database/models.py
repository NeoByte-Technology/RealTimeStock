"""
SQLAlchemy models for West Africa Financial Intelligence Agent.

Schema supports:
- Users (Telegram)
- Transactions (BUY/SELL)
- Watchlist
- Alert rules
- Stock prices (historical cache)
- Company news (cache)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """Telegram user."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="user")
    watchlist = relationship("Watchlist", back_populates="user")
    alert_rules = relationship("AlertRule", back_populates="user")


class Transaction(Base):
    """Buy/Sell transactions."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_name = Column(String(255), nullable=False)
    ticker = Column(String(32), nullable=False, index=True)
    transaction_type = Column(String(8), nullable=False)  # BUY | SELL
    quantity = Column(Numeric(18, 6), nullable=False)
    price = Column(Numeric(18, 6), nullable=False)
    fees = Column(Numeric(18, 6), default=Decimal("0"))
    currency = Column(String(8), default="XOF")
    transaction_date = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class Watchlist(Base):
    """User watchlist stocks."""

    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(32), nullable=False, index=True)
    stock_name = Column(String(255), nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),)

    user = relationship("User", back_populates="watchlist")


class AlertRule(Base):
    """User-defined alert rules."""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(32), nullable=False, index=True)
    rule_type = Column(String(32), nullable=False)  # price_above, price_below, loss_pct, gain_pct
    threshold_value = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="alert_rules")


class StockPrice(Base):
    """Historical stock price cache."""

    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(32), nullable=False, index=True)
    price = Column(Numeric(18, 6), nullable=False)
    currency = Column(String(8), default="XOF")
    source = Column(String(64), nullable=True)
    price_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("ticker", "price_date", name="uq_stock_price_ticker_date"),)


class CompanyNews(Base):
    """Company news cache."""

    __tablename__ = "company_news"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(32), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    source = Column(String(128), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
