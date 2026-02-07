from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories import MovieRepository, UserRepository, StatsRepository
from keyboards.inline import (
    pagination_kb, genres_kb, categories_kb,
)
from keyboards.reply import main_menu_kb
from utils.helpers import format_movie_list_item, calculate_pages
from states.admin_states import SearchStates
from config import config

router = Router()


@router.message(F.text == "🔍 Qidirish")
async def search_prompt(message: Message, state: FSMContext):
    await state.set_state(SearchStates.waiting_query)
    await message.answer(
        "🔍 Kino nomini yoki kodini yozing:",
        parse_mode="HTML",
    )


@router.message(F.text == "🔥 Top kinolar")
async def top_movies(message: Message, session: AsyncSession):
    movies = await MovieRepository.get_popular(session, limit=config.MOVIES_PER_PAGE)
    if not movies:
        await message.answer("📭 Kinolar yo'q.")
        return

    text = "🔥 <b>Top kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("top", 1, pages) if pages > 1 else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("top:"))
async def top_page(callback: CallbackQuery, session: AsyncSession):
    page = int(callback.data.split(":")[1])
    offset = (page - 1) * config.MOVIES_PER_PAGE
    movies = await MovieRepository.get_popular(session, limit=config.MOVIES_PER_PAGE, offset=offset)
    if not movies:
        await callback.answer("Boshqa yo'q")
        return

    text = "🔥 <b>Top kinolar:</b>\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=pagination_kb("top", page, pages))
    except Exception:
        pass
    await callback.answer()


@router.message(F.text == "🆕 Yangilari")
async def new_movies(message: Message, session: AsyncSession):
    movies = await MovieRepository.get_latest(session, limit=config.MOVIES_PER_PAGE)
    if not movies:
        await message.answer("📭 Kinolar yo'q.")
        return

    text = "🆕 <b>Yangi kinolar:</b>\n\n"
    for i, movie in enumerate(movies, 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("new", 1, pages) if pages > 1 else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("new:"))
async def new_page(callback: CallbackQuery, session: AsyncSession):
    page = int(callback.data.split(":")[1])
    offset = (page - 1) * config.MOVIES_PER_PAGE
    movies = await MovieRepository.get_latest(session, limit=config.MOVIES_PER_PAGE, offset=offset)
    if not movies:
        await callback.answer("Boshqa yo'q")
        return

    text = "🆕 <b>Yangi kinolar:</b>\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

    total = await MovieRepository.get_total_count(session)
    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=pagination_kb("new", page, pages))
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
        await message.answer("📭 Janrlar yo'q.")
        return
    await message.answer("🎬 <b>Janr tanlang:</b>", reply_markup=genres_kb(genres), parse_mode="HTML")


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
        await callback.answer("Bu janrda kinolar yo'q")
        return

    text = "🎬 <b>Janr bo'yicha:</b>\n\n"
    for i, movie in enumerate(movies, offset + 1):
        text += format_movie_list_item(movie, i) + "\n"
    text += "\n🔢 Kodini yuboring."

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
        await message.answer("/start yuboring.")
        return

    text = (
        f"📊 <b>Sizning statistikangiz</b>\n\n"
        f"🔍 Qidiruvlar: <b>{user.search_count}</b>\n"
        f"🎬 Ko'rishlar: <b>{user.movies_watched}</b>\n"
        f"📅 Qo'shilgan: <b>{user.joined_at.strftime('%d.%m.%Y')}</b>\n"
        f"⏰ Oxirgi: <b>{user.last_active.strftime('%d.%m.%Y %H:%M')}</b>"
    )
    await message.answer(text, parse_mode="HTML")