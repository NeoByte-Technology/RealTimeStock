"""
Telegram bot for West Africa Financial Intelligence Agent.

Commands: /start, /portfolio, /analyze, /watchlist, /add_stock, /remove_stock
Supports: text transaction input, CSV upload, PDF upload
"""

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Optional

from core.config import settings
from core.logger import get_logger
from database.connection import SessionLocal, init_db
from database import crud
from services.portfolio_service import (
    get_portfolio_summary,
    get_portfolio_summary_async,
    parse_transaction_text,
    parse_transaction_csv,
)
from core.agent import FinancialAgent
from core.tools import AgentTools

logger = get_logger("telegram_bot")

# Lazy init to avoid import errors if telegram not installed
_bot_instance = None
_agent_instance = None


def get_bot():
    """Get or create Telegram bot application."""
    global _bot_instance
    if _bot_instance is None:
        from telegram import Bot
        from telegram.ext import Application

        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        _register_handlers(app)
        _bot_instance = app
    return _bot_instance


def _register_handlers(app):
    """Register all command and message handlers."""
    from telegram.ext import CommandHandler, MessageHandler, filters

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("add_stock", cmd_add_stock))
    app.add_handler(CommandHandler("remove_stock", cmd_remove_stock))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))


def _get_agent() -> FinancialAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = FinancialAgent()
    return _agent_instance


async def _ensure_user(update) -> Optional[tuple]:
    """Ensure user exists and is allowed. Returns (db, user) or None."""
    if not settings.is_telegram_user_allowed(str(update.effective_user.id)):
        await update.message.reply_text("Access denied.")
        return None
    db = SessionLocal()
    try:
        user = crud.get_or_create_user(
            db,
            telegram_id=str(update.effective_user.id),
            name=update.effective_user.full_name or "",
            username=update.effective_user.username or "",
        )
        return (db, user)
    except Exception as e:
        logger.exception("User ensure failed: %s", e)
        return None


async def cmd_start(update, context):
    """Handle /start."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result
    db.close()

    await update.message.reply_text(
        f"Welcome to {settings.PROJECT_NAME}!\n\n"
        "Commands:\n"
        "/portfolio - View your portfolio\n"
        "/analyze <ticker> - Analyze a stock\n"
        "/watchlist - View watchlist\n"
        "/add_stock <ticker> - Add to watchlist\n"
        "/remove_stock <ticker> - Remove from watchlist\n\n"
        "You can also:\n"
        "- Send: BUY SNTS 100 @ 5000\n"
        "- Send: SELL ETIT 50 @ 12000\n"
        "- Upload CSV with transactions"
    )


async def cmd_portfolio(update, context):
    """Handle /portfolio."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result
    try:
        summary = await get_portfolio_summary_async(db, user.id)
        if not summary.positions:
            await update.message.reply_text("Your portfolio is empty. Add transactions to get started.")
            return

        lines = [f"*Portfolio Summary*", f"Total cost: {summary.total_cost:,.0f} XOF"]
        if summary.total_market_value > 0:
            lines.append(f"Market value: {summary.total_market_value:,.0f} XOF")
            lines.append(f"Total return: {summary.total_return_pct:+.1f}%")
        lines.append("")

        for p in summary.positions:
            line = f"{p.ticker}: {p.total_quantity} @ avg {p.average_buy_price:,.0f} XOF"
            if p.current_price:
                line += f" | Now: {p.current_price:,.0f}"
                if p.unrealized_profit_pct is not None:
                    line += f" ({p.unrealized_profit_pct:+.1f}%)"
            lines.append(line)

        # AI summary
        agent = _get_agent()
        summary_dict = {
            "total_cost": float(summary.total_cost),
            "total_market_value": float(summary.total_market_value or 0),
            "total_return_pct": summary.total_return_pct,
            "positions_count": len(summary.positions),
        }
        ai_text = agent.explain_portfolio(summary_dict)
        lines.append(f"\n_{ai_text}_")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Portfolio error: %s", e)
        await update.message.reply_text(f"Error: {e}")
    finally:
        db.close()


