from sqlalchemy import select, func, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from database.models import User, user_favorites, Movie


class UserRepository:

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        telegram_id: int,
        username: str = None,
        full_name: str = None,
    ) -> Tuple[User, bool]:
        """Get existing user or create new. Returns (user, is_new)."""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Update last active and info
            user.last_active = datetime.utcnow()
            if username:
                user.username = username
            if full_name:
                user.full_name = full_name
            await session.commit()
            return user, False

        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user, True

    @staticmethod
    async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def ban_user(session: AsyncSession, telegram_id: int) -> bool:
        result = await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(is_banned=True)
        )
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def unban_user(session: AsyncSession, telegram_id: int) -> bool:
        result = await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(is_banned=False)
        )
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def is_banned(session: AsyncSession, telegram_id: int) -> bool:
        result = await session.execute(
            select(User.is_banned).where(User.telegram_id == telegram_id)
        )
        val = result.scalar_one_or_none()
        return val is True

    @staticmethod
    async def get_total_count(session: AsyncSession) -> int:
        result = await session.execute(select(func.count(User.id)))
        return result.scalar() or 0

    @staticmethod
    async def get_active_count(session: AsyncSession, days: int = 7) -> int:
        since = datetime.utcnow() - timedelta(days=days)
        result = await session.execute(
            select(func.count(User.id)).where(User.last_active >= since)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_today_count(session: AsyncSession) -> int:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(User.id)).where(User.joined_at >= today)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_all_user_ids(session: AsyncSession, active_only: bool = True) -> List[int]:
        """Get all user telegram IDs for broadcast."""
        q = select(User.telegram_id).where(User.is_banned == False)
        if active_only:
            since = datetime.utcnow() - timedelta(days=30)
            q = q.where(User.last_active >= since)
        result = await session.execute(q)
        return [row[0] for row in result.all()]

    @staticmethod
    async def get_all_user_ids_no_filter(session: AsyncSession) -> List[int]:
        result = await session.execute(
            select(User.telegram_id).where(User.is_banned == False)
        )
        return [row[0] for row in result.all()]

    @staticmethod
    async def increment_search(session: AsyncSession, telegram_id: int):
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(
                search_count=User.search_count + 1
            )
        )
        await session.commit()

    @staticmethod
    async def increment_watched(session: AsyncSession, telegram_id: int):
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(
                movies_watched=User.movies_watched + 1
            )
        )
        await session.commit()

    # ---- Favorites ----
    @staticmethod
    async def add_favorite(session: AsyncSession, user_id: int, movie_id: int) -> bool:
        try:
            await session.execute(
                user_favorites.insert().values(user_id=user_id, movie_id=movie_id)
            )
            await session.commit()
            return True
        except Exception:
            await session.rollback()
            return False

    @staticmethod
    async def remove_favorite(session: AsyncSession, user_id: int, movie_id: int) -> bool:
        result = await session.execute(
            delete(user_favorites).where(
                user_favorites.c.user_id == user_id,
                user_favorites.c.movie_id == movie_id,
            )
        )
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def is_favorite(session: AsyncSession, user_id: int, movie_id: int) -> bool:
        result = await session.execute(
            select(func.count()).where(
                user_favorites.c.user_id == user_id,
                user_favorites.c.movie_id == movie_id,
            )
        )
        return (result.scalar() or 0) > 0

    @staticmethod
    async def get_favorites(
        session: AsyncSession, user_id: int, limit: int = 10, offset: int = 0
    ) -> Tuple[List[Movie], int]:
        count_q = select(func.count()).where(user_favorites.c.user_id == user_id)
        total = (await session.execute(count_q)).scalar() or 0

        result = await session.execute(
            select(Movie)
            .join(user_favorites, user_favorites.c.movie_id == Movie.id)
            .where(user_favorites.c.user_id == user_id, Movie.is_active == True)
            .order_by(desc(Movie.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def get_users_paginated(
        session: AsyncSession, limit: int = 20, offset: int = 0
    ) -> Tuple[List[User], int]:
        total = (await session.execute(select(func.count(User.id)))).scalar() or 0
        result = await session.execute(
            select(User).order_by(desc(User.joined_at)).limit(limit).offset(offset)
        )
        return result.scalars().all(), total
