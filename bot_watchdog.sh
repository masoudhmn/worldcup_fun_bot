#!/bin/bash

APP_DIR="/home/worldcup/worldcup_bot/worldcup_fun_bot"
PYTHON="/home/worldcup/virtualenv/worldcup_bot/3.12/bin/python"
MAIN_FILE="$APP_DIR/main.py"

RUN_DIR="$APP_DIR/.run"
LOG_DIR="$APP_DIR/logs"

PID_FILE="$RUN_DIR/bot.pid"
DISABLE_FILE="$RUN_DIR/disabled"
LOCK_DIR="$RUN_DIR/watchdog.lock"

BOT_LOG="$LOG_DIR/bot.log"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"

mkdir -p "$RUN_DIR" "$LOG_DIR"

# اگر ربات عمداً غیرفعال شده باشد، آن را اجرا نکن
if [ -f "$DISABLE_FILE" ]; then
    exit 0
fi

# جلوگیری از اجرای هم‌زمان چند Watchdog
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    exit 0
fi

cleanup_lock() {
    rmdir "$LOCK_DIR" 2>/dev/null
}

trap cleanup_lock EXIT INT TERM

cd "$APP_DIR" || {
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Cannot enter $APP_DIR" >> "$WATCHDOG_LOG"
    exit 1
}

# بررسی پردازش ثبت‌شده در PID file
if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null)"

    if echo "$PID" | grep -Eq '^[0-9]+$' && kill -0 "$PID" 2>/dev/null; then
        PROCESS_COMMAND="$(ps -p "$PID" -o args= 2>/dev/null)"

        if echo "$PROCESS_COMMAND" | grep -Fq "$MAIN_FILE"; then
            # ربات در حال اجراست
            exit 0
        fi
    fi

    # PID قدیمی یا نامعتبر
    rm -f "$PID_FILE"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Bot is not running; starting..." >> "$WATCHDOG_LOG"

PYTHONUNBUFFERED=1 nohup "$PYTHON" -u "$MAIN_FILE" \
    >> "$BOT_LOG" 2>&1 < /dev/null &

NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

sleep 3

if kill -0 "$NEW_PID" 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Bot started successfully; PID=$NEW_PID" >> "$WATCHDOG_LOG"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Bot failed to start; PID=$NEW_PID" >> "$WATCHDOG_LOG"
    rm -f "$PID_FILE"
    exit 1
fi
