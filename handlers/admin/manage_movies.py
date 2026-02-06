from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from filters.admin_filter import IsAdmin
from database.repositories import MovieRepository
from keyboards.inline import (
    admin_menu_kb, admin_movie_actions_kb, pagination_kb,
    confirm_kb,
)
from utils.helpers import format_movie_list_item, format_movie_caption, calculate_pages
from services.cache_service import CacheService
from config import config

router = Router()
router.message.filter(IsAdmin())


@router.message(F.text == "📋 Kinolar ro'yxati")
async def list_movies(message: Message, session: AsyncSession):
    movies, total = await MovieRepository.get_all_movies(
        session, limit=config.MOVIES_PER_PAGE
    )
    if not movies:
        await message.answer("📭 Kinolar bazasi bo'sh.")
        return

    text = f"📋 <b>Kinolar ro'yxati</b> ({total} ta):\n\n"
    for i, movie in enumerate(movies, 1):
        status = "✅" if movie.is_active else "❌"
        text += f"{status} {format_movie_list_item(movie, i)}\n"

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("amovies", 1, pages) if pages > 1 else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("amovies:"))
async def list_movies_page(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    page = int(parts[1])
    offset = (page - 1) * config.MOVIES_PER_PAGE

    movies, total = await MovieRepository.get_all_movies(
        session, limit=config.MOVIES_PER_PAGE, offset=offset
    )
    if not movies:
        await callback.answer("Boshqa kino yo'q")
        return

    text = f"📋 <b>Kinolar ro'yxati</b> ({total} ta):\n\n"
    for i, movie in enumerate(movies, offset + 1):
        status = "✅" if movie.is_active else "❌"
        text += f"{status} {format_movie_list_item(movie, i)}\n"

    pages = calculate_pages(total, config.MOVIES_PER_PAGE)
    kb = pagination_kb("amovies", page, pages)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("mdel:"))
async def delete_movie_confirm(callback: CallbackQuery, state: FSMContext):
    movie_id = int(callback.data.split(":")[1])
    await state.update_data(delete_movie_id=movie_id)
    await callback.message.edit_text(
        "🗑 <b>Haqiqatan o'chirmoqchimisiz?</b>\n\nBu amalni qaytarib bo'lmaydi!",
        reply_markup=confirm_kb("delmovie"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delmovie:"))
async def delete_movie_action(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    action = callback.data.split(":")[1]
    data = await state.get_data()
    movie_id = data.get("delete_movie_id")

    if action == "no" or not movie_id:
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.answer()
        await state.clear()
        return

    movie = await MovieRepository.get_by_id(session, movie_id)
    if movie:
        await MovieRepository.delete_movie(session, movie_id)
        await CacheService.invalidate_movie(movie.code)
        await callback.message.edit_text(
            f"✅ Kino o'chirildi: [{movie.code}] {movie.title}",
            parse_mode="HTML",
        )
        logger.info(f"Movie deleted: {movie.code} by admin {callback.from_user.id}")
    else:
        await callback.message.edit_text("❌ Kino topilmadi.")

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin_movies_back")
async def admin_movies_back(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()
