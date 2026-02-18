"""
West Africa Financial Intelligence Agent - Main Entry Point

Run:
  python main.py bot      - Start Telegram bot (polling)
  python main.py analyze <ticker> - CLI stock analysis
  python main.py init-db  - Initialize database
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Minimal imports for all commands
from core.config import settings


def cmd_bot():
    """Start Telegram bot with polling."""
    from core.logger import setup_logging
    setup_logging()
    from integrations.telegram_bot import run_bot_polling
    from services.scheduler import start_scheduler

    start_scheduler()
    run_bot_polling()


def cmd_analyze(ticker: str):
    """CLI stock analysis."""
    from core.logger import setup_logging
    setup_logging()
    from core.agent import FinancialAgent

    agent = FinancialAgent()
    result = agent.analyze_with_ai(ticker)
    if "error" in result:
        print(result["error"])
        return 1
    print(f"\n{result.get('ticker', ticker)} Analysis")
    print("-" * 40)
    for k, v in result.items():
        if k not in ("ai_summary", "ai_risk_analysis"):
            print(f"  {k}: {v}")
    if result.get("ai_summary"):
        print(f"\nSummary: {result['ai_summary']}")
    if result.get("ai_risk_analysis"):
        print(f"Risk: {result['ai_risk_analysis']}")
    return 0


def cmd_init_db():
    """Initialize database schema."""
    from database.connection import init_db

    init_db()
    print("Database initialized.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=settings.PROJECT_NAME)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("bot", help="Start Telegram bot")
    a = sub.add_parser("analyze", help="Analyze a stock (CLI)")
    a.add_argument("ticker", help="Stock ticker e.g. SNTS")
    sub.add_parser("init-db", help="Initialize database")

    args = parser.parse_args()

    if args.command == "bot":
        cmd_bot()
    elif args.command == "analyze":
        sys.exit(cmd_analyze(args.ticker))
    elif args.command == "init-db":
        sys.exit(cmd_init_db())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
