from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from config import settings
from services.time_utils import as_utc

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa_digits(value: object) -> str:
    return str(value).translate(FA_DIGITS)


def normalize_digits(value: str) -> str:
    return value.translate(EN_DIGITS)


def h(value: object) -> str:
    return escape(str(value or ""), quote=False)


def format_dt(dt: datetime, tz: ZoneInfo | None = None) -> str:
    local = as_utc(dt).astimezone(tz or settings.tzinfo)
    return fa_digits(local.strftime("%Y/%m/%d ساعت %H:%M"))


def mention(username: str | None, first_name: str | None, telegram_user_id: int | None = None) -> str:
    if username:
        return f"@{h(username)}"
    name = h(first_name or "کارشناس بی‌نام")
    if telegram_user_id:
        return f'<a href="tg://user?id={telegram_user_id}">{name}</a>'
    return name


PRIVATE_ONLY_GROUPS = "من برای کری‌خونی گروهی ساخته شدم رفیق 😄 منو ببر توی گروه، اونجا غوغا می‌کنیم ⚽️"
REGISTERED = "باریکلام! چه پسرچی خوبی ⚽️"
HELP = """⚽️ <b>راهنمای ربات پیش‌بینی جام جهانی</b>

/register — ثبت‌نام در همین گروه
/matches — دیدن بازی‌های بعدی و ثبت پیش‌بینی
/leaderboard — جدول بزرگان و مدعیان
/myreport — کارنامه شخصی خودت
/matchreport — گزارش بازی‌های تمام‌شده

قانون امتیازدهی:
🎯 نتیجه دقیق: {exact} امتیاز
✅ برنده/مساوی درست: {outcome} امتیاز
🥔 اشتباه: {wrong} امتیاز

نکته: با شروع بازی، دفترچه پیش‌بینی بسته می‌شه پس تاخ باش
""".format(exact=fa_digits(settings.exact_score_points), outcome=fa_digits(settings.outcome_points), wrong=fa_digits(settings.wrong_points))

NO_UPCOMING_MATCHES = "فعلاً بازی قابل پیش‌بینی توی کش نیست. یا جام جهانی خوابیده، یا API قهر کرده 😅 چند دقیقه دیگه دوباره /matches بزن."
NO_FINISHED_MATCHES = "هنوز بازی تمام‌شده‌ای نداریم که گزارشش رو دربیارم. صبر کن سوت پایان بخوره حاجی 🕰️"
CHOOSE_MATCH = "یکی از بازی‌ها رو انتخاب کن ببینیم مغز فوتبالی‌ات چی می‌گه 🧠⚽️"
CHOOSE_OUTCOME = "برای بازی <b>{home}</b> - <b>{away}</b> اول بگو تهش چی می‌شه؟"
ASK_EXACT_SCORE = "حالا نتیجه دقیق رو بفرست؛ مثلاً <code>۲-۱</code>. فشار نیار، فقط عدد و خط تیره 😄"
INVALID_SCORE = "این شبیه نتیجه فوتبال نیست رفیق 😅 مثل <code>۲-۱</code> بفرست."
SCORE_OUTCOME_MISMATCH = "خودت گفتی <b>{outcome}</b> ولی این نتیجه یه چیز دیگه‌ست! یه نتیجه هماهنگ بفرست، مربی گیج شد 😵‍💫"
PREDICTION_SAVED = "ثبت شد گلی چی! <b>{home}</b> {ph}-{pa} <b>{away}</b> ⚽️ جوندابرم"
PREDICTION_UPDATED = "آپدیت شد پسرحجی! پیش‌بینی جدیدت: <b>{home}</b> {ph}-{pa} <b>{away}</b> 🔁"
MATCH_LOCKED = "دیر رسیدی مهندس! بازی شروع شده، سوت رو زدن 🚫"
MATCH_NOT_FOUND = "این بازی رو پیدا نکردم. انگار توپ رفته پشت بوم 🏟️"
NO_PENDING_PREDICTION = "اول با /matches یه بازی انتخاب کن، بعد نتیجه رو بفرست. نظم داشته باش کاپیتان 😄"
REPORT_CHOOSE_MATCH = "کدوم بازی رو کالبدشکافی کنیم؟ 🔍⚽️"
NOT_REGISTERED = "اول /register بزن تا اسمت وارد رختکن بشه 😄"
NO_STATS = "هنوز آماری نداری. برو /matches بزن، از روی نیمکت بلند شو 😄"
EMPTY_LEADERBOARD = "هنوز کسی امتیاز نگرفته. همه در حد کارشناسی قبل بازی هستن فعلاً 😅"
API_SYNC_FAILED = "فعلاً نتونستم بازی‌ها رو از API بگیرم. اینترنت یا API ادا درآورده 😬 چند دقیقه دیگه امتحان کن."

OUTCOME_HOME = "برد {team}"
OUTCOME_AWAY = "برد {team}"
OUTCOME_DRAW = "مساوی"

OUTCOME_LABELS = {
    "HOME": "برد میزبان",
    "AWAY": "برد مهمان",
    "DRAW": "مساوی",
}

REMINDER_TEXT = """⏰ <b>یادآوری {label} تا بازی</b>
<b>{home}</b> - <b>{away}</b>
شروع: {kickoff}

یعنی یه پیش بینی نمخواید بوکونید:
{mentions}

/matches بزنید رو ای دکمه چی 😄⚽️"""

FUNNY_TITLES = [
    "👑 نوستراداموس گروه",
    "🧠 کمک‌مربی مخفی",
    "🥉 سلطان VAR خانگی",
    "📋 آنالیزور مبل‌نشین",
    "🥁 لیدر سکوها",
    "⚽️ توپ‌جمع‌کن افتخاری",
]
