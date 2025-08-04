# TennisSlotBot

Automated tennis slot booking bot.

## Setup

1. Clone repo.
2. Install deps: pip install -r requirements.txt
3. Set .env vars.
4. Run: python main.py

## Docker

docker build -t tennis-slot-bot .
docker run -v $(pwd)/data:/app/data -e FERNET_KEY=your_key tennis-slot-bot
