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

    @staticmethod
    async def get_random(session: AsyncSession) -> Optional[Movie]:
        """Get a random active movie."""
        result = await session.execute(
            select(Movie)
            .where(Movie.is_active == True)
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_similar(session: AsyncSession, movie: Movie, limit: int = 5) -> List[Movie]:
        """Get similar movies by genre or year."""
        genre_ids = [g.id for g in movie.genres] if movie.genres else []

        if genre_ids:
            result = await session.execute(
                select(Movie)
                .join(movie_genres)
                .where(
                    movie_genres.c.genre_id.in_(genre_ids),
                    Movie.id != movie.id,
                    Movie.is_active == True,
                )
                .group_by(Movie.id)
                .order_by(desc(Movie.view_count))
                .limit(limit)
            )
            movies = result.scalars().all()
            if movies:
                return movies

        # Fallback: same year or popular
        if movie.year:
            result = await session.execute(
                select(Movie)
                .where(
                    Movie.year == movie.year,
                    Movie.id != movie.id,
                    Movie.is_active == True,
                )
                .order_by(desc(Movie.view_count))
                .limit(limit)
            )
            movies = result.scalars().all()
            if movies:
                return movies

        # Fallback: just popular
        result = await session.execute(
            select(Movie)
            .where(Movie.id != movie.id, Movie.is_active == True)
            .order_by(desc(Movie.view_count))
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def search_similar_names(session: AsyncSession, query: str, limit: int = 5) -> List[Movie]:
        """Fuzzy search — shorter query parts."""
        words = query.strip().split()
        if not words:
            return []

        conditions = []
        for word in words:
            if len(word) >= 2:
                conditions.append(Movie.title.ilike(f"%{word}%"))
                conditions.append(Movie.title_uz.ilike(f"%{word}%"))
                conditions.append(Movie.title_ru.ilike(f"%{word}%"))

        if not conditions:
            return []

        result = await session.execute(
            select(Movie)
            .where(or_(*conditions), Movie.is_active == True)
            .order_by(desc(Movie.view_count))
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_language(
            session: AsyncSession, lang_keyword: str, limit: int = 10, offset: int = 0
    ) -> Tuple[List[Movie], int]:
        search = f"%{lang_keyword}%"
        count_q = select(func.count(Movie.id)).where(
            or_(Movie.language.ilike(search), Movie.caption.ilike(search)),
            Movie.is_active == True,
        )
        total = (await session.execute(count_q)).scalar() or 0

        result = await session.execute(
            select(Movie)
            .where(
                or_(Movie.language.ilike(search), Movie.caption.ilike(search)),
                Movie.is_active == True,
            )
            .order_by(desc(Movie.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def get_avg_rating(session: AsyncSession, movie_id: int) -> Tuple[float, int]:
        """Get average rating and count for a movie."""
        from database.models import Rating
        result = await session.execute(
            select(
                func.avg(Rating.score),
                func.count(Rating.id),
            ).where(Rating.movie_id == movie_id)
        )
        row = result.one()
        avg = float(row[0]) if row[0] else 0.0
        count = row[1] or 0
        return round(avg, 1), count

    @staticmethod
    async def rate_movie(session: AsyncSession, user_id: int, movie_id: int, score: int) -> bool:
        """Rate a movie (1-5). Updates if already rated."""
        from database.models import Rating
        existing = await session.execute(
            select(Rating).where(Rating.user_id == user_id, Rating.movie_id == movie_id)
        )
        rating = existing.scalar_one_or_none()

        if rating:
            rating.score = score
        else:
            session.add(Rating(user_id=user_id, movie_id=movie_id, score=score))

        await session.commit()
        return True
