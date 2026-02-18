# West Africa Financial Intelligence Agent
# Python 3.11+ - Uses Tavily API (no Playwright)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default: run bot
CMD ["python", "main.py", "bot"]