async def cmd_analyze(update, context):
    """Handle /analyze <ticker>."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result

    ticker = " ".join(context.args).strip().upper() if context.args else ""
    if not ticker:
        await update.message.reply_text("Usage: /analyze <ticker> e.g. /analyze SNTS")
        db.close()
        return

    try:
        agent = _get_agent()
        analysis = await agent.analyze_with_ai_async(ticker)

        if "error" in analysis:
            await update.message.reply_text(analysis["error"])
            db.close()
            return

        lines = [
            f"*{ticker} Analysis*",
            f"Price: {analysis['current_price']:,.0f} {analysis.get('currency', 'XOF')}",
        ]
        if analysis.get("daily_return_pct") is not None:
            lines.append(f"1d return: {analysis['daily_return_pct']:+.2f}%")
        if analysis.get("monthly_return_pct") is not None:
            lines.append(f"~1m return: {analysis['monthly_return_pct']:+.2f}%")
        if analysis.get("volatility_annualized") is not None:
            lines.append(f"Volatility: {analysis['volatility_annualized']:.1f}%")
        if analysis.get("ma_20"):
            lines.append(f"MA20: {analysis['ma_20']:,.0f}")
        if analysis.get("ma_50"):
            lines.append(f"MA50: {analysis['ma_50']:,.0f}")
        if analysis.get("signal"):
            lines.append(f"Signal: {analysis['signal']}")

        lines.append(f"\n{analysis.get('ai_summary', '')}")
        lines.append(f"\nRisk: {analysis.get('ai_risk_analysis', '')}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Analyze error: %s", e)
        await update.message.reply_text(f"Error: {e}")
    finally:
        db.close()


async def cmd_watchlist(update, context):
    """Handle /watchlist."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result
    try:
        watchlist = crud.get_watchlist(db, user.id)
        if not watchlist:
            await update.message.reply_text("Your watchlist is empty. Use /add_stock <ticker>")
            return

        tools = AgentTools()
        lines = ["*Watchlist*"]
        for w in watchlist:
            quote = await tools.get_current_stock_price_async(w.ticker)
            if quote:
                change = f" ({quote['change_pct']:+.1f}%)" if quote.get("change_pct") else ""
                lines.append(f"• {w.ticker}: {quote['price']:,.0f} XOF{change}")
            else:
                lines.append(f"• {w.ticker} (no price)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Watchlist error: %s", e)
        await update.message.reply_text(f"Error: {e}")
    finally:
        db.close()


async def cmd_add_stock(update, context):
    """Handle /add_stock <ticker>."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result

    ticker = " ".join(context.args).strip().upper() if context.args else ""
    if not ticker:
        await update.message.reply_text("Usage: /add_stock <ticker> e.g. /add_stock SNTS")
        db.close()
        return

    try:
        w = crud.add_to_watchlist(db, user.id, ticker)
        await update.message.reply_text(f"Added {w.ticker} to watchlist.")
    except Exception as e:
        logger.exception("Add stock error: %s", e)
        await update.message.reply_text(f"Error: {e}")
    finally:
        db.close()


async def cmd_remove_stock(update, context):
    """Handle /remove_stock <ticker>."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result

    ticker = " ".join(context.args).strip().upper() if context.args else ""
    if not ticker:
        await update.message.reply_text("Usage: /remove_stock <ticker>")
        db.close()
        return

    try:
        removed = crud.remove_from_watchlist(db, user.id, ticker)
        await update.message.reply_text(f"Removed {ticker} from watchlist." if removed else f"{ticker} was not in watchlist.")
    except Exception as e:
        logger.exception("Remove stock error: %s", e)
        await update.message.reply_text(f"Error: {e}")
    finally:
        db.close()


