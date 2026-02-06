from sqlalchemy import select, func, update, delete, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple
from datetime import datetime

from database.models import Movie, Genre, movie_genres, Statistic


class MovieRepository:

    @staticmethod
    async def get_by_code(session: AsyncSession, code: int) -> Optional[Movie]:
        """Get movie by its code."""
        result = await session.execute(
            select(Movie)
            .options(selectinload(Movie.genres))
            .where(Movie.code == code, Movie.is_active == True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, movie_id: int) -> Optional[Movie]:
        result = await session.execute(
            select(Movie)
            .options(selectinload(Movie.genres))
            .where(Movie.id == movie_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_file_unique_id(session: AsyncSession, file_unique_id: str) -> Optional[Movie]:
        result = await session.execute(
            select(Movie).where(Movie.file_unique_id == file_unique_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def search_by_title(
        session: AsyncSession, query: str, limit: int = 10, offset: int = 0
    ) -> Tuple[List[Movie], int]:
        """Search movies by title (uz, ru, original)."""
        search_filter = or_(
            Movie.title.ilike(f"%{query}%"),
            Movie.title_uz.ilike(f"%{query}%"),
            Movie.title_ru.ilike(f"%{query}%"),
        )

        # Count
        count_q = select(func.count(Movie.id)).where(search_filter, Movie.is_active == True)
        total = (await session.execute(count_q)).scalar() or 0

        # Results
        result = await session.execute(
            select(Movie)
            .options(selectinload(Movie.genres))
            .where(search_filter, Movie.is_active == True)
            .order_by(desc(Movie.view_count), desc(Movie.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def get_by_genre(
        session: AsyncSession, genre_id: int, limit: int = 10, offset: int = 0
    ) -> Tuple[List[Movie], int]:
        count_q = (
            select(func.count(Movie.id))
            .join(movie_genres)
            .where(movie_genres.c.genre_id == genre_id, Movie.is_active == True)
        )
        total = (await session.execute(count_q)).scalar() or 0

        result = await session.execute(
            select(Movie)
            .join(movie_genres)
            .where(movie_genres.c.genre_id == genre_id, Movie.is_active == True)
            .order_by(desc(Movie.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def get_by_year(
        session: AsyncSession, year: int, limit: int = 10, offset: int = 0
    ) -> Tuple[List[Movie], int]:
        count_q = select(func.count(Movie.id)).where(Movie.year == year, Movie.is_active == True)
        total = (await session.execute(count_q)).scalar() or 0

        result = await session.execute(
            select(Movie)
            .where(Movie.year == year, Movie.is_active == True)
            .order_by(desc(Movie.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def get_popular(session: AsyncSession, limit: int = 10, offset: int = 0) -> List[Movie]:
        result = await session.execute(
            select(Movie)
            .where(Movie.is_active == True)
            .order_by(desc(Movie.view_count))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    @staticmethod
    async def get_latest(session: AsyncSession, limit: int = 10, offset: int = 0) -> List[Movie]:
        result = await session.execute(
            select(Movie)
            .where(Movie.is_active == True)
            .order_by(desc(Movie.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    @staticmethod
    async def create(session: AsyncSession, **kwargs) -> Movie:
        movie = Movie(**kwargs)
        session.add(movie)
        await session.commit()
        await session.refresh(movie)
        return movie

    @staticmethod
    async def bulk_create(session: AsyncSession, movies_data: List[dict]) -> Tuple[int, int]:
        """Bulk create movies. Returns (success_count, fail_count)."""
        success = 0
        fail = 0
        for data in movies_data:
            try:
                movie = Movie(**data)
                session.add(movie)
                await session.flush()
                success += 1
            except Exception:
                await session.rollback()
                fail += 1
        if success > 0:
            await session.commit()
        return success, fail

    @staticmethod
    async def update_movie(session: AsyncSession, movie_id: int, **kwargs) -> Optional[Movie]:
        kwargs["updated_at"] = datetime.utcnow()
        await session.execute(
            update(Movie).where(Movie.id == movie_id).values(**kwargs)
        )
        await session.commit()
        return await MovieRepository.get_by_id(session, movie_id)

    @staticmethod
    async def delete_movie(session: AsyncSession, movie_id: int) -> bool:
        result = await session.execute(
            delete(Movie).where(Movie.id == movie_id)
        )
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def deactivate(session: AsyncSession, movie_id: int) -> bool:
        await session.execute(
            update(Movie).where(Movie.id == movie_id).values(is_active=False)
        )
        await session.commit()
        return True

    @staticmethod
    async def increment_view(session: AsyncSession, movie_id: int):
        await session.execute(
            update(Movie).where(Movie.id == movie_id).values(
                view_count=Movie.view_count + 1
            )
        )
        await session.commit()

    @staticmethod
    async def get_next_code(session: AsyncSession) -> int:
        result = await session.execute(
            select(func.max(Movie.code))
        )
        max_code = result.scalar()
        return (max_code or 0) + 1

    @staticmethod
    async def get_total_count(session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count(Movie.id)).where(Movie.is_active == True)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_all_movies(
        session: AsyncSession, limit: int = 50, offset: int = 0, active_only: bool = True
    ) -> Tuple[List[Movie], int]:
        where_clause = [Movie.is_active == True] if active_only else []
        count_q = select(func.count(Movie.id)).where(*where_clause)
        total = (await session.execute(count_q)).scalar() or 0

        result = await session.execute(
            select(Movie)
            .where(*where_clause)
            .order_by(desc(Movie.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def set_genres(session: AsyncSession, movie_id: int, genre_ids: List[int]):
        """Set genres for a movie (replace existing)."""
        # Remove existing
        await session.execute(
            delete(movie_genres).where(movie_genres.c.movie_id == movie_id)
        )
        # Add new
        for gid in genre_ids:
            await session.execute(
                movie_genres.insert().values(movie_id=movie_id, genre_id=gid)
            )
        await session.commit()
