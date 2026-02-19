# Natural Language Query Feature

## Overview

The agent has been enhanced to accept **natural language queries** instead of just structured commands. Now you can ask questions in plain English, and the agent will:

1. Use Tavily search to find relevant information from trusted financial sources
2. Process the results with the LLM (Ollama, OpenAI, or Anthropic)
3. Return an intelligent, context-aware answer

## Usage

### CLI Interface

```bash
# Ask any financial question
python main.py query "what is the best performing stock today?"
python main.py query "which BRVM stocks are worth buying?"
python main.py query "how is Senegal's economy performing?"
python main.py query "give me latest news about Orange Senegal"
python main.py query "what caused the drop in SNTS stock price?"
```

### Telegram Bot

Simply send any message to the bot:
```
What is the best performing stock today?
Which companies are in the BRVM index?
How are tech stocks performing in West Africa?
Which stocks have the highest dividend yields?
```

The bot will:
1. First try to parse it as a transaction (e.g., "BUY SNTS 100 @ 5000")
2. If not a transaction, treat it as a natural language query
3. Search trusted financial websites
4. Return an AI-generated answer

## How It Works

### Trusted Sources

The Tavily search is configured to only search these trusted financial domains:
- **richbourse.com** - BRVM price data
- **dabafinance.com** - West African finance news
- **brvm.org** - Official BRVM website
- **reuters.com** - International financial news
- **investing.com** - Stock data and analysis

### Query Processing Pipeline

```
User Query
    ↓
Tavily Search (8 results + relevance scores)
    ↓
Format search results for LLM context
    ↓
LLM Processing (SYSTEM_PROMPT + search context)
    ↓
Natural Language Answer
```

### Example Query Flow

**User:** "What is the best performing stock today?"

**System:**
1. Searches: "what is the best performing stock today?" on trusted domains
2. Gets 8 results with scores (e.g., Reuters article 0.95, Investing.com post 0.87)
3. Formats results: `[1] Title... Relevance: 0.95 ...`
4. Builds LLM prompt with system guidelines + search context
5. LLM generates answer: "Based on today's market data, SNTS is up 2.5% leading BRVM performers..."

## Implementation Details

### New Methods Added

#### `FinancialAgent.query(user_query: str) -> str`
Synchronous version for CLI usage.

#### `FinancialAgent.query_async(user_query: str) -> str`
Asynchronous version for Telegram bot.

#### `FinancialAgent._format_search_results(results) -> str`
Helper method to format search results for LLM consumption.

### Modified Files

1. **core/agent.py**
   - Added `query()` and `query_async()` methods
   - Added `_format_search_results()` helper
   - Tavily search already imported

2. **main.py**
   - Added `cmd_query(question: str)` handler
   - Added `query` subcommand to argument parser
   - Updated docstring with usage

3. **integrations/telegram_bot.py**
   - Enhanced `handle_text()` to support natural language queries
   - Falls back to query processing if text isn't a transaction
   - Updated `/start` command to mention natural language capability

4. **README.md**
   - Added "Natural Language Queries" section with examples

## Configuration

No additional configuration needed! The feature uses:
- Existing **TAVILY_API_KEY** from environment
- Existing **LLM_PROVIDER** settings (ollama/openai/anthropic)
- Existing **SYSTEM_PROMPT** with BRVM expertise

## Error Handling

If Tavily search fails:
```
"I couldn't find relevant information to answer your question. Please try a more specific query."
```

If LLM is unavailable:
```
"Unable to process your query. Raw search results:\n[formatted results]"
```

## Future Enhancements

- [ ] Add conversation memory (multi-turn queries)
- [ ] Support follow-up questions with context
- [ ] Add query confidence scores
- [ ] Cache search results for repeated questions
- [ ] Add query history to database
- [ ] Support multi-language queries

## Examples

### CLI
```bash
$ python main.py query "best BRVM stocks 2025"

Question: best BRVM stocks 2025
----------------------------------------
Based on recent market data, several BRVM stocks are showing strong performance:

1. **SNTS** - Senegal Telecom is up 2.5% with strong dividend yields
2. **ETIT** - Orange Senegal maintains market leadership with consistent returns
3. **CRDT** - Credit mutuel Senegal shows growth momentum

The BRVM index overall is up 1.2% with technology and financial services sectors leading...
```

### Telegram
```
User: what stocks should I buy?
Bot: <bot shows typing indicator>
Bot: Based on current market analysis...

User: when is the SNTS earnings call?
Bot: <bot shows typing indicator>
Bot: SNTS scheduled its next earnings call for...
```