async def handle_text(update, context):
    """Handle free text - try to parse as transaction."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result

    text = update.message.text.strip()
    parsed = parse_transaction_text(text)
    if parsed:
        try:
            t = crud.create_transaction(
                db,
                user_id=user.id,
                stock_name=parsed["ticker"],
                ticker=parsed["ticker"],
                transaction_type=parsed["type"],
                quantity=parsed["quantity"],
                price=parsed["price"],
                transaction_date=datetime.utcnow(),
                currency=parsed.get("currency", "XOF"),
            )
            await update.message.reply_text(
                f"Recorded: {t.transaction_type} {t.quantity} {t.ticker} @ {t.price} XOF"
            )
        except Exception as e:
            logger.exception("Transaction save error: %s", e)
            await update.message.reply_text(f"Error saving: {e}")
        finally:
            db.close()
        return

    # Not a transaction - maybe ask for analysis?
    await update.message.reply_text(
        "Send a transaction like: BUY SNTS 100 @ 5000\nOr use /analyze <ticker>"
    )
    db.close()


async def handle_document(update, context):
    """Handle CSV/PDF upload."""
    result = await _ensure_user(update)
    if not result:
        return
    db, user = result

    doc = update.message.document
    if not doc:
        db.close()
        return

    file = await context.bot.get_file(doc.file_id)
    bytes_io = io.BytesIO()
    await file.download_to_memory(bytes_io)
    bytes_io.seek(0)
    content = bytes_io.read().decode("utf-8", errors="ignore")

    # Try CSV
    if doc.file_name and doc.file_name.lower().endswith(".csv"):
        try:
            lines = content.strip().split("\n")
            if not lines:
                await update.message.reply_text("CSV is empty.")
                db.close()
                return

            transactions = parse_transaction_csv(lines)
            created = 0
            for t in transactions:
                try:
                    crud.create_transaction(
                        db,
                        user_id=user.id,
                        stock_name=t.get("stock_name", t["ticker"]),
                        ticker=t["ticker"],
                        transaction_type=t["type"],
                        quantity=t["quantity"],
                        price=t["price"],
                        transaction_date=t.get("date", datetime.utcnow()),
                        fees=t.get("fees", Decimal("0")),
                        notes=t.get("notes", ""),
                    )
                    created += 1
                except Exception as e:
                    logger.warning("Skip transaction: %s", e)
            await update.message.reply_text(f"Imported {created} transactions from CSV.")
        except Exception as e:
            logger.exception("CSV import error: %s", e)
            await update.message.reply_text(f"CSV import error: {e}")
        finally:
            db.close()
        return

    # PDF - basic text extraction
    if doc.file_name and doc.file_name.lower().endswith(".pdf"):
        try:
            import PyPDF2

            pdf_reader = PyPDF2.PdfReader(bytes_io)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            # Try to find transaction-like lines
            parsed_any = False
            for line in text.split("\n"):
                p = parse_transaction_text(line)
                if p:
                    try:
                        crud.create_transaction(
                            db,
                            user_id=user.id,
                            stock_name=p["ticker"],
                            ticker=p["ticker"],
                            transaction_type=p["type"],
                            quantity=p["quantity"],
                            price=p["price"],
                            transaction_date=datetime.utcnow(),
                            currency=p.get("currency", "XOF"),
                        )
                        parsed_any = True
                    except Exception:
                        pass
            await update.message.reply_text(
                "PDF processed. " + (f"Imported transactions from PDF." if parsed_any else "No transactions found in PDF.")
            )
        except ImportError:
            await update.message.reply_text("PDF parsing requires PyPDF2. Install: pip install PyPDF2")
        except Exception as e:
            logger.exception("PDF import error: %s", e)
            await update.message.reply_text(f"PDF error: {e}")
        finally:
            db.close()
        return

    await update.message.reply_text("Supported: CSV, PDF. Send a .csv or .pdf file.")
    db.close()


def send_telegram_message(user_id: int, text: str) -> bool:
    """Send message to user by internal user_id. Resolves telegram_id from users table."""
    from database.models import User
    from telegram import Bot

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("User %s not found for Telegram notify", user_id)
            return False
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=user.telegram_id, text=text)
        return True
    except Exception as e:
        logger.exception("Telegram send failed: %s", e)
        return False
    finally:
        db.close()


def run_bot_polling():
    """Run bot with long polling."""
    init_db()
    app = get_bot()
    app.run_polling(allowed_updates=["message"])


def run_bot_webhook():
    """Run bot with webhook (production)."""
    from telegram.ext import Application

    init_db()
    app = get_bot()
    app.run_webhook(
        listen="0.0.0.0",
        port=8080,
        url_path=settings.TELEGRAM_BOT_TOKEN,
        webhook_url=settings.TELEGRAM_WEBHOOK_URL or "",
    )
