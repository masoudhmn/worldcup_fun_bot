# Persian World Cup Prediction Telegram Bot

A production-ready, async, modular Telegram group bot for World Cup match predictions. The bot is Persian-language, funny, and isolates every Telegram group by `chat_id`, so each small group gets its own members, predictions, reminders, reports, and leaderboard.

## Stack

- Python 3.10+
- `python-telegram-bot` v22 async long-polling (`run_polling`)
- MySQL
- SQLAlchemy 2 async ORM
- `football-data.org` API v4, competition code `WC`
- `python-dotenv`
- No Flask, no webhooks, no external cron jobs

## Project layout

```text
worldcup_predictions_bot/
├── main.py
├── config.py
├── requirements.txt
├── .env.example
├── bot/
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── callbacks.py
│   │   ├── commands.py
│   │   ├── predictions.py
│   │   ├── reports.py
│   │   └── utils.py
│   ├── keyboards.py
│   └── messages_fa.py
├── services/
│   ├── background_tasks.py
│   ├── football_api.py
│   ├── scoring.py
│   └── time_utils.py
└── database/
    ├── db.py
    └── models.py
```

## Bot commands

Add the bot to a Telegram group, then use:

```text
/register      ثبت‌نام در گروه
/matches       انتخاب بازی و ثبت پیش‌بینی
/leaderboard   جدول رتبه‌بندی همان گروه
/myreport      گزارش شخصی کاربر در همان گروه
/matchreport   گزارش بازی‌های تمام‌شده
/help          راهنما
```

## Database setup on Ubuntu/Debian

Install MySQL and create a database/user:

```bash
sudo apt update
sudo apt install -y mysql-server python3.10 python3.10-venv
sudo mysql
```

Inside the MySQL shell:

```sql
CREATE DATABASE worldcup_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'bot_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON worldcup_bot.* TO 'bot_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

The app creates tables automatically on startup via SQLAlchemy `create_all()`. For a bigger deployment, replace that with Alembic migrations later.

## Installation

```bash
git clone <your-repo-url> worldcup_predictions_bot
cd worldcup_predictions_bot
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set these required values:

```dotenv
TELEGRAM_BOT_TOKEN=123456:replace-me
FOOTBALL_DATA_TOKEN=replace-me
MYSQL_URL=mysql+asyncmy://bot_user:strong_password@127.0.0.1:3306/worldcup_bot?charset=utf8mb4
```

`MYSQL_URL` may also start with `mysql://`; `config.py` will convert it to `mysql+asyncmy://` automatically.

## Run locally

```bash
source .venv/bin/activate
python main.py
```

The bot starts long-polling and also starts these background asyncio loops:

- match sync loop: fetches/caches World Cup matches
- scoring loop: locks predictions at kickoff and calculates points after final score
- reminder loop: sends 24h, 3h, and 30m reminders to registered users who have not predicted

## Run with systemd

Create a service file:

```bash
sudo nano /etc/systemd/system/worldcup-bot.service
```

Paste and adjust paths/user:

```ini
[Unit]
Description=Persian World Cup Prediction Telegram Bot
After=network-online.target mysql.service
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/worldcup_predictions_bot
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/ubuntu/worldcup_predictions_bot/.venv/bin/python /home/ubuntu/worldcup_predictions_bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable worldcup-bot
sudo systemctl start worldcup-bot
sudo journalctl -u worldcup-bot -f
```

## Run with pm2

```bash
npm install -g pm2
pm2 start .venv/bin/python --name worldcup-bot -- main.py
pm2 save
pm2 logs worldcup-bot
```

## Configuration knobs

Optional `.env` values:

```dotenv
BOT_TIMEZONE=Asia/Tehran
FOOTBALL_COMPETITION_CODE=WC
UPCOMING_MATCHES_LIMIT=5
FOOTBALL_API_CACHE_TTL_SECONDS=600
MATCH_SYNC_INTERVAL_SECONDS=1800
SCORING_INTERVAL_SECONDS=60
REMINDER_INTERVAL_SECONDS=300
REMINDER_WINDOW_SECONDS=600
EXACT_SCORE_POINTS=3
OUTCOME_POINTS=1
WRONG_POINTS=0
DEBUG_SQL=false
```

Scoring is centralized in `services/scoring.py` and uses the `.env` values above.

## Notes for Telegram groups

- The bot is designed for groups/supergroups.
- Every group is isolated by `chat_id`.
- Users are considered “registered” after `/register` or using a command like `/matches`.
- Reminders tag only active registered users in that specific group who have not predicted that match.

## football-data.org notes

The bot calls:

```text
GET /v4/competitions/WC/matches
Header: X-Auth-Token: <FOOTBALL_DATA_TOKEN>
```

The API is cached in memory and match data is cached in MySQL, so small groups should stay well below normal rate limits. Availability of World Cup data can depend on your football-data.org plan and the active competition season.
