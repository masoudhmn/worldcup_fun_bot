from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Chat, User as TelegramUser

from database.models import Group, GroupUser, User
from services.time_utils import utc_now

GROUP_TYPES = {"group", "supergroup"}


def is_group_chat(chat: Chat | None) -> bool:
    return bool(chat and chat.type in GROUP_TYPES)


async def ensure_group_user(session: AsyncSession, chat: Chat, telegram_user: TelegramUser) -> tuple[Group, User, GroupUser]:
    group = await session.scalar(select(Group).where(Group.chat_id == chat.id))
    if group is None:
        group = Group(chat_id=chat.id, title=chat.title)
        session.add(group)
        await session.flush()
    elif group.title != chat.title:
        group.title = chat.title

    user = await session.scalar(select(User).where(User.user_id == telegram_user.id))
    if user is None:
        user = User(user_id=telegram_user.id, username=telegram_user.username, first_name=telegram_user.first_name)
        session.add(user)
        await session.flush()
    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name

    group_user = await session.scalar(
        select(GroupUser).where(GroupUser.group_id == group.id, GroupUser.user_id == user.id)
    )
    if group_user is None:
        group_user = GroupUser(group_id=group.id, user_id=user.id, is_active=True, last_seen_at=utc_now())
        session.add(group_user)
        await session.flush()
    else:
        group_user.is_active = True
        group_user.last_seen_at = utc_now()

    return group, user, group_user


async def get_group_by_chat(session: AsyncSession, chat: Chat) -> Group | None:
    return await session.scalar(select(Group).where(Group.chat_id == chat.id))
