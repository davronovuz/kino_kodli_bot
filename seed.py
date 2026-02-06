"""Seed database with default genres."""
import asyncio
from sqlalchemy import select
from database.engine import create_db, async_session
from database.models import Genre

DEFAULT_GENRES = [
    {"name_uz": "Jangari", "name_ru": "Боевик", "emoji": "💥"},
    {"name_uz": "Komediya", "name_ru": "Комедия", "emoji": "😂"},
    {"name_uz": "Drama", "name_ru": "Драма", "emoji": "🎭"},
    {"name_uz": "Fantastika", "name_ru": "Фантастика", "emoji": "🚀"},
    {"name_uz": "Qo'rqinchli", "name_ru": "Ужасы", "emoji": "👻"},
    {"name_uz": "Romantik", "name_ru": "Романтика", "emoji": "❤️"},
    {"name_uz": "Triller", "name_ru": "Триллер", "emoji": "😱"},
    {"name_uz": "Detektiv", "name_ru": "Детектив", "emoji": "🔍"},
    {"name_uz": "Animatsiya", "name_ru": "Мультфильм", "emoji": "🎨"},
    {"name_uz": "Hujjatli", "name_ru": "Документальный", "emoji": "📹"},
    {"name_uz": "Tarixiy", "name_ru": "Исторический", "emoji": "⚔️"},
    {"name_uz": "Sport", "name_ru": "Спортивный", "emoji": "⚽"},
    {"name_uz": "Musiqiy", "name_ru": "Музыкальный", "emoji": "🎵"},
    {"name_uz": "Oilaviy", "name_ru": "Семейный", "emoji": "👨‍👩‍👧‍👦"},
    {"name_uz": "Sarguzasht", "name_ru": "Приключения", "emoji": "🗺"},
    {"name_uz": "Ilmiy-fantastik", "name_ru": "Научная фантастика", "emoji": "🔬"},
    {"name_uz": "Urush", "name_ru": "Военный", "emoji": "🎖"},
    {"name_uz": "Biografik", "name_ru": "Биография", "emoji": "📖"},
    {"name_uz": "Koreya dramasi", "name_ru": "Корейская дорама", "emoji": "🇰🇷"},
    {"name_uz": "Turk seriali", "name_ru": "Турецкий сериал", "emoji": "🇹🇷"},
]


async def seed():
    await create_db()

    async with async_session() as session:
        for genre_data in DEFAULT_GENRES:
            # Check if exists
            result = await session.execute(
                select(Genre).where(Genre.name_uz == genre_data["name_uz"])
            )
            if not result.scalar_one_or_none():
                genre = Genre(**genre_data)
                session.add(genre)
                print(f"  + {genre_data['emoji']} {genre_data['name_uz']}")

        await session.commit()
        print("\n✅ Genres seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
