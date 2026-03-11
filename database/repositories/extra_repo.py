from sqlalchemy import select, func, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from database.models import (
    Collection, collection_movies, Movie, Referral,
    MovieRequest, Advertisement, DailyMovie, User,
    WatchHistory, Review, SerialProgress, AdminLog, Serial,
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


class WatchHistoryRepository:

    @staticmethod
    async def add(session: AsyncSession, user_id: int, movie_id: int = None,
                  serial_id: int = None, season: int = None, episode_num: int = None):
        entry = WatchHistory(
            user_id=user_id, movie_id=movie_id,
            serial_id=serial_id, season=season, episode_num=episode_num,
        )
        session.add(entry)
        await session.commit()

    @staticmethod
    async def get_history(session: AsyncSession, user_id: int, limit: int = 10, offset: int = 0) -> Tuple[list, int]:
        from sqlalchemy.orm import selectinload
        count_q = select(func.count(WatchHistory.id)).where(WatchHistory.user_id == user_id)
        total = (await session.execute(count_q)).scalar() or 0

        result = await session.execute(
            select(WatchHistory)
            .where(WatchHistory.user_id == user_id)
            .order_by(desc(WatchHistory.watched_at))
            .limit(limit).offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def get_movie_history(session: AsyncSession, user_id: int, limit: int = 10) -> List[Movie]:
        """Foydalanuvchi ko'rgan kinolar ro'yxati (unique, oxirgilari birinchi)."""
        from sqlalchemy import distinct
        subq = (
            select(WatchHistory.movie_id, func.max(WatchHistory.watched_at).label("last"))
            .where(WatchHistory.user_id == user_id, WatchHistory.movie_id.isnot(None))
            .group_by(WatchHistory.movie_id)
            .order_by(desc("last"))
            .limit(limit)
            .subquery()
        )
        result = await session.execute(
            select(Movie).join(subq, Movie.id == subq.c.movie_id)
            .where(Movie.is_active == True)
            .order_by(desc(subq.c.last))
        )
        return result.scalars().all()


class ReviewRepository:

    @staticmethod
    async def add_or_update(session: AsyncSession, user_id: int, movie_id: int, text: str) -> Review:
        existing = await session.execute(
            select(Review).where(Review.user_id == user_id, Review.movie_id == movie_id)
        )
        review = existing.scalar_one_or_none()
        if review:
            review.text = text
            review.created_at = datetime.utcnow()
        else:
            review = Review(user_id=user_id, movie_id=movie_id, text=text)
            session.add(review)
        await session.commit()
        return review

    @staticmethod
    async def get_for_movie(session: AsyncSession, movie_id: int, limit: int = 5) -> List[Review]:
        result = await session.execute(
            select(Review)
            .where(Review.movie_id == movie_id)
            .order_by(desc(Review.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_count(session: AsyncSession, movie_id: int) -> int:
        result = await session.execute(
            select(func.count(Review.id)).where(Review.movie_id == movie_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_user_review(session: AsyncSession, user_id: int, movie_id: int) -> Optional[Review]:
        result = await session.execute(
            select(Review).where(Review.user_id == user_id, Review.movie_id == movie_id)
        )
        return result.scalar_one_or_none()


class SerialProgressRepository:

    @staticmethod
    async def save(session: AsyncSession, user_id: int, serial_id: int, season: int, episode: int):
        existing = await session.execute(
            select(SerialProgress).where(
                SerialProgress.user_id == user_id,
                SerialProgress.serial_id == serial_id,
            )
        )
        prog = existing.scalar_one_or_none()
        if prog:
            prog.last_season = season
            prog.last_episode = episode
            prog.updated_at = datetime.utcnow()
        else:
            prog = SerialProgress(
                user_id=user_id, serial_id=serial_id,
                last_season=season, last_episode=episode,
            )
            session.add(prog)
        await session.commit()

    @staticmethod
    async def get(session: AsyncSession, user_id: int, serial_id: int) -> Optional[SerialProgress]:
        result = await session.execute(
            select(SerialProgress).where(
                SerialProgress.user_id == user_id,
                SerialProgress.serial_id == serial_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_for_user(session: AsyncSession, user_id: int) -> List:
        result = await session.execute(
            select(SerialProgress, Serial)
            .join(Serial, Serial.id == SerialProgress.serial_id)
            .where(SerialProgress.user_id == user_id)
            .order_by(desc(SerialProgress.updated_at))
        )
        return result.all()


class AdminLogRepository:

    @staticmethod
    async def log(session: AsyncSession, admin_id: int, action: str, detail: str = None):
        entry = AdminLog(admin_id=admin_id, action=action, detail=detail)
        session.add(entry)
        await session.commit()

    @staticmethod
    async def get_recent(session: AsyncSession, limit: int = 20) -> List[AdminLog]:
        result = await session.execute(
            select(AdminLog)
            .order_by(desc(AdminLog.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_admin(session: AsyncSession, admin_id: int, limit: int = 20) -> List[AdminLog]:
        result = await session.execute(
            select(AdminLog)
            .where(AdminLog.admin_id == admin_id)
            .order_by(desc(AdminLog.created_at))
            .limit(limit)
        )
        return result.scalars().all()