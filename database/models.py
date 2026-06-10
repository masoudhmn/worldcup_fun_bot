from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Group(Base, TimestampMixin):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    members: Mapped[list["GroupUser"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    groups: Mapped[list["GroupUser"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class GroupUser(Base, TimestampMixin):
    __tablename__ = "group_users"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_user"),
        Index("ix_group_users_group_active", "group_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    group: Mapped[Group] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="groups")


class Match(Base, TimestampMixin):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_status_kickoff", "status", "kickoff_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    home_team: Mapped[str] = mapped_column(String(255), nullable=False)
    away_team: Mapped[str] = mapped_column(String(255), nullable=False)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="SCHEDULED")
    home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="match", cascade="all, delete-orphan")


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "match_id", name="uq_prediction_group_user_match"),
        Index("ix_predictions_group_match", "group_id", "match_id"),
        Index("ix_predictions_points", "group_id", "points"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    predicted_home: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_away: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    group: Mapped[Group] = relationship(back_populates="predictions")
    user: Mapped[User] = relationship(back_populates="predictions")
    match: Mapped[Match] = relationship(back_populates="predictions")


class ReminderLog(Base, TimestampMixin):
    """Prevents duplicate reminder messages per group/match/reminder window."""

    __tablename__ = "reminder_logs"
    __table_args__ = (
        UniqueConstraint("group_id", "match_id", "reminder_key", name="uq_reminder_group_match_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    reminder_key: Mapped[str] = mapped_column(String(20), nullable=False)
