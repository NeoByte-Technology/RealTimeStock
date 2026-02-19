# West Africa Financial Intelligence Agent

Production-ready AI financial agent focused on **BRVM** (Bourse Régionale des Valeurs Mobilières) and West African stock markets.


## Features

- **Web Intelligence**: Tavily API (Richbourse, Daba Finance for BRVM prices)
- **Stock Analysis**: Current price, historical data, returns, volatility, moving averages, P/E
- **Portfolio Management**: Track positions, transactions, watchlist, gains/losses
- **Telegram Bot**: Commands, text transactions, CSV/PDF upload
- **Alert System**: Price thresholds, loss/gain alerts, scheduled jobs (APScheduler)
- **AI Layer**: Ollama (local LLM) for summaries, risk analysis, natural language explanations

## Project Structure

```
RealTimeStock/
├── core/
│   ├── agent.py         # AI agent with LLM
│   ├── analyzer.py      # Stock metrics (returns, volatility, MA)
│   ├── config.py       # Settings from env
│   ├── logger.py       # Logging
│   └── tools.py        # Agent tools (search, scrape, analyze)
├── database/
│   ├── connection.py   # SQLAlchemy engine, session
│   ├── crud.py         # CRUD operations
│   └── models.py       # User, Transaction, Watchlist, AlertRule, StockPrice, CompanyNews
├── integrations/
│   ├── scrapers.py     # BRVM scraping
│   ├── telegram_bot.py # Telegram handlers
│   └── web_search.py   # Tavily search
├── services/
│   ├── alert_service.py    # Alert checks
│   ├── portfolio_service.py # Positions, parsing
│   └── scheduler.py        # APScheduler jobs
├── main.py
├── requirements.txt
├── .env.example
└── Dockerfile
```

## Database Schema

### Users
| Column      | Type   |
|------------|--------|
| id         | INT PK |
| telegram_id| VARCHAR UNIQUE |
| name       | VARCHAR |
| created_at | DATETIME |

### Transactions
| Column          | Type   |
|-----------------|--------|
| id              | INT PK |
| user_id         | INT FK |
| stock_name      | VARCHAR |
| ticker          | VARCHAR |
| transaction_type| BUY/SELL |
| quantity        | NUMERIC |
| price           | NUMERIC |
| fees            | NUMERIC |
| transaction_date| DATETIME |

### Watchlist
| Column   | Type   |
|----------|--------|
| user_id  | INT FK |
| ticker   | VARCHAR |

### Alert Rules
| Column         | Type   |
|----------------|--------|
| user_id        | INT FK |
| ticker         | VARCHAR |
| rule_type      | price_above/price_below/loss_pct/gain_pct |
| threshold_value| FLOAT  |

## Setup

### 1. Clone & install

```bash
cd RealTimeStock
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Ollama (local LLM)

Install [Ollama](https://ollama.com), then:

```bash
ollama serve
ollama pull llama3.2   # or gemma2, mistral, etc.
```

### 3. Environment

```bash
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN, TAVILY_API_KEY
# TAVILY_API_KEY is required for stock data (search + extract)
# LLM uses Ollama by default (no API keys needed)
```

### 4. Initialize database

```bash
python main.py init-db
```

### 5. Run the bot

```bash
python main.py bot
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome and help |
| `/portfolio` | Portfolio summary with AI explanation |
| `/analyze <ticker>` | Stock analysis (e.g. /analyze SNTS) |
| `/watchlist` | View watchlist with prices |
| `/add_stock <ticker>` | Add to watchlist |
| `/remove_stock <ticker>` | Remove from watchlist |

## Natural Language Queries

Ask questions in plain English and the AI will search the web and provide intelligent answers. Works in both CLI and Telegram bot.

### CLI Examples
```bash
python main.py query "what is the best performing stock today?"
python main.py query "which BRVM stocks are worth buying?"
python main.py query "how is Senegal's economy performing?"
python main.py query "give me latest news about Orange Senegal"
```

### Telegram Examples
Just send any question as a message:
```
What is the best performing stock today?
Which companies are in the BRVM index?
How are tech stocks performing in West Africa?
```

The bot will use Tavily search on trusted financial domains (Richbourse, Daba Finance, BRVM.org, Reuters, Investing.com) and provide an AI-generated answer based on the latest information.

## Text Transactions

Send a message like:
```
BUY SNTS 100 @ 5000
SELL ETIT 50 @ 12000
```

## CSV Upload

Upload a CSV with columns: `type,ticker,quantity,price,date,fees,notes`

Example:
```csv
type,ticker,quantity,price,date,fees,notes
BUY,SNTS,100,5000,2025-01-15,0,Initial purchase
SELL,ETIT,50,12000,2025-02-01,0,
```

## Docker

```bash
docker build -t west-africa-finagent .
docker run -e TELEGRAM_BOT_TOKEN=xxx -e OPENAI_API_KEY=xxx -e TAVILY_API_KEY=xxx west-africa-finagent
```

## Security

- Store secrets in `.env` (never commit)
- Use `TELEGRAM_ALLOWED_USERS` to whitelist Telegram IDs
- Enable `DEBUG=false` in production
- Validate all user inputs

## Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: West Africa Financial Intelligence Agent"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/RealTimeStock.git
git push -u origin main
```

> **Note:** Ensure `.env` is never committed (it's in `.gitignore`). Use `.env.example` as a template.

## License

MIT
