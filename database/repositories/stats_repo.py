from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List, Dict

from database.models import Statistic, Movie, User


class StatsRepository:

    @staticmethod
    async def log_action(
        session: AsyncSession,
        action_type: str,
        user_id: int = None,
        movie_id: int = None,
        query_text: str = None,
    ):
        stat = Statistic(
            action_type=action_type,
            user_id=user_id,
            movie_id=movie_id,
            query_text=query_text,
        )
        session.add(stat)
        await session.commit()

    @staticmethod
    async def get_daily_stats(session: AsyncSession, days: int = 7) -> Dict:
        since = datetime.utcnow() - timedelta(days=days)

        # Views
        views = await session.execute(
            select(func.count(Statistic.id))
            .where(Statistic.action_type == "view", Statistic.created_at >= since)
        )
        # Searches
        searches = await session.execute(
            select(func.count(Statistic.id))
            .where(Statistic.action_type == "search", Statistic.created_at >= since)
        )
        # New users
        new_users = await session.execute(
            select(func.count(User.id)).where(User.joined_at >= since)
        )

        return {
            "views": views.scalar() or 0,
            "searches": searches.scalar() or 0,
            "new_users": new_users.scalar() or 0,
            "period_days": days,
        }

    @staticmethod
    async def get_top_movies(session: AsyncSession, limit: int = 10) -> List:
        result = await session.execute(
            select(
                Movie.code,
                Movie.title,
                Movie.view_count,
            )
            .where(Movie.is_active == True)
            .order_by(desc(Movie.view_count))
            .limit(limit)
        )
        return result.all()

    @staticmethod
    async def get_top_searches(session: AsyncSession, limit: int = 10) -> List:
        result = await session.execute(
            select(
                Statistic.query_text,
                func.count(Statistic.id).label("cnt"),
            )
            .where(
                Statistic.action_type == "search",
                Statistic.query_text.isnot(None),
            )
            .group_by(Statistic.query_text)
            .order_by(desc("cnt"))
            .limit(limit)
        )
        return result.all()

    @staticmethod
    async def get_overview(session: AsyncSession) -> Dict:
        total_movies = (await session.execute(
            select(func.count(Movie.id)).where(Movie.is_active == True)
        )).scalar() or 0

        total_users = (await session.execute(
            select(func.count(User.id))
        )).scalar() or 0

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_users = (await session.execute(
            select(func.count(User.id)).where(User.joined_at >= today)
        )).scalar() or 0

        today_views = (await session.execute(
            select(func.count(Statistic.id)).where(
                Statistic.action_type == "view",
                Statistic.created_at >= today,
            )
        )).scalar() or 0

        active_7d = (await session.execute(
            select(func.count(User.id)).where(
                User.last_active >= datetime.utcnow() - timedelta(days=7)
            )
        )).scalar() or 0

        return {
            "total_movies": total_movies,
            "total_users": total_users,
            "today_users": today_users,
            "today_views": today_views,
            "active_7d": active_7d,
        }
