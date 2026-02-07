from sqlalchemy import select, func, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from database.models import (
    Collection, collection_movies, Movie, Referral,
    MovieRequest, Advertisement, DailyMovie, User,
)


class CollectionRepository:

    @staticmethod
    async def create(session: AsyncSession, name: str, description: str = None, emoji: str = "🎬") -> Collection:
        col = Collection(name=name, description=description, emoji=emoji)
        session.add(col)
        await session.commit()
        await session.refresh(col)
        return col

    @staticmethod
    async def get_all(session: AsyncSession) -> List[Collection]:
        result = await session.execute(
            select(Collection).where(Collection.is_active == True).order_by(Collection.name)
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, col_id: int) -> Optional[Collection]:
        result = await session.execute(select(Collection).where(Collection.id == col_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_movies(session: AsyncSession, col_id: int) -> List[Movie]:
        result = await session.execute(
            select(Movie)
            .join(collection_movies)
            .where(collection_movies.c.collection_id == col_id, Movie.is_active == True)
            .order_by(collection_movies.c.position)
        )
        return result.scalars().all()

    @staticmethod
    async def add_movie(session: AsyncSession, col_id: int, movie_id: int, position: int = 0):
        await session.execute(
            collection_movies.insert().values(
                collection_id=col_id, movie_id=movie_id, position=position
            )
        )
        await session.commit()

    @staticmethod
    async def remove_movie(session: AsyncSession, col_id: int, movie_id: int):
        await session.execute(
            delete(collection_movies).where(
                collection_movies.c.collection_id == col_id,
                collection_movies.c.movie_id == movie_id,
            )
        )
        await session.commit()

    @staticmethod
    async def delete_collection(session: AsyncSession, col_id: int):
        await session.execute(delete(Collection).where(Collection.id == col_id))
        await session.commit()


class ReferralRepository:

    @staticmethod
    async def create(session: AsyncSession, referrer_id: int, referred_id: int) -> bool:
        try:
            ref = Referral(referrer_id=referrer_id, referred_id=referred_id)
            session.add(ref)
            await session.commit()
            return True
        except Exception:
            await session.rollback()
            return False

    @staticmethod
    async def get_count(session: AsyncSession, referrer_id: int) -> int:
        result = await session.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == referrer_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_top_referrers(session: AsyncSession, limit: int = 10) -> List:
        result = await session.execute(
            select(
                Referral.referrer_id,
                func.count(Referral.id).label("cnt"),
            )
            .group_by(Referral.referrer_id)
            .order_by(desc("cnt"))
            .limit(limit)
        )
        return result.all()

    @staticmethod
    async def is_referred(session: AsyncSession, user_id: int) -> bool:
        result = await session.execute(
            select(func.count(Referral.id)).where(Referral.referred_id == user_id)
        )
        return (result.scalar() or 0) > 0


class MovieRequestRepository:

    @staticmethod
    async def create(session: AsyncSession, user_id: int, text: str) -> MovieRequest:
        req = MovieRequest(user_id=user_id, request_text=text)
        session.add(req)
        await session.commit()
        await session.refresh(req)
        return req

    @staticmethod
    async def get_pending(session: AsyncSession, limit: int = 20) -> List[MovieRequest]:
        result = await session.execute(
            select(MovieRequest)
            .where(MovieRequest.status == "pending")
            .order_by(desc(MovieRequest.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def reply(session: AsyncSession, req_id: int, reply_text: str, status: str = "replied"):
        await session.execute(
            update(MovieRequest).where(MovieRequest.id == req_id).values(
                admin_reply=reply_text, status=status
            )
        )
        await session.commit()

    @staticmethod
    async def get_by_id(session: AsyncSession, req_id: int) -> Optional[MovieRequest]:
        result = await session.execute(select(MovieRequest).where(MovieRequest.id == req_id))
        return result.scalar_one_or_none()


class AdvertisementRepository:

    @staticmethod
    async def get_active(session: AsyncSession) -> Optional[Advertisement]:
        result = await session.execute(
            select(Advertisement).where(Advertisement.is_active == True).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, **kwargs) -> Advertisement:
        ad = Advertisement(**kwargs)
        session.add(ad)
        await session.commit()
        await session.refresh(ad)
        return ad

    @staticmethod
    async def increment_view(session: AsyncSession, ad_id: int):
        await session.execute(
            update(Advertisement).where(Advertisement.id == ad_id).values(
                view_count=Advertisement.view_count + 1
            )
        )
        await session.commit()

    @staticmethod
    async def deactivate_all(session: AsyncSession):
        await session.execute(
            update(Advertisement).values(is_active=False)
        )
        await session.commit()

    @staticmethod
    async def get_all(session: AsyncSession) -> List[Advertisement]:
        result = await session.execute(select(Advertisement).order_by(desc(Advertisement.created_at)))
        return result.scalars().all()


class DailyMovieRepository:

    @staticmethod
    async def set_today(session: AsyncSession, movie_id: int):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        existing = await session.execute(
            select(DailyMovie).where(DailyMovie.date == today)
        )
        dm = existing.scalar_one_or_none()
        if dm:
            dm.movie_id = movie_id
        else:
            session.add(DailyMovie(movie_id=movie_id, date=today))
        await session.commit()

    @staticmethod
    async def get_today(session: AsyncSession) -> Optional[int]:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(DailyMovie.movie_id).where(DailyMovie.date == today)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def auto_set(session: AsyncSession) -> Optional[int]:
        """Avtomatik kunlik kino tanlash."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        existing = await session.execute(
            select(DailyMovie).where(DailyMovie.date == today)
        )
        if existing.scalar_one_or_none():
            return None

        # Oxirgi 30 kunda tanlanmaganlardan random
        recent_ids = await session.execute(
            select(DailyMovie.movie_id).where(
                DailyMovie.date >= today - timedelta(days=30)
            )
        )
        exclude = [r[0] for r in recent_ids.all()]

        from database.models import Movie
        q = select(Movie.id).where(Movie.is_active == True)
        if exclude:
            q = q.where(Movie.id.notin_(exclude))
        q = q.order_by(func.random()).limit(1)

        result = await session.execute(q)
        movie_id = result.scalar_one_or_none()

        if movie_id:
            session.add(DailyMovie(movie_id=movie_id, date=today))
            await session.commit()
            return movie_id
        return None


class LeaderboardRepository:

    @staticmethod
    async def get_top_watchers(session: AsyncSession, limit: int = 10) -> List:
        result = await session.execute(
            select(
                User.telegram_id,
                User.full_name,
                User.username,
                User.movies_watched,
            )
            .where(User.is_banned == False)
            .order_by(desc(User.movies_watched))
            .limit(limit)
        )
        return result.all()

    @staticmethod
    async def get_top_searchers(session: AsyncSession, limit: int = 10) -> List:
        result = await session.execute(
            select(
                User.telegram_id,
                User.full_name,
                User.username,
                User.search_count,
            )
            .where(User.is_banned == False)
            .order_by(desc(User.search_count))
            .limit(limit)
        )
        return result.all()