from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.messages_fa import MATCH_NOT_FOUND, NO_FINISHED_MATCHES, fa_digits, format_dt, h, mention
from database.models import Group, GroupUser, Match, Prediction, User
from services.football_api import FINISHED_STATUSES
from services.scoring import calculate_prediction_points


async def build_match_report(session: AsyncSession, chat_id: int, match_id: int) -> str:
    group = await session.scalar(select(Group).where(Group.chat_id == chat_id))
    match = await session.get(Match, match_id)
    if group is None or match is None:
        return MATCH_NOT_FOUND
    if match.status not in FINISHED_STATUSES or match.home_score is None or match.away_score is None:
        return NO_FINISHED_MATCHES

    prediction_rows = (
        await session.execute(
            select(Prediction, User)
            .join(User, Prediction.user_id == User.id)
            .where(Prediction.group_id == group.id, Prediction.match_id == match.id)
            .order_by(Prediction.points.desc(), Prediction.updated_at.asc())
        )
    ).all()

    active_users = (
        await session.execute(
            select(User)
            .join(GroupUser, GroupUser.user_id == User.id)
            .where(GroupUser.group_id == group.id, GroupUser.is_active.is_(True))
        )
    ).scalars().all()

    predicted_user_ids = {prediction.user_id for prediction, _ in prediction_rows}
    missed_users = [user for user in active_users if user.id not in predicted_user_ids]

    lines = [
        "📊 <b>گزارش بازی</b>",
        f"<b>{h(match.home_team)}</b> {fa_digits(match.home_score)}-{fa_digits(match.away_score)} <b>{h(match.away_team)}</b>",
        f"شروع: {format_dt(match.kickoff_at)}",
        "",
        "🎯 <b>پیش‌بینی‌ها و امتیازها</b>",
    ]

    if not prediction_rows:
        lines.append("هیچ‌کس پیش‌بینی نکرده؛ سکوت مطلق روی نیمکت 😶")
    else:
        for prediction, user in prediction_rows:
            if prediction.points is None:
                prediction.points = calculate_prediction_points(
                    prediction.predicted_home,
                    prediction.predicted_away,
                    int(match.home_score),
                    int(match.away_score),
                )
            lines.append(
                f"• {mention(user.username, user.first_name, user.user_id)}: "
                f"{fa_digits(prediction.predicted_home)}-{fa_digits(prediction.predicted_away)} "
                f"→ <b>{fa_digits(prediction.points)}</b> امتیاز"
            )

    lines.extend(["", "🚫 <b>جا مونده‌ها</b>"])
    if missed_users:
        lines.extend(f"• {mention(user.username, user.first_name, user.user_id)}" for user in missed_users)
    else:
        lines.append("همه پیش‌بینی کردن؛ گروه منظم‌تر از خط دفاع ایتالیا 😄")

    return "\n".join(lines)
