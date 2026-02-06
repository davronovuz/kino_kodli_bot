from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from database.repositories import MovieRepository, UserRepository, StatsRepository
from keyboards.inline import (
    movie_detail_kb, pagination_kb, main_menu_kb,
    genres_kb,
)
from utils.helpers import format_movie_caption, format_movie_list_item, calculate_pages
from services.cache_service import CacheService
from states.admin_states import SearchStates
from config import config

router = Router()


@router.message(F.text == "🔍 Qidirish")
async def search_prompt(message: Message, state: FSMContext):
    await state.set_state(SearchStates.waiting_query)
    await message.answer(
        "🔍 <b>Qidirish</b>\n\nKino nomini yoki kodini yozing:",
        parse_mode="HTML",
    )


@router.message(F.text == "🔥 Top kinolar")
async def top_movies(message: Message, session: AsyncSession):
    movies = await MovieRepository.get_popular(session, limit=config.MOVIES_PER_PAGE)
    if not movies:
        await message.answer("📭 Hozircha kinolar yo'q.")
        return

    text = "🔥 <b>Top kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("top", 1, pages) if pages > 1 else None

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("top:"))
async def top_movies_page(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    page = int(parts[1])
    offset = (page - 1) * config.MOVIES_PER_PAGE

    movies = await MovieRepository.get_popular(session, limit=config.MOVIES_PER_PAGE, offset=offset)
    if not movies:
        await callback.answer("Boshqa kinolar yo'q")
        return

    text = "🔥 <b>Top kinolar:</b>\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("top", page, pages)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.message(F.text == "🆕 Yangilari")
async def new_movies(message: Message, session: AsyncSession):
    movies = await MovieRepository.get_latest(session, limit=config.MOVIES_PER_PAGE)
    if not movies:
        await message.answer("📭 Hozircha kinolar yo'q.")
        return

    text = "🆕 <b>Yangi kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("new", 1, pages) if pages > 1 else None

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("new:"))
async def new_movies_page(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    page = int(parts[1])
    offset = (page - 1) * config.MOVIES_PER_PAGE

    movies = await MovieRepository.get_latest(session, limit=config.MOVIES_PER_PAGE, offset=offset)
    if not movies:
        await callback.answer("Boshqa kinolar yo'q")
        return

    text = "🆕 <b>Yangi kinolar:</b>\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("new", page, pages)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.message(F.text == "🎬 Janrlar")
async def show_genres(message: Message, session: AsyncSession):
    from sqlalchemy import select
    from database.models import Genre

    result = await session.execute(select(Genre).order_by(Genre.name_uz))
    genres = result.scalars().all()

    if not genres:
        await message.answer("📭 Hozircha janrlar yo'q.")
        return

    await message.answer(
        "🎬 <b>Janrni tanlang:</b>",
        reply_markup=genres_kb(genres),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("genre:"))
async def genre_movies(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    genre_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 1
    offset = (page - 1) * config.MOVIES_PER_PAGE

    movies, total = await MovieRepository.get_by_genre(
        session, genre_id, limit=config.MOVIES_PER_PAGE, offset=offset
    )

    if not movies:
        await callback.answer("Bu janrda kinolar topilmadi")
        return

    text = "🎬 <b>Janr bo'yicha kinolar:</b>\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n💡 Kino ko'rish uchun kodini yuboring."

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("genre", page, pages, str(genre_id)) if pages > 1 else None

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.message(F.text == "📊 Mening statistikam")
async def my_stats(message: Message, session: AsyncSession):
    user = await UserRepository.get_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini yuboring.")
        return

    text = (
        f"📊 <b>Sizning statistikangiz</b>\n\n"
        f"🔍 Qidiruvlar soni: <b>{user.search_count}</b>\n"
        f"🎬 Ko'rilgan kinolar: <b>{user.movies_watched}</b>\n"
        f"📅 Ro'yxatdan o'tgan: <b>{user.joined_at.strftime('%d.%m.%Y')}</b>\n"
        f"⏰ Oxirgi faollik: <b>{user.last_active.strftime('%d.%m.%Y %H:%M')}</b>"
    )
    await message.answer(text, parse_mode="HTML")
